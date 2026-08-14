"""Every environment variable this application reads, in one typed object.

Importing this module calls `load_dotenv()`. That is deliberate and it is the only
place it happens: provider SDKs underneath LiteLLM (openai, google-genai) read their
API keys straight from `os.environ`, and `pydantic-settings`' own `env_file` support
populates the `Settings` object *without* touching `os.environ`. So we do both — the
dotenv load feeds the SDKs, the `Settings` fields feed our code.

Settings are read when `get_settings()` is first *called*, never at class-definition
time, which is what lets the crew module be imported freely at module scope.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

# <repo>/src/customer_support_crew/core/settings.py → <repo>
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Configuration for the crew, the Jira adapter, and where results are written."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # LiteLLM-style model strings. The split is deliberate: a cheap fast model for
    # triage, a stronger reasoning model for resolution.
    triage_model: str = "openai/gpt-4o-mini"
    triage_temperature: float = 0.2
    resolver_model: str = "gemini/gemini-2.0-flash"
    resolver_temperature: float = 0.5

    # Atlassian Cloud basic auth. Optional so the app still boots (and the test suite
    # still runs) without them; the Jira adapter reports the gap as tool output.
    jira_server_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[SecretStr] = None

    # Where `final_resolution__<KEY>.json` files land. A relative value is resolved
    # against the repository root, not the current working directory, so results go to
    # the same place no matter where the process was started from.
    output_dir: Path = Field(default=Path("output"))

    @property
    def resolved_output_dir(self) -> Path:
        if self.output_dir.is_absolute():
            return self.output_dir
        return PROJECT_ROOT / self.output_dir

    def has_jira_credentials(self) -> bool:
        return all([self.jira_server_url, self.jira_email, self.jira_api_token])


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings. Cached so `.env` is parsed once."""
    return Settings()
