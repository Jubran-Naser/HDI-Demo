"""Settings for the model server, the AI model it runs, and the database for the audit records.

Names used here: this file = config.py · `Settings` = the list of settings with their
defaults · `settings` = the values in use (defaults, overridden by environment variables
or a .env file). To change a value, set e.g. AI_MODEL=... — no code change needed.

The model server is swappable: any server speaking the OpenAI-compatible protocol
works by changing these values. Nothing about the model server is hardcoded elsewhere.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Default: Ollama (runs on macOS, Linux and Windows — easy for reviewers).
    model_server_url: str = "http://localhost:11434/v1"
    ai_model: str = "qwen3.5:4b"
    model_server_api_key: str = "ollama"  # Ollama ignores the key, but the driver requires one

    # Extra options sent with every request to the model server. Here: switch the AI
    # model's thinking off (Ollama's spelling). Another model server spells this differently,
    # so swapping the model server means changing this setting too.
    model_server_extra_body: dict = {"reasoning_effort": "none"}

    # How long to wait for the AI model's answer before giving up; the claim then goes to a person.
    model_server_timeout_seconds: float = 60

    # Where the audit records are stored. Default: a SQLite file next to where the service starts
    # (no database server needed). PostgreSQL later: set DATABASE_URL, no code change.
    database_url: str = "sqlite:///audit.db"


settings = Settings()
