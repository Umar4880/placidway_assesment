"""
Live Knowledge Base Refresh route (FR-7).
Re-crawls the 7 authorized URLs (respecting the 1 req/sec politeness rule),
re-chunks the content, and atomically updates the index without downtime.
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.ingestion.pipeline import IngestionPipeline
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
        logger.info("Executing on-demand knowledge base refresh via IngestionPipeline...")
        pipeline = IngestionPipeline()
        service = get_orchestration_service()

        # 1. Polite crawling & cleaning of authorized URLs
        output_files = await pipeline.run(force_refresh=True)

        # 2. Re-chunk & index markdown files into Qdrant in executor thread
        loop = asyncio.get_running_loop()
        chunks_count = await loop.run_in_executor(
            None,
            lambda: service.retriever.embedding_service.index_all_markdown(force_recreate=True),
        )

        urls_count = len(output_files)
        logger.info(
            "Refresh complete: %d URLs crawled, %d chunks indexed.",
            urls_count,
            chunks_count,
        )

        return RefreshResponse(
            status="success",
            urls_crawled=urls_count,
            chunks_indexed=chunks_count,
            message=f"Successfully re-crawled {urls_count} authorized pages and indexed {chunks_count} chunks.",
        )
    except Exception as e:
        logger.error("Error refreshing knowledge base: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
