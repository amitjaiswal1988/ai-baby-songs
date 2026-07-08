"""
Kling AI API Integration via Evolink
Generates cartoon animation video clips for children's songs.
"""
import logging
import os
import time
import requests
from pathlib import Path
from typing import List, Optional

from .config import get_config

logger = logging.getLogger(__name__)

EVOLINK_BASE_URL = "https://api.evolink.ai/v1"


class KlingAPI:
    """Generates cartoon video clips using Kling AI via Evolink API."""

    def __init__(self):
        self.config = get_config()
        self.api_key = os.getenv("EVOLINK_API_KEY", "")
        self.base_url = os.getenv("EVOLINK_BASE_URL", EVOLINK_BASE_URL)
        self.model = "kling-v3"

    def generate_video_clip(
        self,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "16:9",
    ) -> Optional[str]:
        """
        Generate a single cartoon video clip.

        Args:
            prompt: Description of what to show in the video.
            duration: Clip duration in seconds (5 or 10).
            aspect_ratio: "16:9" for YouTube.

        Returns:
            Path to downloaded video file, or None on failure.
        """
        if not self.api_key:
            logger.error("EVOLINK_API_KEY not set!")
            return None

        logger.info(f"Generating video clip: {prompt[:60]}...")

        # Submit task
        task_id = self._submit_task(prompt, duration, aspect_ratio)
        if not task_id:
            return None

        # Wait for completion
        video_url = self._wait_for_completion(task_id)
        if not video_url:
            return None

        # Download video
        output_path = self._download_video(video_url, prompt)
        return output_path

    def generate_scene_clips(
        self,
        scenes: List[str],
        duration_per_clip: int = 5,
    ) -> List[str]:
        """
        Generate multiple video clips for song scenes.

        Args:
            scenes: List of scene descriptions/prompts.
            duration_per_clip: Duration per clip in seconds.

        Returns:
            List of paths to downloaded video clips.
        """
        logger.info(f"Generating {len(scenes)} scene clips...")
        clips = []

        for i, scene_prompt in enumerate(scenes):
            logger.info(f"  Scene {i+1}/{len(scenes)}: {scene_prompt[:50]}...")
            clip_path = self.generate_video_clip(
                prompt=scene_prompt,
                duration=duration_per_clip,
            )
            if clip_path:
                clips.append(clip_path)
            else:
                logger.warning(f"  Scene {i+1} failed, skipping")

            # Small delay between requests
            if i < len(scenes) - 1:
                time.sleep(2)

        logger.info(f"Generated {len(clips)}/{len(scenes)} clips successfully")
        return clips

    def _submit_task(self, prompt: str, duration: int, aspect_ratio: str) -> Optional[str]:
        """Submit video generation task."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Add kids-friendly style to prompt
        full_prompt = (
            f"{prompt}, "
            f"3D Pixar style cartoon animation, bright colorful, "
            f"cute characters, children's nursery rhyme scene, "
            f"kid-friendly, smooth animation, high quality"
        )

        payload = {
            "model": self.model,
            "task_type": "video_generation",
            "input": {
                "prompt": full_prompt,
                "duration": str(duration),
                "aspect_ratio": aspect_ratio,
                "mode": "standard",
            },
        }

        try:
            response = requests.post(
                f"{self.base_url}/tasks",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            task_id = data.get("task_id") or data.get("id") or data.get("data", {}).get("task_id")
            if task_id:
                logger.info(f"  Task submitted: {task_id}")
                return task_id
            else:
                logger.error(f"  No task_id: {data}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"  Kling API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"  Response: {e.response.text[:500]}")
            return None

    def _wait_for_completion(self, task_id: str, timeout: int = 600) -> Optional[str]:
        """Poll until video is ready (Kling takes longer than Suno)."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        start_time = time.time()
        poll_interval = 10  # Kling is slower

        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    f"{self.base_url}/tasks/{task_id}",
                    headers=headers,
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()

                status = data.get("status") or data.get("data", {}).get("status", "")
                status_lower = status.lower() if status else ""

                if status_lower in ("completed", "succeeded", "success", "done"):
                    output = data.get("output") or data.get("data", {}).get("output", {})
                    video_url = None

                    if isinstance(output, dict):
                        video_url = (
                            output.get("video_url")
                            or output.get("url")
                            or output.get("video")
                        )
                        videos = output.get("videos") or output.get("clips") or []
                        if videos and isinstance(videos, list):
                            video_url = videos[0].get("url") or videos[0].get("video_url")
                    elif isinstance(output, str):
                        video_url = output

                    if video_url:
                        logger.info(f"  Video generated!")
                        return video_url
                    else:
                        logger.error(f"  No video URL: {output}")
                        return None

                elif status_lower in ("failed", "error"):
                    logger.error(f"  Generation failed: {data.get('error', 'Unknown')}")
                    return None
                else:
                    elapsed = int(time.time() - start_time)
                    logger.info(f"  Status: {status} ({elapsed}s)...")

            except requests.exceptions.RequestException as e:
                logger.warning(f"  Poll error: {e}")

            time.sleep(poll_interval)

        logger.error(f"  Timeout after {timeout}s")
        return None

    def _download_video(self, video_url: str, prompt: str) -> Optional[str]:
        """Download generated video clip."""
        try:
            response = requests.get(video_url, timeout=120)
            response.raise_for_status()

            temp_dir = self.config.temp_dir / "clips"
            temp_dir.mkdir(parents=True, exist_ok=True)

            safe_name = prompt.replace(" ", "_")[:20]
            timestamp = int(time.time())
            output_path = str(temp_dir / f"clip_{safe_name}_{timestamp}.mp4")

            with open(output_path, "wb") as f:
                f.write(response.content)

            file_size = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"  Clip downloaded: {output_path} ({file_size:.1f} MB)")
            return output_path

        except Exception as e:
            logger.error(f"  Download failed: {e}")
            return None


def get_scene_prompts(song_category: str, song_title: str) -> List[str]:
    """Generate video scene prompts based on song category."""
    base_prompts = {
        "counting_songs": [
            "cute cartoon baby counting colorful blocks 1 2 3",
            "animated numbers floating in sky with stars and clouds",
            "cartoon children dancing and holding number balloons",
            "cute animals lined up being counted one by one",
        ],
        "animal_songs": [
            "cute cartoon farm with happy cow, chicken, and dog",
            "animated baby animals playing in green meadow",
            "colorful cartoon zoo with friendly animals waving",
            "cute cartoon cat and dog playing together",
        ],
        "vehicle_songs": [
            "colorful cartoon bus with spinning wheels driving on road",
            "cute animated train going through countryside with children waving",
            "cartoon airplane flying over rainbow with happy clouds",
            "bright red cartoon fire truck with sirens flashing",
        ],
        "color_songs": [
            "animated rainbow appearing over beautiful cartoon landscape",
            "cute cartoon children painting with bright colors",
            "colorful balloons floating up in blue sky",
            "cartoon flowers blooming in different vibrant colors",
        ],
        "action_songs": [
            "cute cartoon baby clapping hands and stomping feet",
            "animated children jumping and dancing in circle",
            "cartoon kids doing exercises stretching and spinning",
            "happy cartoon characters waving and blowing kisses",
        ],
        "lullabies": [
            "peaceful cartoon night sky with twinkling stars and moon",
            "cute cartoon baby sleeping in cozy crib with teddy bear",
            "animated soft clouds floating over sleeping village",
            "gentle cartoon owl sitting on tree branch at night",
        ],
        "alphabet_songs": [
            "colorful animated letters ABC floating and bouncing",
            "cartoon apple, ball, cat representing A B C",
            "cute animated children writing letters on blackboard",
            "bright alphabet blocks stacking up playfully",
        ],
        "food_songs": [
            "cute cartoon fruits dancing apple banana orange",
            "animated vegetables in garden smiling",
            "cartoon baby eating healthy food happily",
            "colorful cartoon kitchen with bouncing fruits",
        ],
        "family_songs": [
            "cute cartoon family hugging together at home",
            "animated parents playing with baby in park",
            "cartoon grandparents telling story to children",
            "happy cartoon family eating dinner together",
        ],
        "friendship_songs": [
            "cute cartoon children holding hands in circle",
            "animated kids sharing toys and smiling",
            "cartoon friends playing on colorful playground",
            "happy cartoon animals being friends together",
        ],
    }

    # Get prompts for category, with fallback
    prompts = base_prompts.get(song_category, [
        "cute cartoon baby singing and dancing happily",
        "colorful animated children's nursery rhyme scene",
        "bright cartoon characters playing with musical instruments",
        "happy animated kids in magical colorful world",
    ])

    return prompts
