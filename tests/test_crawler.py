"""
Automated unit tests for CrawlerService (FR-1: Polite & Compliant Web Ingestion).
"""

import pytest
from src.ingestion.crawler import CrawlerService
from src.ingestion.urls import AUTHORIZED_URLS


@pytest.mark.asyncio
async def test_crawler_user_agent_and_headers():
    crawler = CrawlerService()
    assert crawler.user_agent == "PlacidWayAssessmentBot/1.0"
    assert crawler.headers["User-Agent"] == "PlacidWayAssessmentBot/1.0"


@pytest.mark.asyncio
async def test_robots_txt_allows_authorized_urls():
    crawler = CrawlerService()
    for item in AUTHORIZED_URLS:
        url = item["url"]
        is_allowed = await crawler.check_robots_txt(url)
        assert is_allowed is True, f"Robots.txt should permit authorized URL: {url}"


@pytest.mark.asyncio
async def test_robots_txt_disallows_forbidden_paths():
    crawler = CrawlerService()
    # /video/5469/ is explicitly disallowed in placid_way.robots.txt
    disallowed_url = "https://www.placidway.com/video/5469/test"
    is_allowed = await crawler.check_robots_txt(disallowed_url)
    assert is_allowed is False, "Robots.txt should disallow /video/5469/"


@pytest.mark.asyncio
async def test_cached_html_retrieval():
    crawler = CrawlerService()
    # Test loading from cache for Page 1
    page_1 = AUTHORIZED_URLS[0]
    cached_html = await crawler.fetch_page(url=page_1["url"], page_id=page_1["id"], force_refresh=False)
    assert cached_html is not None
    assert len(cached_html) > 1000
    assert "Immunity Therapy Center" in cached_html
