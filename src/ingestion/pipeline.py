"""
Ingestion Pipeline Coordinator.
Coordinates:
1. Fetching raw HTML files via CrawlerService (or loading cached files).
2. Cleaning raw HTML and stripping recommendation carousels via DOMCleaner.
3. Preserving pricing tables and structured inclusion lists in GitHub-Flavored Markdown.
4. Saving cleaned Markdown files to data/markdown/ for chunking and hybrid indexing.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from src.utils.config import settings
from src.ingestion.crawler import CrawlerService
from src.ingestion.cleaner import DOMCleaner
from src.ingestion.urls import AUTHORIZED_URLS

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Coordinates web ingestion: Polite crawling -> DOM pruning -> Markdown persistence.
    """

    def __init__(
        self,
        crawler: Optional[CrawlerService] = None,
        cleaner: Optional[DOMCleaner] = None,
        markdown_dir: Optional[Path] = None,
    ):
        self.crawler = crawler or CrawlerService()
        self.cleaner = cleaner or DOMCleaner()
        self.markdown_dir = markdown_dir or settings.MARKDOWN_DIR
        try:
            self.markdown_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _get_markdown_path(self, item: Dict[str, Any]) -> Path:
        """Generate a deterministic filename for the markdown file."""
        page_id = item.get("id", 1)
        url = item["url"]
        parsed = urlparse(url)
        clean_path = re.sub(r"[^\w\-]", "_", parsed.path.strip("/"))
        if not clean_path:
            clean_path = "root"
        return self.markdown_dir / f"page_{page_id}_{clean_path}.md"

    async def run(self, force_refresh: bool = False) -> Dict[str, Path]:
        """
        Execute ingestion pipeline across all authorized URLs.
        Returns a dictionary mapping {url: markdown_file_path}.
        """
        logger.info("Executing Ingestion Pipeline (force_refresh=%s)...", force_refresh)
        html_pages = await self.crawler.fetch_all(target_urls=AUTHORIZED_URLS, force_refresh=force_refresh)

        output_files: Dict[str, Path] = {}

        for item in AUTHORIZED_URLS:
            url = item["url"]
            raw_html = html_pages.get(url)

            if not raw_html:
                logger.warning("No HTML available for %s, skipping markdown conversion.", url)
                continue

            # Clean DOM and convert to Markdown
            markdown_content = self.cleaner.clean_html(raw_html=raw_html, metadata=item)

            # Save clean markdown file
            md_path = self._get_markdown_path(item)
            md_path.write_text(markdown_content, encoding="utf-8")
            logger.info("Saved clean Markdown for %s -> %s (%d chars)", url, md_path.name, len(markdown_content))

            output_files[url] = md_path

        logger.info("Ingestion complete. %d/%d Markdown files generated in %s.", len(output_files), len(AUTHORIZED_URLS), self.markdown_dir)
        return output_files
