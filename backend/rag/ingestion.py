"""
Document ingestion pipeline.
Supports PDF, images (OCR), CSV, Excel, JSON, and plain text.
Extracts text → chunks → embeds → stores in vector DB.
"""
import io
import json
import logging
import uuid
import csv
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# ─── Text extractors ──────────────────────────────────────────────────────────

def extract_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file."""
    try:
        import pdfplumber
        text_parts: List[str] = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""


def extract_image_ocr(file_bytes: bytes) -> str:
    """Extract text from an image using pytesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(file_bytes))
        return pytesseract.image_to_string(img, lang="eng+hin")
    except Exception as e:
        logger.error(f"OCR extraction error: {e}")
        return ""


def extract_csv(file_bytes: bytes) -> str:
    """Convert CSV to human-readable text."""
    try:
        text = file_bytes.decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        lines: List[str] = []
        for row in reader:
            parts = [f"{k}: {v}" for k, v in row.items() if v]
            lines.append(", ".join(parts))
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"CSV extraction error: {e}")
        return ""


def extract_excel(file_bytes: bytes) -> str:
    """Convert Excel spreadsheet to text."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        parts: List[str] = []
        for sheet in wb.worksheets:
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                continue
            headers = [str(h) if h is not None else "" for h in rows[0]]
            for row in rows[1:]:
                row_parts = [
                    f"{h}: {v}"
                    for h, v in zip(headers, row)
                    if v is not None
                ]
                parts.append(", ".join(row_parts))
        return "\n".join(parts)
    except Exception as e:
        logger.error(f"Excel extraction error: {e}")
        return ""


def extract_json(file_bytes: bytes) -> str:
    """Convert JSON to readable text."""
    try:
        data = json.loads(file_bytes.decode("utf-8"))
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"JSON extraction error: {e}")
        return ""


# ─── Dispatcher ───────────────────────────────────────────────────────────────

EXTRACTORS = {
    "pdf": extract_pdf,
    "png": extract_image_ocr,
    "jpg": extract_image_ocr,
    "jpeg": extract_image_ocr,
    "webp": extract_image_ocr,
    "csv": extract_csv,
    "xlsx": extract_excel,
    "xls": extract_excel,
    "json": extract_json,
}


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Route file bytes to the correct extractor based on extension."""
    ext = filename.rsplit(".", 1)[-1].lower()
    extractor = EXTRACTORS.get(ext)
    if extractor is None:
        logger.warning(f"No extractor for extension .{ext}; treating as plain text.")
        return file_bytes.decode("utf-8", errors="ignore")
    return extractor(file_bytes)


# ─── Full ingestion pipeline ──────────────────────────────────────────────────

async def ingest_document(
    file_bytes: bytes,
    filename: str,
    source_type: str = "document",
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Full ingestion: extract → chunk → embed → store.

    Returns:
        Number of chunks successfully ingested.
    """
    from backend.rag.chunking import chunk_by_paragraphs
    from backend.rag.embeddings import embedding_service
    from backend.rag.vector_store import vector_store

    text = extract_text(file_bytes, filename)
    if not text.strip():
        logger.warning(f"No text extracted from {filename}.")
        return 0

    base_metadata: Dict[str, Any] = {
        "source": filename,
        "source_type": source_type,
        **(extra_metadata or {}),
    }
    chunks = chunk_by_paragraphs(text, metadata=base_metadata)
    if not chunks:
        return 0

    texts = [c.text for c in chunks]
    metadatas = [c.metadata for c in chunks]
    ids = [f"{filename}_{i}_{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]
    embeddings = embedding_service.embed_batch(texts)

    vector_store.add_documents(
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )
    logger.info(f"Ingested {len(chunks)} chunks from {filename!r}.")
    return len(chunks)


async def ingest_menu_item_text(
    item_id: str,
    name: str,
    description: str,
    category: str,
    ingredients: List[str],
    dietary_tags: List[str],
) -> None:
    """
    Build a rich text document for a menu item and add it to the vector store.
    Called whenever a menu item is created or updated.
    """
    from backend.rag.embeddings import embedding_service
    from backend.rag.vector_store import vector_store

    text = (
        f"Item: {name}. "
        f"Category: {category}. "
        f"Description: {description or 'N/A'}. "
        f"Ingredients: {', '.join(ingredients) or 'N/A'}. "
        f"Dietary info: {', '.join(dietary_tags) or 'N/A'}."
    )
    metadata = {
        "source": "menu_item",
        "source_type": "menu",
        "item_id": item_id,
        "name": name,
        "category": category,
    }
    doc_id = f"menu_item_{item_id}"

    # Remove existing entry before re-adding
    try:
        vector_store.delete_by_ids([doc_id])
    except Exception:
        pass

    embedding = embedding_service.embed(text)
    vector_store.add_documents(
        documents=[text],
        embeddings=[embedding],
        metadatas=[metadata],
        ids=[doc_id],
    )
