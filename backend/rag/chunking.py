"""
Text chunking strategies for the RAG ingestion pipeline.
"""
import re
from typing import List
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    metadata: dict


def chunk_by_sentences(
    text: str,
    chunk_size: int = 300,
    overlap: int = 50,
    metadata: dict = None,
) -> List[Chunk]:
    """
    Split text into overlapping sentence-level chunks.

    Args:
        text: Input document text.
        chunk_size: Target character count per chunk.
        overlap: Character overlap between consecutive chunks.
        metadata: Base metadata to attach to every chunk.
    """
    meta = metadata or {}
    # Sentence boundaries: period / ! / ? / Devanagari danda
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())

    chunks: List[Chunk] = []
    buffer = ""
    for sentence in sentences:
        if len(buffer) + len(sentence) > chunk_size and buffer:
            chunks.append(Chunk(text=buffer.strip(), metadata={**meta}))
            # Keep last `overlap` characters as context
            buffer = buffer[-overlap:] + " " + sentence
        else:
            buffer += (" " if buffer else "") + sentence

    if buffer.strip():
        chunks.append(Chunk(text=buffer.strip(), metadata={**meta}))

    return chunks


def chunk_by_paragraphs(
    text: str,
    max_chunk_size: int = 500,
    metadata: dict = None,
) -> List[Chunk]:
    """
    Split text at paragraph boundaries, then further split large paragraphs.
    """
    meta = metadata or {}
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks: List[Chunk] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chunk_size:
            chunks.append(Chunk(text=para, metadata={**meta}))
        else:
            sub = chunk_by_sentences(para, chunk_size=max_chunk_size, metadata=meta)
            chunks.extend(sub)
    return chunks
