"""
Magic Docs service — document ingestion, summarisation, and Q&A support.

Ports: services/MagicDocs/magicDocs.ts, services/MagicDocs/prompts.ts
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Document model
# ---------------------------------------------------------------------------

@dataclass
class DocChunk:
    """A section of a document with metadata."""
    content: str
    chunk_index: int
    char_start: int
    char_end: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        return len(self.content) // 4


@dataclass
class MagicDoc:
    """
    Represents an ingested document ready for context injection.

    Ports: MagicDocs document object model.
    """
    doc_id: str
    title: str
    content: str
    source: str = ""           # file path or URL
    mime_type: str = "text/plain"
    ingested_at: float = field(default_factory=time.time)
    chunks: list[DocChunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        return len(self.content) // 4

    def to_context_block(self, max_chars: int | None = None) -> str:
        """Render the document as a context block for injection into prompts."""
        body = self.content
        if max_chars and len(body) > max_chars:
            body = body[:max_chars] + "\n...[truncated]"
        return (
            f"<document id={self.doc_id!r} title={self.title!r}>\n"
            f"{body}\n"
            f"</document>"
        )


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = 4000,
    overlap: int = 200,
) -> list[DocChunk]:
    """
    Split *text* into overlapping chunks for retrieval or context windows.

    Uses paragraph breaks when possible, otherwise hard-splits at chunk_size.
    """
    if not text:
        return []

    # Split on double newlines first
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[DocChunk] = []
    current = ""
    current_start = 0
    char_pos = 0

    for para in paragraphs:
        if len(current) + len(para) + 2 > chunk_size and current:
            chunk_end = current_start + len(current)
            chunks.append(
                DocChunk(
                    content=current.strip(),
                    chunk_index=len(chunks),
                    char_start=current_start,
                    char_end=chunk_end,
                )
            )
            # Overlap: carry forward last `overlap` chars
            current = current[-overlap:] + "\n\n" + para if overlap else para
            current_start = chunk_end - overlap if overlap else chunk_end
        else:
            current = (current + "\n\n" + para).lstrip() if current else para
        char_pos += len(para) + 2  # +2 for the double newline

    if current:
        chunks.append(
            DocChunk(
                content=current.strip(),
                chunk_index=len(chunks),
                char_start=current_start,
                char_end=current_start + len(current),
            )
        )

    return chunks


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SUMMARISE_PROMPT = """You are summarising a document for use as context.
Produce a concise but complete summary that preserves:
- Key facts, figures, and named entities
- Main conclusions or recommendations
- Any code snippets or technical specifications

Document title: {title}

Document content:
{content}

Write the summary below:"""

QA_PROMPT = """You have access to the following document:

{doc_context}

Answer the user's question based only on the document above.
If the answer is not in the document, say so clearly.

Question: {question}"""


def build_summarise_prompt(doc: MagicDoc, max_content_chars: int = 20_000) -> str:
    content = doc.content[:max_content_chars]
    if len(doc.content) > max_content_chars:
        content += "\n...[truncated for summarisation]"
    return SUMMARISE_PROMPT.format(title=doc.title, content=content)


def build_qa_prompt(doc: MagicDoc, question: str, max_chars: int = 16_000) -> str:
    ctx = doc.to_context_block(max_chars=max_chars)
    return QA_PROMPT.format(doc_context=ctx, question=question)


# ---------------------------------------------------------------------------
# Ingestion helpers
# ---------------------------------------------------------------------------

def _make_doc_id(source: str, content: str) -> str:
    digest = hashlib.sha256((source + content[:256]).encode()).hexdigest()[:12]
    return f"doc_{digest}"


def ingest_text(
    content: str,
    title: str = "Untitled",
    source: str = "",
    chunk_size: int = 4000,
    chunk_overlap: int = 200,
) -> MagicDoc:
    """Create a MagicDoc from a raw text string."""
    doc_id = _make_doc_id(source or title, content)
    chunks = chunk_text(content, chunk_size=chunk_size, overlap=chunk_overlap)
    return MagicDoc(
        doc_id=doc_id,
        title=title,
        content=content,
        source=source,
        chunks=chunks,
    )


def ingest_file(
    path: str | Path,
    chunk_size: int = 4000,
    chunk_overlap: int = 200,
) -> MagicDoc:
    """Create a MagicDoc from a local file."""
    p = Path(path)
    content = p.read_text(encoding="utf-8", errors="replace")
    return ingest_text(
        content=content,
        title=p.name,
        source=str(p),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


# ---------------------------------------------------------------------------
# Document store
# ---------------------------------------------------------------------------

class MagicDocStore:
    """
    In-process store for MagicDoc objects.

    For production use, back this with a vector DB or disk cache.
    """

    def __init__(self) -> None:
        self._docs: dict[str, MagicDoc] = {}

    def add(self, doc: MagicDoc) -> None:
        self._docs[doc.doc_id] = doc

    def get(self, doc_id: str) -> MagicDoc | None:
        return self._docs.get(doc_id)

    def remove(self, doc_id: str) -> bool:
        return self._docs.pop(doc_id, None) is not None

    def list_docs(self) -> list[MagicDoc]:
        return list(self._docs.values())

    def clear(self) -> None:
        self._docs.clear()

    def search_by_title(self, query: str) -> list[MagicDoc]:
        q = query.lower()
        return [d for d in self._docs.values() if q in d.title.lower()]

    def build_context(self, doc_ids: list[str], max_chars_each: int = 8000) -> str:
        """Build a combined context block for multiple docs."""
        blocks: list[str] = []
        for doc_id in doc_ids:
            doc = self.get(doc_id)
            if doc:
                blocks.append(doc.to_context_block(max_chars=max_chars_each))
        return "\n\n".join(blocks)


__all__ = [
    "DocChunk",
    "MagicDoc",
    "MagicDocStore",
    "build_qa_prompt",
    "build_summarise_prompt",
    "chunk_text",
    "ingest_file",
    "ingest_text",
]
