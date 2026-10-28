import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from src.utils.config import settings
from src.ingestion.urls import AUTHORIZED_URLS
from src.utils.rate_limiter import limit_it

logger = logging.getLogger(__name__)

class CrawlerService:
    """
    Asynchronous polite crawler for authorized PlacidWay URLs.
    Combines robots.txt enforcement, rate-limiting, semaphore concurrency bounding,
    and tenacity retry handling.
    """

    def __init__(
        self,
        user_agent: Optional[str] = None,
        rate_limit_delay: Optional[float] = None,
        raw_html_dir: Optional[Path] = None,
    ):
        self.user_agent = user_agent or settings.CRAWLER_USER_AGENT
        self.rate_limit_delay = rate_limit_delay or settings.CRAWLER_RATE_LIMIT_DELAY
        self.raw_html_dir = raw_html_dir or settings.RAW_HTML_DIR
        self.raw_html_dir.mkdir(parents=True, exist_ok=True)

        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        self._robot_parser: Optional[RobotFileParser] = None

    async def _init_robots_parser(self, client: httpx.AsyncClient) -> None:
        """Fetch and parse robots.txt, or fall back to local file if offline."""
        if self._robot_parser is not None:
            return

        parser = RobotFileParser()
        robots_url = settings.ROBOTS_TXT_URL

        try:
            logger.info("Fetching robots.txt from %s...", robots_url)
            resp = await client.get(robots_url, headers=self.headers, timeout=15.0)
            if resp.status_code == 200:
                parser.parse(resp.text.splitlines())
                self._robot_parser = parser
                logger.info("Successfully parsed live robots.txt")
                return
        except Exception as e:
            logger.warning("Live robots.txt fetch failed (%s). Checking local fallback...", e)

        # Fallback to placid_way.robots.txt in project root
        local_robots_path = settings.BASE_DIR / "placid_way.robots.txt"
        if local_robots_path.exists():
            logger.info("Parsing local placid_way.robots.txt fallback...")
            with open(local_robots_path, "r", encoding="utf-8") as f:
                parser.parse(f.readlines())
            self._robot_parser = parser
            logger.info("Successfully parsed local robots.txt")
        else:
            logger.warning("No local robots.txt found. Defaulting to permissive parser.")
            parser.allow_all = True
            self._robot_parser = parser

    async def check_robots_txt(self, url: str, client: Optional[httpx.AsyncClient] = None) -> bool:
        """
        Verify whether the given URL is permitted for this user agent by robots.txt.
        """
        if self._robot_parser is None:
            if client is None:
                async with httpx.AsyncClient(timeout=15.0) as temp_client:
                    await self._init_robots_parser(temp_client)
            else:
                await self._init_robots_parser(client)

        allowed = self._robot_parser.can_fetch(self.user_agent, url)
        if not allowed:
            # Also check wildcard user-agent
            allowed = self._robot_parser.can_fetch("*", url)

        return allowed

    def _get_cache_path(self, url: str, page_id: Optional[int] = None) -> Path:
        """Generate a deterministic file path for caching raw HTML."""
        parsed = urlparse(url)
        clean_path = re.sub(r"[^\w\-]", "_", parsed.path.strip("/"))
        if not clean_path:
            clean_path = "root"
        prefix = f"page_{page_id}_" if page_id else ""
        filename = f"{prefix}{clean_path}.html"
        return self.raw_html_dir / filename

    @limit_it(delay_seconds=1, max_concurrent=1)
    async def fetch_page(
        self,
        url: str,
        page_id: Optional[int] = None,
        client: Optional[httpx.AsyncClient] = None,
        force_refresh: bool = False,
    ) -> Optional[str]:
        """
        Fetch HTML for a single URL with compliance checks, rate limits, semaphore lock, and caching.
        """
        cache_path = self._get_cache_path(url, page_id)

        # 1. Use cached HTML if available and refresh is not forced
        if not force_refresh and cache_path.exists():
            logger.debug("Loading cached HTML for %s (%s)", url, cache_path.name)
            return cache_path.read_text(encoding="utf-8")

        # 2. Check robots.txt compliance
        should_close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
            should_close_client = True

        try:
            is_allowed = await self.check_robots_txt(url, client=client)
            if not is_allowed:
                logger.error("Access denied by robots.txt for URL: %s", url)
                raise PermissionError(f"URL disallowed by robots.txt: {url}")

            # 3. Fetch with Semaphore, Rate Limiter, and Tenacity Retry
            response = await client.get(url, headers=self.headers, timeout=30.0)
            response.raise_for_status()
            html_content = response.text

            # 4. Save to disk cache
            cache_path.write_text(html_content, encoding="utf-8")
            logger.info("Saved raw HTML (%d bytes) to %s", len(html_content), cache_path.name)

            return html_content

        finally:
            if should_close_client:
                await client.aclose()

    async def fetch_all(
        self,
        target_urls: Optional[List[Dict[str, Any]]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, str]:
        """
        Sequentially fetch all target URLs with rate-limiting.
        Returns a dictionary mapping {url: raw_html_content}.
        """
        targets = target_urls or AUTHORIZED_URLS
        results: Dict[str, str] = {}

        logger.info("Starting crawl for %d authorized URLs...", len(targets))

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # Ensure robots.txt is loaded first
            await self._init_robots_parser(client)

            for item in targets:
                url = item["url"]
                page_id = item.get("id")
                try:
                    html = await self.fetch_page(
                        url=url,
                        page_id=page_id,
                        client=client,
                        force_refresh=force_refresh,
                    )
                    if html:
                        results[url] = html
                except Exception as e:
                    logger.error("Error fetching %s: %s", url, e)

        logger.info("Crawl completed: %d/%d pages fetched.", len(results), len(targets))
        return results