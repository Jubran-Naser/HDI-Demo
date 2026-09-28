"""Engine-slot configuration.

The model runtime is a *swappable slot*: base URL, model name and key all come from
the environment, so OMLX / Ollama / LM Studio are interchangeable behind one
OpenAI-compatible interface. Nothing about the runtime is hardcoded in the pipeline.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Default: Ollama's OpenAI-compatible endpoint (cross-platform, easy for reviewers).
    engine_base_url: str = "http://localhost:11434/v1"
    engine_model: str = "qwen3.5:4b"
    engine_api_key: str = "ollama"  # Ollama ignores the key, but the client requires one


settings = Settings()
