"""
Live Knowledge Base Refresh route (FR-7).
Re-crawls the 7 authorized URLs (respecting the 1 req/sec politeness rule),
re-chunks the content, and atomically updates the index without downtime.
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.ingestion.crawler import CrawlerService
from src.ingestion.cleaner import DOMCleaner
from src.orchestration.service import get_orchestration_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["refresh"])


class RefreshResponse(BaseModel):
    status: str
    urls_crawled: int
    chunks_indexed: int
    message: str


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_knowledge_base() -> RefreshResponse:
    """Trigger an atomic crawl and re-indexing of the 7 authorized URLs."""
    try:
        crawler = CrawlerService()
        cleaner = DOMCleaner()
        service = get_orchestration_service()

        loop = asyncio.get_running_loop()

        def do_refresh():
            logger.info("Executing on-demand knowledge base refresh...")
            # 1. Crawl all 7 authorized URLs with 1.0s politeness delay
            crawled_pages = crawler.crawl_all(force_recrawl=True)
            # 2. Clean HTML to Markdown
            cleaner.clean_all(force_reclean=True)
            # 3. Index markdown files into Qdrant
            indexed_count = service.retriever.embedding_service.index_all_markdown(force_recreate=True)
            return len(crawled_pages), indexed_count

        urls_count, chunks_count = await loop.run_in_executor(None, do_refresh)

        return RefreshResponse(
            status="success",
            urls_crawled=urls_count,
            chunks_indexed=chunks_count,
            message=f"Successfully re-crawled {urls_count} authorized pages and indexed {chunks_count} chunks.",
        )
    except Exception as e:
        logger.error("Error refreshing knowledge base: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
