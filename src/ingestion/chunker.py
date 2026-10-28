"""
Header-Aware Context-Enriched Semantic Chunker with Table-RAG Protection.

Implements the two-stage chunking methodology:
1. Markdown header splitting on #, ##, ### to preserve clinical topic boundaries.
2. Short-chunk merging (< 40 words) to prevent hollow orphan fragments.
3. Table detection and semantic summarization (raw table preserved in metadata).
4. Table-preserving recursive sub-splitting for oversized sections (> 500 tokens).
5. Breadcrumb context injection at chunk header ([Document | Section | Source]).
6. Full corpus chunking via chunk_all().
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from src.utils.config import settings
from src.ingestion.urls import AUTHORIZED_URLS
from src.llm.table_summarizer import TableSummarizerService

logger = logging.getLogger(__name__)

# Regex pattern matching GitHub-Flavored Markdown tables
TABLE_REGEX = re.compile(r"(\|[^\n]+\|\n\|[-: |]+\|\n(?:\|[^\n]+\|\n?)+)")


class ChunkingService:
    """
    Production-grade chunking service for clinical and tabular medical tourism documents.
    """

    def __init__(
        self,
        target_chunk_size: int = 1800,  # ~450 tokens
        chunk_overlap: int = 200,      # ~50 tokens
        min_chunk_words: int = 40,      # Minimum words threshold for merging
        table_summarizer: Optional[TableSummarizerService] = None,
    ):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_words = min_chunk_words
        self.table_summarizer = table_summarizer or TableSummarizerService()

        # Stage 1: Header splitter on ATX headings
        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
            ],
            strip_headers=False,
        )

        # Stage 4: Sub-splitter for oversized non-table sections
        self.sub_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.target_chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " "],
        )

    def _build_breadcrumb_and_path(
        self, doc_metadata: Dict[str, Any], chunk_headers: Dict[str, str]
    ) -> tuple[str, str]:
        """
        Builds the 1-line text breadcrumb and the hierarchical section path string.
        """
        doc_title = doc_metadata.get("title", "ITC Alternative Cancer Treatment")
        source_url = doc_metadata.get("url", "https://www.placidway.com")

        header_parts = []
        for key in ["Header 1", "Header 2", "Header 3"]:
            if key in chunk_headers and chunk_headers[key]:
                h_val = chunk_headers[key].strip("# ").strip()
                if h_val and h_val not in header_parts:
                    header_parts.append(h_val)

        section_path = " > ".join(header_parts) if header_parts else "General Overview"
        breadcrumb = f"[Document: {doc_title} | Section: {section_path} | Source: {source_url}]"
        return breadcrumb, section_path

    def chunk_document(
        self,
        markdown_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Split a single clean markdown document into context-enriched, table-aware chunks.
        """
        if not markdown_text or not markdown_text.strip():
            return []

        meta = metadata or {}
        doc_title = meta.get("title", "PlacidWay Medical Document")
        source_url = meta.get("url", "")
        page_type = meta.get("page_type") or meta.get("type", "General")
        page_id = meta.get("id", 0)

        # 1. Stage 1: Header-aware split
        initial_docs = self.header_splitter.split_text(markdown_text)
        if not initial_docs:
            initial_docs = [Document(page_content=markdown_text, metadata={})]

        # 2. Stage 2: Short-chunk merging (< min_chunk_words)
        merged_docs: List[Document] = []
        for doc in initial_docs:
            words = doc.page_content.split()
            if merged_docs and len(words) < self.min_chunk_words:
                prev_doc = merged_docs[-1]
                # Merge into previous if within size limit and shares context
                if len(prev_doc.page_content.split()) + len(words) < 400:
                    prev_doc.page_content += "\n\n" + doc.page_content
                    for k, v in doc.metadata.items():
                        if k not in prev_doc.metadata:
                            prev_doc.metadata[k] = v
                    continue
            merged_docs.append(doc)

        final_chunks: List[Document] = []
        chunk_counter = 0

        # 3. Stages 3 & 4: Process tables and handle oversized chunks
        for section_doc in merged_docs:
            content = section_doc.page_content.strip()
            chunk_headers = section_doc.metadata
            breadcrumb, section_path = self._build_breadcrumb_and_path(meta, chunk_headers)

            # Check if this section contains a markdown table
            table_matches = list(TABLE_REGEX.finditer(content))
            if table_matches:
                for match in table_matches:
                    chunk_counter += 1
                    raw_table = match.group(1)

                    # Extract context before table (introductory paragraph)
                    text_before = content[: match.start()].strip()

                    # Extract text after table (capped to 50 words to capture short notes/caveats)
                    text_after = content[match.end() :].strip()
                    words_after = text_after.split()
                    table_notes = " ".join(words_after[:50]) if words_after else ""

                    # Generate natural language summary retaining exact figures and context
                    summary = self.table_summarizer.summarize(
                        table_markdown=raw_table,
                        document_title=doc_title,
                        section_title=section_path,
                        source_url=source_url,
                        intro_text=text_before,
                        table_notes=table_notes,
                    )

                    chunk_text = (
                        f"{breadcrumb}\n\n"
                        f"### Table Summary: {summary.title}\n"
                        f"{summary.summary}"
                    )

                    chunk_meta = {
                        "chunk_id": f"page_{page_id}_table_{chunk_counter}",
                        "page_id": page_id,
                        "document_title": doc_title,
                        "source_url": source_url,
                        "page_type": page_type,
                        "section_path": section_path,
                        "is_table": True,
                        "raw_table": summary.raw_table,
                        "key_figures": summary.key_figures,
                        **chunk_headers,
                    }
                    final_chunks.append(Document(page_content=chunk_text, metadata=chunk_meta))

                # Remove tables from text to process the remaining prose
                content = TABLE_REGEX.sub("", content).strip()
                if not content:
                    continue

            # Process non-table text
            if len(content) > self.target_chunk_size:
                sub_texts = self.sub_splitter.split_text(content)
                for sub_text in sub_texts:
                    chunk_counter += 1
                    full_chunk_text = f"{breadcrumb}\n\n{sub_text}"
                    chunk_meta = {
                        "chunk_id": f"page_{page_id}_chunk_{chunk_counter}",
                        "page_id": page_id,
                        "document_title": doc_title,
                        "source_url": source_url,
                        "page_type": page_type,
                        "section_path": section_path,
                        "is_table": False,
                        "raw_table": None,
                        "key_figures": {},
                        **chunk_headers,
                    }
                    final_chunks.append(Document(page_content=full_chunk_text, metadata=chunk_meta))
            else:
                chunk_counter += 1
                full_chunk_text = f"{breadcrumb}\n\n{content}"
                chunk_meta = {
                    "chunk_id": f"page_{page_id}_chunk_{chunk_counter}",
                    "page_id": page_id,
                    "document_title": doc_title,
                    "source_url": source_url,
                    "page_type": page_type,
                    "section_path": section_path,
                    "is_table": False,
                    "raw_table": None,
                    "key_figures": {},
                    **chunk_headers,
                }
                final_chunks.append(Document(page_content=full_chunk_text, metadata=chunk_meta))

        logger.debug(
            "Chunked document '%s' (id=%s) into %d chunks.",
            doc_title,
            page_id,
            len(final_chunks),
        )
        return final_chunks

    def chunk_all(
        self,
        markdown_files: Optional[List[Path]] = None,
    ) -> List[Document]:
        """
        Chunk all markdown files in the knowledge base (data/markdown/)
        matching them with their authorized metadata.
        """
        target_files = markdown_files or sorted(settings.MARKDOWN_DIR.glob("page_*.md"))
        url_metadata_by_id = {item["id"]: item for item in AUTHORIZED_URLS}

        all_chunks: List[Document] = []
        for file_path in target_files:
            # Extract page id from filename (e.g. page_2_package_7903... -> 2)
            match = re.match(r"^page_(\d+)_", file_path.name)
            page_id = int(match.group(1)) if match else 0
            metadata = url_metadata_by_id.get(page_id, {
                "id": page_id,
                "title": file_path.stem,
                "url": "",
                "page_type": "Medical Document",
            })

            text = file_path.read_text(encoding="utf-8")
            chunks = self.chunk_document(markdown_text=text, metadata=metadata)
            all_chunks.extend(chunks)

        logger.info(
            "Total knowledge base chunking complete: %d chunks generated across %d markdown documents.",
            len(all_chunks),
            len(target_files),
        )
        return all_chunks

    # Backward-compatible alias
    chunk_markdown = chunk_document


# Alias for backward and forward compatibility
HeaderAwareChunker = ChunkingService