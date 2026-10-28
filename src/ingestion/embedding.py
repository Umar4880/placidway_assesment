"""
Native Qdrant Hybrid Vector Store Service (Dense Semantic + FastEmbed BM25 Sparse).

Features:
1. Native Qdrant named vectors: 'dense' (Google text-embedding-004 / FastEmbed BGE-small)
   and 'sparse' (FastEmbed Qdrant/bm25).
2. Native in-engine Reciprocal Rank Fusion (RRF) query.
3. Automatically writes all generated chunks into .debug/chunks/ for developer inspection.
4. Automatically records retrieved chunks per query into .debug/retrievals/ for evaluation auditing.
5. Deterministic UUID generation for idempotent upserts.
"""

import os
import json
import uuid
import logging
import atexit
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from qdrant_client import QdrantClient, models

from src.utils.config import settings
from src.llm.client import get_dense_embeddings, get_sparse_embeddings
from src.ingestion.chunker import ChunkingService

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME = "placidway_knowledge_base"


class EmbeddingService:
    """
    Manages native Qdrant dual-vector (Dense + BM25 Sparse) indexing and RRF hybrid retrieval.
    """

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        client: Optional[QdrantClient] = None,
    ):
        self.collection_name = collection_name
        self.dense_embedder = get_dense_embeddings()
        self.sparse_embedder = get_sparse_embeddings()

        # Initialize Qdrant Client
        if client is not None:
            self.client = client
        elif settings.QDRANT_MODE == "memory":
            logger.info("Initializing in-memory Qdrant client.")
            self.client = QdrantClient(":memory:")
        elif (settings.QDRANT_MODE == "remote" or bool(settings.QDRANT_URL)) and settings.QDRANT_URL:
            logger.info("Connecting to remote Qdrant at %s", settings.QDRANT_URL)
            self.client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY or None,
                timeout=60,
            )
        else:
            storage_path = settings.QDRANT_STORAGE_DIR
            if os.environ.get("VERCEL"):
                tmp_qdrant = Path("/tmp/data/qdrant")
                if tmp_qdrant.exists():
                    storage_path = tmp_qdrant
            try:
                storage_path.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            logger.info("Initializing embedded persistent Qdrant at %s", storage_path)
            try:
                self.client = QdrantClient(path=str(storage_path))
            except Exception as exc:
                if "already accessed" in str(exc).lower() or "lock" in str(exc).lower() or "read-only" in str(exc).lower():
                    logger.warning(
                        "Qdrant directory is locked or read-only (%s). Falling back to in-memory mode.",
                        exc,
                    )
                    self.client = QdrantClient(":memory:")
                else:
                    raise

        # Setup debug paths (safe for read-only Vercel environment)
        self.debug_dir = Path("/tmp/.debug") if os.environ.get("VERCEL") else settings.DEBUG_DIR
        self.debug_chunks_dir = self.debug_dir / "chunks"
        self.debug_retrievals_dir = self.debug_dir / "retrievals"
        try:
            self.debug_chunks_dir.mkdir(parents=True, exist_ok=True)
            self.debug_retrievals_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        self._ensure_collection()
        atexit.register(self.close)

    def close(self) -> None:
        """Cleanly close QdrantClient to release OS locks on Windows."""
        if hasattr(self, "client") and self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass

    def _probe_dense_dimension(self) -> int:
        """Dynamically detect dense embedding dimension."""
        sample_vec = self.dense_embedder.embed_query("probe")
        return len(sample_vec)

    def _ensure_collection(self) -> None:
        """Create Qdrant collection with named dense and sparse vectors if not existing."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            dense_dim = self._probe_dense_dimension()
            logger.info(
                "Creating Qdrant collection '%s' with Dense(dim=%d, Cosine) and Sparse(bm25)",
                self.collection_name,
                dense_dim,
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=dense_dim,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(
                        index=models.SparseIndexParams(on_disk=False)
                    )
                },
            )

    def _write_debug_chunks(self, documents: List[Document]) -> None:
        """Writes the generated chunks to .debug/chunks/ for developer inspection."""
        try:
            chunks_data = []
            pages_data: Dict[int, List[Dict[str, Any]]] = {}

            for idx, doc in enumerate(documents, start=1):
                chunk_dict = {
                    "index": idx,
                    "chunk_id": doc.metadata.get("chunk_id", f"chunk_{idx}"),
                    "page_id": doc.metadata.get("page_id", 0),
                    "document_title": doc.metadata.get("document_title", ""),
                    "source_url": doc.metadata.get("source_url", ""),
                    "page_type": doc.metadata.get("page_type", ""),
                    "section_path": doc.metadata.get("section_path", ""),
                    "is_table": doc.metadata.get("is_table", False),
                    "raw_table": doc.metadata.get("raw_table"),
                    "key_figures": doc.metadata.get("key_figures", {}),
                    "char_count": len(doc.page_content),
                    "word_count": len(doc.page_content.split()),
                    "page_content": doc.page_content,
                }
                chunks_data.append(chunk_dict)

                page_id = doc.metadata.get("page_id", 0)
                pages_data.setdefault(page_id, []).append(chunk_dict)

            # 1. Write consolidated all_chunks.json
            all_chunks_file = self.debug_chunks_dir / "all_chunks.json"
            all_chunks_file.write_text(
                json.dumps(chunks_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # 2. Write per-page files for granular inspection
            for p_id, p_chunks in pages_data.items():
                p_file = self.debug_chunks_dir / f"page_{p_id}_chunks.json"
                p_file.write_text(
                    json.dumps(p_chunks, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

            logger.info("Wrote %d debug chunks to %s", len(documents), self.debug_chunks_dir)
        except Exception as e:
            logger.warning("Failed to write debug chunks (%s)", e)

    def _write_debug_retrieval(self, query: str, retrieved_docs: List[Document]) -> None:
        """Records retrieved chunks for a query into .debug/retrievals/."""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            retrieval_entry = {
                "query": query,
                "timestamp": timestamp,
                "retrieved_count": len(retrieved_docs),
                "chunks": [
                    {
                        "rank": rank,
                        "score": round(doc.metadata.get("score", 0.0), 4),
                        "chunk_id": doc.metadata.get("chunk_id", ""),
                        "document_title": doc.metadata.get("document_title", ""),
                        "section_path": doc.metadata.get("section_path", ""),
                        "source_url": doc.metadata.get("source_url", ""),
                        "is_table": doc.metadata.get("is_table", False),
                        "key_figures": doc.metadata.get("key_figures", {}),
                        "content_preview": doc.page_content[:300] + ("..." if len(doc.page_content) > 300 else ""),
                    }
                    for rank, doc in enumerate(retrieved_docs, start=1)
                ],
            }

            # 1. Update last_retrieval.json
            last_file = self.debug_retrievals_dir / "last_retrieval.json"
            last_file.write_text(
                json.dumps(retrieval_entry, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # 2. Append to queries.jsonl
            history_file = self.debug_retrievals_dir / "queries.jsonl"
            with history_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(retrieval_entry, ensure_ascii=False) + "\n")

            logger.debug("Logged debug retrieval for query '%s' to %s", query, self.debug_retrievals_dir)
        except Exception as e:
            logger.warning("Failed to write debug retrieval log (%s)", e)

    def index_documents(
        self,
        documents: List[Document],
        batch_size: int = 32,
    ) -> int:
        """
        Embed and index chunks into local Qdrant collection with named dense + sparse vectors.
        """
        if not documents:
            logger.warning("No documents provided for indexing.")
            return 0

        # Output chunks into .debug/
        if settings.MODE == "DEV":
            self._write_debug_chunks(documents)

        logger.info("Indexing %d chunks into Qdrant collection '%s'...", len(documents), self.collection_name)
        texts = [doc.page_content for doc in documents]

        # 1. Compute Dense Embeddings in batches with rate-limit protection
        import time
        all_dense_vectors: List[List[float]] = []
        eff_batch_size = min(batch_size, 16)
        total_batches = (len(texts) + eff_batch_size - 1) // eff_batch_size

        for b_idx in range(total_batches):
            start_i = b_idx * eff_batch_size
            batch_texts = texts[start_i : start_i + eff_batch_size]

            for attempt in range(4):
                try:
                    dense_batch = self.dense_embedder.embed_documents(batch_texts)
                    all_dense_vectors.extend(dense_batch)
                    time.sleep(1.0)  # Politeness interval between embedding batches
                    break
                except Exception as e:
                    if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                        logger.warning(
                            "Gemini embedding rate limit reached for batch %d/%d. Waiting 15s for quota reset...",
                            b_idx + 1,
                            total_batches,
                        )
                        time.sleep(15)
                    elif attempt < 3:
                        time.sleep(2)
                    else:
                        raise

        # 2. Compute Sparse BM25 Embeddings
        sparse_generator = self.sparse_embedder.embed(texts)
        all_sparse_vectors = list(sparse_generator)

        # 3. Build PointStruct list with deterministic UUIDs
        points: List[models.PointStruct] = []
        for idx, doc in enumerate(documents):
            chunk_id = doc.metadata.get("chunk_id", f"chunk_{idx}")
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))

            sparse_obj = all_sparse_vectors[idx]
            sparse_vector = models.SparseVector(
                indices=sparse_obj.indices.tolist(),
                values=sparse_obj.values.tolist(),
            )

            payload = {
                "chunk_id": chunk_id,
                "page_id": doc.metadata.get("page_id", 0),
                "document_title": doc.metadata.get("document_title", ""),
                "source_url": doc.metadata.get("source_url", ""),
                "page_type": doc.metadata.get("page_type", ""),
                "section_path": doc.metadata.get("section_path", ""),
                "is_table": doc.metadata.get("is_table", False),
                "raw_table": doc.metadata.get("raw_table"),
                "key_figures": doc.metadata.get("key_figures", {}),
                "page_content": doc.page_content,
            }

            point = models.PointStruct(
                id=point_id,
                vector={
                    "dense": all_dense_vectors[idx],
                    "sparse": sparse_vector,
                },
                payload=payload,
            )
            points.append(point)

        # 4. Upsert into Qdrant in smaller batches with timeout protection
        upsert_batch_size = 20
        for i in range(0, len(points), upsert_batch_size):
            batch_points = points[i : i + upsert_batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch_points,
            )

        logger.info(
            "Successfully indexed %d hybrid points into Qdrant '%s'.",
            len(points),
            self.collection_name,
        )
        return len(points)

    def search(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Perform native hybrid search using Qdrant in-engine Reciprocal Rank Fusion (RRF).
        Fuses Dense semantic search and BM25 sparse keyword search natively.
        """
        if not query or not query.strip():
            return []

        # 1. Embed query (dense via Gemini Embeddings)
        dense_query = self.dense_embedder.embed_query(query)

        query_filter = None
        if filter_dict:
            must_conditions = [
                models.FieldCondition(key=k_field, match=models.MatchValue(value=v_val))
                for k_field, v_val in filter_dict.items()
            ]
            query_filter = models.Filter(must=must_conditions)

        # 2. Execute search: hybrid RRF if sparse embedder is active, else dense-only
        if self.sparse_embedder is not None:
            try:
                sparse_query_obj = list(self.sparse_embedder.embed([query]))[0]
                sparse_vector = models.SparseVector(
                    indices=sparse_query_obj.indices.tolist(),
                    values=sparse_query_obj.values.tolist(),
                )
                prefetch = [
                    models.Prefetch(
                        query=dense_query,
                        using="dense",
                        limit=k * 2,
                    ),
                    models.Prefetch(
                        query=sparse_vector,
                        using="sparse",
                        limit=k * 2,
                    ),
                ]
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    prefetch=prefetch,
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    query_filter=query_filter,
                    limit=k,
                )
            except Exception as e:
                logger.warning("Sparse RRF prefetch failed (%s). Using dense query.", e)
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=dense_query,
                    using="dense",
                    query_filter=query_filter,
                    limit=k,
                )
        else:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=dense_query,
                using="dense",
                query_filter=query_filter,
                limit=k,
            )

        # 4. Convert to LangChain Document list
        retrieved_docs: List[Document] = []
        for point in response.points:
            payload = point.payload or {}
            metadata = {
                **payload,
                "score": point.score,
            }
            # Remove page_content from metadata to avoid duplication
            content = metadata.pop("page_content", "")
            retrieved_docs.append(Document(page_content=content, metadata=metadata))

        # 5. Write debug retrieval log
        if settings.MODE == "DEV":
            self._write_debug_retrieval(query, retrieved_docs)

        return retrieved_docs

    def index_all_markdown(self, force_recreate: bool = False) -> int:
        """
        Reads all markdown documents in data/markdown/, chunks them, and indexes into Qdrant.
        """
        if force_recreate:
            logger.info("Force recreating Qdrant collection '%s'...", self.collection_name)
            self.client.delete_collection(self.collection_name)
            self._ensure_collection()

        chunker = ChunkingService()
        chunks = chunker.chunk_all()
        return self.index_documents(chunks)
