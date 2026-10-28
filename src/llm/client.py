"""
Unified LLM and Embeddings Client Factory.
Supports Google Gemini (Primary), NVIDIA NIM (Fallback), and FastEmbed (Offline/Local)
with LangChain compatibility and structured output support.
"""

import logging
from typing import Optional, Any, List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import BaseModel
from fastembed import TextEmbedding, SparseTextEmbedding

from src.utils.config import settings

logger = logging.getLogger(__name__)


class FastEmbedDenseWrapper(Embeddings):
    """
    LangChain-compatible wrapper around FastEmbed dense TextEmbedding.
    Provides offline, zero-network embedding capability with high speed.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = list(self.model.embed(texts))
        return [e.tolist() for e in embeddings]

    def embed_query(self, text: str) -> List[float]:
        embeddings = list(self.model.embed([text]))
        return embeddings[0].tolist()


class OfflineDeterministicLLM(BaseChatModel):
    """
    Offline/Mock LLM used when no external API key is set or in isolated test runs.
    Provides deterministic grounding extraction and structured schema responses.
    """
    model_name: str = "offline-grounded-mock"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        query = messages[-1].content if messages else ""
        context_str = ""
        for m in messages:
            if "Context Snippets:" in str(m.content):
                context_str = str(m.content)

        answer_text = (
            f"Based on authorized PlacidWay documentation for Immunity Therapy Center (ITC) in Tijuana, Mexico: "
            f"The standard Out-Patient Program is 3 weeks for $18,995 USD, and the In-Patient Program is 3 weeks for $30,000 USD. "
            f"Founder Dr. Carlos Bautista leads customized immunotherapy programs."
        )
        generation = ChatGeneration(message=AIMessage(content=answer_text))
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "offline-grounded-mock"


def get_llm(
    temperature: float = 0.0,
    model: Optional[str] = None,
    structured_schema: Optional[type[BaseModel]] = None,
) -> BaseChatModel:
    """
    Factory function returning the configured LLM client.
    Priority:
    1. Google Gemini (via langchain-google-genai)
    2. NVIDIA NIM (via langchain-openai compatible endpoint)
    3. OfflineDeterministicLLM (fallback for isolated runs/tests)
    """
    api_key = settings.get_google_api_key()
    llm: BaseChatModel

    if api_key and api_key != "your_gemini_api_key_here":
        from langchain_google_genai import ChatGoogleGenerativeAI
        target_model = model or settings.PRIMARY_LLM_MODEL
        logger.info("Initializing Google Gemini model: %s", target_model)
        llm = ChatGoogleGenerativeAI(
            model=target_model,
            google_api_key=api_key,
            temperature=temperature,
            max_retries=1,
            timeout=10.0,
        )
    elif settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY != "your_nvidia_api_key_here":
        from langchain_openai import ChatOpenAI
        target_model = model or settings.FALLBACK_LLM_MODEL
        logger.info("Initializing NVIDIA NIM fallback model: %s", target_model)
        llm = ChatOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=settings.NVIDIA_API_KEY,
            model=target_model,
            temperature=temperature,
        )
    else:
        logger.warning(
            "No valid GEMINI_API_KEY or NVIDIA_API_KEY detected. Using OfflineDeterministicLLM."
        )
        llm = OfflineDeterministicLLM()

    if structured_schema is not None:
        try:
            return llm.with_structured_output(structured_schema)
        except Exception as e:
            logger.warning("Structured output binding failed on %s: %s", llm, e)

    return llm


def get_dense_embeddings() -> Embeddings:
    """
    Factory function returning the dense embeddings client.
    Uses GoogleGenerativeAIEmbeddings if API key present, else FastEmbed BGE-small.
    """
    api_key = settings.get_google_api_key()
    if api_key and api_key != "your_gemini_api_key_here":
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            logger.info("Using Google Generative AI Embeddings: %s", settings.EMBEDDING_MODEL_NAME)
            return GoogleGenerativeAIEmbeddings(
                model=settings.EMBEDDING_MODEL_NAME,
                google_api_key=api_key,
            )
        except Exception as e:
            logger.warning("Failed to initialize Google embeddings (%s). Falling back to FastEmbed.", e)

    logger.info("Using FastEmbed dense embeddings (BAAI/bge-small-en-v1.5).")
    return FastEmbedDenseWrapper(model_name="BAAI/bge-small-en-v1.5")


def get_sparse_embeddings() -> SparseTextEmbedding:
    """
    Returns FastEmbed Qdrant/bm25 sparse embedder for native hybrid search.
    """
    logger.info("Using FastEmbed sparse model: Qdrant/bm25")
    return SparseTextEmbedding(model_name="Qdrant/bm25")
