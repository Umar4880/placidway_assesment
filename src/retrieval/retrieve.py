"""
Hybrid Retriever combining Dense Vector search and FastEmbed BM25 keyword search
via native Qdrant Reciprocal Rank Fusion (RRF).
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document

from src.ingestion.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class HybridRetrieverService:
    """
    Unified hybrid retriever interface combining dense semantic search and BM25 keyword search.
    """

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self.embedding_service = embedding_service or EmbeddingService()

    def retrieve(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Execute native Qdrant RRF hybrid search.
        """
        return self.embedding_service.search(query=query, k=k, filter_dict=filter_dict)

    def refresh_index(self, documents: List[Document]) -> int:
        """
        Atomically refresh both dense and sparse vector indices.
        """
        return self.embedding_service.index_documents(documents)
