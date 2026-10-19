"""Model providers for the AI features.

Use `get_llm()` / `get_embedder()` everywhere; tests and the eval script swap
in fakes with `set_providers()`.
"""

from app.ai.base import EmbeddingProvider, LLMProvider
from app.ai.openai_compat import OpenAICompatEmbedder, OpenAICompatLLM
from app.core.config import settings
from app.models.embedding import VECTOR_DIM

_llm: LLMProvider | None = None
_embedder: EmbeddingProvider | None = None


def get_llm() -> LLMProvider:
    global _llm
    if _llm is None:
        _llm = OpenAICompatLLM(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            timeout=settings.LLM_TIMEOUT_S,
        )
    return _llm


def get_embedder() -> EmbeddingProvider:
    global _embedder
    if _embedder is None:
        _embedder = OpenAICompatEmbedder(
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
            model=settings.EMBEDDING_MODEL,
            dim=VECTOR_DIM,
            query_prefix=settings.EMBEDDING_QUERY_PREFIX,
            doc_prefix=settings.EMBEDDING_DOC_PREFIX,
            min_similarity=settings.EMBEDDING_MIN_SIMILARITY,
        )
    return _embedder


def set_providers(
    llm: LLMProvider | None = None, embedder: EmbeddingProvider | None = None
) -> None:
    """Replace the providers (None resets to the configured ones)."""
    global _llm, _embedder
    _llm, _embedder = llm, embedder
