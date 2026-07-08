"""Configuration loader for AI Baby Songs."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
TEMP_DIR = PROJECT_ROOT / "temp"
OUTPUT_DIR = PROJECT_ROOT / "output"


class Config:
    """Application configuration loaded from config.yaml and environment variables."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(PROJECT_ROOT / "config.yaml")

        self._config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}

        # Ensure directories exist
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def project_root(self) -> Path:
        """Project root directory."""
        return PROJECT_ROOT

    @property
    def temp_dir(self) -> Path:
        """Temporary files directory."""
        return TEMP_DIR

    @property
    def output_dir(self) -> Path:
        """Output files directory."""
        return OUTPUT_DIR

    @property
    def channel(self) -> dict:
        """Channel configuration."""
        return self._config.get("channel", {})

    @property
    def schedule(self) -> dict:
        """Schedule configuration."""
        return self._config.get("schedule", {})

    @property
    def songs(self) -> dict:
        """Songs configuration."""
        return self._config.get("songs", {})

    @property
    def voice(self) -> dict:
        """Voice/TTS configuration."""
        return self._config.get("voice", {})

    @property
    def music(self) -> dict:
        """Music generation configuration."""
        return self._config.get("music", {})

    @property
    def video(self) -> dict:
        """Video generation configuration."""
        return self._config.get("video", {})

    @property
    def youtube(self) -> dict:
        """YouTube upload configuration."""
        return self._config.get("youtube", {})

    @property
    def ai(self) -> dict:
        """AI/LLM configuration."""
        return self._config.get("ai", {})

    @property
    def output(self) -> dict:
        """Output configuration."""
        return self._config.get("output", {})

    # API Keys from environment variables
    @property
    def openai_api_key(self) -> str:
        """OpenAI API key from environment."""
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def youtube_client_id(self) -> str:
        """YouTube OAuth client ID from environment."""
        return os.getenv("YOUTUBE_CLIENT_ID", "")

    @property
    def youtube_client_secret(self) -> str:
        """YouTube OAuth client secret from environment."""
        return os.getenv("YOUTUBE_CLIENT_SECRET", "")

    @property
    def youtube_refresh_token(self) -> str:
        """YouTube OAuth refresh token from environment."""
        return os.getenv("YOUTUBE_REFRESH_TOKEN", "")


# Singleton instance
_config_instance = None


def get_config(config_path: str = None) -> Config:
    """Get the singleton Config instance.

    Args:
        config_path: Optional path to config.yaml. Only used on first call.

    Returns:
        Config singleton instance.
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance
