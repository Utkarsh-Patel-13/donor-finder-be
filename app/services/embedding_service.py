"""Embedding service for generating and managing vector embeddings."""

import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating semantic embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize embedding service with specified model."""
        self.model_name = model_name
        self.model = None
        self.embedding_dimension = 384  # Dimension for all-MiniLM-L6-v2

    def _load_model(self):
        """Lazy load the sentence transformer model."""
        if self.model is None:
            try:
                logger.info(f"Loading embedding model: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.embedding_dimension

        self._load_model()

        try:
            # Generate embedding
            embedding = self.model.encode(text.strip())

            # Convert numpy array to list and ensure it's the right dimension
            embedding_list = embedding.tolist()

            if len(embedding_list) != self.embedding_dimension:
                logger.warning(
                    f"Embedding dimension mismatch: expected {self.embedding_dimension}, got {len(embedding_list)}"
                )

            return embedding_list

        except Exception as e:
            logger.error(f"Failed to generate embedding for text: {e}")
            # Return zero vector on error
            return [0.0] * self.embedding_dimension

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently."""
        if not texts:
            return []

        self._load_model()

        try:
            # Filter out empty texts and keep track of original indices
            valid_texts = []
            valid_indices = []

            for i, text in enumerate(texts):
                if text and text.strip():
                    valid_texts.append(text.strip())
                    valid_indices.append(i)

            if not valid_texts:
                # All texts were empty, return zero vectors
                return [[0.0] * self.embedding_dimension] * len(texts)

            # Generate embeddings for valid texts
            embeddings = self.model.encode(valid_texts)

            # Create result array with zero vectors for empty texts
            result = [[0.0] * self.embedding_dimension] * len(texts)

            # Fill in the valid embeddings
            for i, embedding in enumerate(embeddings):
                original_index = valid_indices[i]
                result[original_index] = embedding.tolist()

            return result

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            # Return zero vectors for all texts on error
            return [[0.0] * self.embedding_dimension] * len(texts)

    def compute_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            # Compute cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            # Use numpy.isclose for safe float comparison
            if np.isclose(norm1, 0.0) or np.isclose(norm2, 0.0):
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            return float(similarity)

        except Exception as e:
            logger.error(f"Failed to compute similarity: {e}")
            return 0.0

    def find_similar_embeddings(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        top_k: int = 10,
    ) -> List[tuple]:
        """Find the most similar embeddings to a query embedding.

        Returns:
            List of (index, similarity_score) tuples sorted by similarity (highest first)
        """
        similarities = []

        for i, candidate_embedding in enumerate(candidate_embeddings):
            similarity = self.compute_similarity(query_embedding, candidate_embedding)
            similarities.append((i, similarity))

        # Sort by similarity score (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Get singleton embedding service instance."""
    return EmbeddingService()
