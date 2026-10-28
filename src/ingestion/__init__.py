"""
Ingestion module for fetching, cleaning, chunking, and embedding PlacidWay target URLs.
"""

from src.ingestion.urls import AUTHORIZED_URLS
from src.ingestion.crawler import CrawlerService
from src.ingestion.cleaner import DOMCleaner
from src.ingestion.chunker import ChunkingService, HeaderAwareChunker
from src.ingestion.embedding import EmbeddingService
from src.ingestion.pipeline import IngestionPipeline

__all__ = [
    "AUTHORIZED_URLS",
    "CrawlerService",
    "DOMCleaner",
    "ChunkingService",
    "HeaderAwareChunker",
    "EmbeddingService",
    "IngestionPipeline",
]
