from typing import List, Optional
import numpy as np
from backend.app.core.logging import logger

class EmbeddingEngine:
    """
    Local CPU embedding generator using Hugging Face's sentence-transformers.
    100% free, zero external API calls, running on CPU.
    """

    _instance: Optional["EmbeddingEngine"] = None
    _model = None

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", use_mock: bool = False):
        self.model_name = model_name
        self.dim = 384
        self.use_mock = use_mock

        if not self.use_mock and EmbeddingEngine._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading local embedding model: {self.model_name} on CPU...")
                EmbeddingEngine._model = SentenceTransformer(self.model_name, device="cpu")
                logger.info("Local embedding model loaded successfully.")
            except Exception as e:
                logger.warning(f"Failed to load SentenceTransformer ({e}). Falling back to mock embeddings.")
                self.use_mock = True

    def embed_text(self, text: str) -> List[float]:
        """Generate 384-dim normalized embedding vector for a single text."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate 384-dim normalized embedding vectors for a batch of texts."""
        if not texts:
            return []

        if self.use_mock or EmbeddingEngine._model is None:
            # Deterministic, non-zero mock embeddings based on text hash for fast unit tests
            embeddings = []
            for t in texts:
                np.random.seed(abs(hash(t)) % (2**32))
                vec = np.random.randn(self.dim).astype(np.float32)
                norm = np.linalg.norm(vec)
                norm_vec = (vec / norm).tolist() if norm > 0 else vec.tolist()
                embeddings.append(norm_vec)
            return embeddings

        vectors = EmbeddingEngine._model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vectors.tolist()


def get_embedding_engine(use_mock: bool = False) -> EmbeddingEngine:
    return EmbeddingEngine(use_mock=use_mock)

