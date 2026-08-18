"""
High-level RAG service facade used by the FastAPI app.
"""
from backend.rag.retrieval import rag_service
from backend.rag.ingestion import ingest_document, ingest_menu_item_text
from backend.rag.vector_store import vector_store

__all__ = ["rag_service", "ingest_document", "ingest_menu_item_text", "vector_store"]
