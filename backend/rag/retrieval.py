"""
RAG retrieval service.
Accepts a natural-language query and returns the most relevant context chunks.
"""
import logging
from typing import List, Dict, Any, Optional
from backend.rag.embeddings import embedding_service
from backend.rag.vector_store import vector_store

logger = logging.getLogger(__name__)


class RAGService:
    """Semantic retrieval over the restaurant knowledge base."""

    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        source_type_filter: Optional[str] = None,
        max_distance: float = 0.75,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context for a given query.

        Args:
            query: Natural language question or utterance.
            n_results: Maximum number of results to return.
            source_type_filter: Optionally filter by source_type metadata.
            max_distance: Cosine distance threshold (lower = more similar).

        Returns:
            List of result dicts with 'document', 'metadata', 'distance'.
        """
        query_embedding = embedding_service.embed(query)
        where = {"source_type": source_type_filter} if source_type_filter else None
        results = vector_store.query(
            query_embedding=query_embedding,
            n_results=n_results,
            where=where,
        )
        # Filter by distance threshold
        filtered = [r for r in results if r["distance"] <= max_distance]
        logger.debug(f"RAG retrieved {len(filtered)}/{len(results)} results for query: {query!r}")
        return filtered

    def format_context(self, results: List[Dict[str, Any]]) -> str:
        """
        Format retrieval results into a context string for the LLM prompt.
        """
        if not results:
            return "No relevant restaurant knowledge found."
        parts = []
        for i, r in enumerate(results, 1):
            meta = r.get("metadata", {})
            source = meta.get("source", "unknown")
            parts.append(f"[{i}] (source: {source})\n{r['document']}")
        return "\n\n".join(parts)

    def retrieve_formatted(
        self,
        query: str,
        n_results: int = 5,
        source_type_filter: Optional[str] = None,
    ) -> str:
        """Convenience: retrieve + format in one call."""
        results = self.retrieve(query, n_results, source_type_filter)
        return self.format_context(results)


# Singleton
rag_service = RAGService()
