from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from utils.config import get_settings

load_dotenv()


@lru_cache(maxsize=8)
def llm_pick(model_level: str):

    """
    Pick a LLM model based on the provided level.

    low    -> cheap & fast model (question curation, intent classification)
    medium -> balanced model (SQL generation, final answer)
    high   -> strongest model (SQL self-correction after a failed attempt)

    Instances are cached so the HTTP client / connection pool is reused across requests.

    Args:
        model_level (str): The level of the model to use.

    Returns:
        An instance of the selected LLM model.
    """
    settings = get_settings()
    models = {
        "low": settings.llm_model_low,
        "medium": settings.llm_model_medium,
        "high": settings.llm_model_high,
    }

    level = model_level.lower()
    if level not in models:
        raise ValueError(f"Invalid model level: {model_level}. Choose from 'low', 'medium', or 'high'.")

    return ChatOpenAI(
        model_name=models[level],
        api_key=settings.openai_api_key or None,
        temperature=0,
        timeout=settings.llm_timeout_seconds,
        max_retries=2,
    )


if __name__ == "__main__":
    llm_obj = llm_pick("medium")
    print(llm_obj.invoke("What is Agentic AI?"))
