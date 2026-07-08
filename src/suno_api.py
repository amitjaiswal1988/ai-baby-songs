"""
Suno AI API Integration via Evolink
Generates high-quality singing audio from lyrics automatically.
"""
import logging
import os
import time
import requests
from pathlib import Path
from typing import Optional

from .config import get_config

logger = logging.getLogger(__name__)

EVOLINK_BASE_URL = "https://api.evolink.ai/v1"


class SunoAPI:
    """Generates singing audio using Suno AI via Evolink API."""

    def __init__(self):
        self.config = get_config()
        self.api_key = os.getenv("EVOLINK_API_KEY", "")
        self.base_url = os.getenv("EVOLINK_BASE_URL", EVOLINK_BASE_URL)
        self.model = "suno-v4.5-beta"

    def generate_song(
        self,
        lyrics: str,
        title: str = "Baby Song",
        style: str = None,
        instrumental: bool = False,
    ) -> Optional[str]:
        """
        Generate a singing song from lyrics using Suno AI.

        Args:
            lyrics: Song lyrics with [Verse], [Chorus] markers.
            title: Song title.
            style: Music style description. Auto-generated if None.
            instrumental: If True, generate without vocals.

        Returns:
            Path to downloaded MP3 file, or None on failure.
        """
        if not self.api_key:
            logger.error("EVOLINK_API_KEY not set in .env file!")
            return None

        if style is None:
            style = "hindi children's nursery rhyme, cute little girl singing, happy bouncy, upbeat, xylophone, ukulele, hand claps, Bollywood kids style"

        logger.info(f"Generating song with Suno AI: {title}")
        logger.info(f"  Style: {style[:60]}...")
        logger.info(f"  Lyrics: {len(lyrics)} chars")

        # Submit generation request
        task_id = self._submit_task(lyrics, title, style, instrumental)
        if not task_id:
            return None

        # Poll for completion
        audio_url = self._wait_for_completion(task_id)
        if not audio_url:
            return None

        # Download the MP3
        output_path = self._download_audio(audio_url, title)
        return output_path

    def _submit_task(
        self, lyrics: str, title: str, style: str, instrumental: bool
    ) -> Optional[str]:
        """Submit a song generation task to Suno via Evolink."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "prompt": style,
            "lyrics": lyrics,
            "title": title,
            "instrumental": instrumental,
            "custom_mode": True,
        }

        try:
            response = requests.post(
                f"{self.base_url}/audios/generations",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            task_id = data.get("id") or data.get("task_id") or data.get("data", {}).get("task_id")
            if task_id:
                logger.info(f"  Task submitted: {task_id}")
                return task_id
            else:
                logger.error(f"  No task_id in response: {data}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"  Suno API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"  Response: {e.response.text[:500]}")
            return None

    def _wait_for_completion(self, task_id: str, timeout: int = 300) -> Optional[str]:
        """Poll task status until completion."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        start_time = time.time()
        poll_interval = 5  # seconds

        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    f"{self.base_url}/tasks/{task_id}",
                    headers=headers,
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()

                status = data.get("status", "")
                status_lower = status.lower() if status else ""

                if status_lower in ("completed", "succeeded", "success", "done"):
                    # Extract audio URL from result_data
                    result_data = data.get("result_data") or data.get("output") or data.get("data", {}).get("output", {})

                    audio_url = None
                    if isinstance(result_data, list) and result_data:
                        # Evolink returns list of generated songs
                        audio_url = result_data[0].get("audio_url") or result_data[0].get("url")
                    elif isinstance(result_data, dict):
                        audio_url = (
                            result_data.get("audio_url")
                            or result_data.get("url")
                            or result_data.get("music_url")
                        )
                        songs = result_data.get("songs") or result_data.get("clips") or []
                        if songs and isinstance(songs, list):
                            audio_url = songs[0].get("audio_url") or songs[0].get("url")
                    elif isinstance(result_data, str):
                        audio_url = result_data

                    if audio_url:
                        logger.info(f"  Song generated successfully!")
                        return audio_url
                    else:
                        logger.error(f"  No audio URL in output: {data}")
                        return None

                elif status_lower in ("failed", "error"):
                    error_msg = data.get("error") or data.get("message", "Unknown error")
                    logger.error(f"  Generation failed: {error_msg}")
                    return None

                else:
                    elapsed = int(time.time() - start_time)
                    logger.info(f"  Status: {status} ({elapsed}s elapsed)...")

            except requests.exceptions.RequestException as e:
                logger.warning(f"  Poll error: {e}")

            time.sleep(poll_interval)

        logger.error(f"  Timeout after {timeout}s")
        return None

    def _download_audio(self, audio_url: str, title: str) -> Optional[str]:
        """Download the generated audio file."""
        try:
            response = requests.get(audio_url, timeout=60)
            response.raise_for_status()

            # Save to input folder
            input_dir = self.config.project_root / "input"
            input_dir.mkdir(parents=True, exist_ok=True)

            safe_title = title.replace(" ", "_").lower()[:30]
            output_path = str(input_dir / f"{safe_title}.mp3")

            with open(output_path, "wb") as f:
                f.write(response.content)

            file_size = os.path.getsize(output_path) / 1024
            logger.info(f"  Audio downloaded: {output_path} ({file_size:.0f} KB)")
            return output_path

        except Exception as e:
            logger.error(f"  Download failed: {e}")
            return None
