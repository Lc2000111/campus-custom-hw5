"""The one LLM every agent uses: gpt-5.6-luna through Portkey."""

import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from backend.config import MODEL_NAME, MODEL_TIMEOUT_S, PORTKEY_BASE_URL, ROOT

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


def build_model() -> OpenAIResponsesModel:
    # .env lives in hw5/ or the class folder above it; never printed or logged.
    for env_path in (ROOT / ".env", ROOT.parent / ".env"):
        if env_path.exists():
            load_dotenv(env_path)
            break
    key = os.environ["PORTKEY_API_KEY"]
    client = AsyncOpenAI(
        api_key=key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": key},
        timeout=MODEL_TIMEOUT_S,  # a stalled gateway call fails fast instead of freezing the run
        max_retries=2,
    )
    return OpenAIResponsesModel(
        MODEL_NAME,
        provider=OpenAIProvider(openai_client=client),
        settings=OpenAIResponsesModelSettings(openai_reasoning_effort="low"),
    )
