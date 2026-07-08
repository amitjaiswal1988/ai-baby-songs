"""Pipeline orchestrator and scheduler for automated song creation and upload."""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from .config import get_config
from .lyrics_generator import LyricsGenerator, SongLyrics
from .singing_voice import SingingVoice
from .video_generator import VideoGenerator
from .youtube_uploader import YouTubeUploader

logger = logging.getLogger(__name__)



class BabySongPipeline:
    """Complete pipeline for creating and uploading a children's song."""

    def __init__(self):
        """Initialize the pipeline with all components."""
        self.config = get_config()
        self.lyrics_generator = LyricsGenerator()
        self.voice_generator = SingingVoice()
        self.video_generator = VideoGenerator()
        self.uploader = YouTubeUploader()

    def create_and_upload(
        self, category: str = None, topic: str = None
    ) -> Optional[str]:
        """Run the full pipeline: generate lyrics, audio, video, and upload.

        Args:
            category: Song category (random if None).
            topic: Song topic (auto-selected if None).

        Returns:
            YouTube video ID if successful, None otherwise.
        """
        logger.info("="*60)
        logger.info("Starting full pipeline: create and upload")
        logger.info("="*60)

        try:
            # Step 1: Generate lyrics
            logger.info("[1/5] Generating lyrics...")
            song = self.lyrics_generator.generate_song(category, topic)
            logger.info(f"  → Song: '{song.title}' ({song.category})")

            # Step 2: Generate audio (voice + music)
            logger.info("[2/5] Generating audio...")
            audio_path = self.voice_generator.generate_full_song_audio(song)
            logger.info(f"  → Audio: {audio_path}")

            # Step 3: Generate video
            logger.info("[3/5] Generating video...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"{song.title.replace(' ', '_').lower()}_{timestamp}.mp4"
            video_path = str(self.config.output_dir / video_filename)
            self.video_generator.create_video(song, audio_path, video_path)
            logger.info(f"  → Video: {video_path}")

            # Step 4: Generate thumbnail
            logger.info("[4/5] Generating thumbnail...")
            thumb_path = video_path.replace(".mp4", "_thumb.jpg")
            self.video_generator.generate_thumbnail(song, thumb_path)
            logger.info(f"  → Thumbnail: {thumb_path}")

            # Step 5: Upload to YouTube
            logger.info("[5/5] Uploading to YouTube...")
            video_id = self.uploader.upload_video(video_path, song, thumb_path)

            if video_id:
                logger.info(f"  → SUCCESS! Video ID: {video_id}")
                logger.info(f"  → URL: https://www.youtube.com/watch?v={video_id}")
            else:
                logger.error("  → Upload failed!")

            # Cleanup temp files
            self._cleanup()

            return video_id

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            self._cleanup()
            return None

    def create_only(
        self, category: str = None, topic: str = None
    ) -> Optional[Tuple[SongLyrics, str, str]]:
        """Run the pipeline without uploading (for testing).

        Args:
            category: Song category (random if None).
            topic: Song topic (auto-selected if None).

        Returns:
            Tuple of (song, video_path, thumbnail_path) if successful.
        """
        logger.info("="*60)
        logger.info("Starting pipeline: create only (no upload)")
        logger.info("="*60)

        try:
            # Step 1: Generate lyrics
            logger.info("[1/4] Generating lyrics...")
            song = self.lyrics_generator.generate_song(category, topic)
            logger.info(f"  → Song: '{song.title}' ({song.category})")

            # Step 2: Generate audio
            logger.info("[2/4] Generating audio...")
            audio_path = self.voice_generator.generate_full_song_audio(song)
            logger.info(f"  → Audio: {audio_path}")

            # Step 3: Generate video
            logger.info("[3/4] Generating video...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"{song.title.replace(' ', '_').lower()}_{timestamp}.mp4"
            video_path = str(self.config.output_dir / video_filename)
            self.video_generator.create_video(song, audio_path, video_path)
            logger.info(f"  → Video: {video_path}")

            # Step 4: Generate thumbnail
            logger.info("[4/4] Generating thumbnail...")
            thumb_path = video_path.replace(".mp4", "_thumb.jpg")
            self.video_generator.generate_thumbnail(song, thumb_path)
            logger.info(f"  → Thumbnail: {thumb_path}")

            logger.info("="*60)
            logger.info(f"Pipeline complete! Output: {video_path}")
            logger.info("="*60)

            return song, video_path, thumb_path

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return None

    def _cleanup(self):
        """Clean up temporary files if configured."""
        if not self.config.output.get("keep_temp_files", False):
            temp_dir = self.config.temp_dir
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    logger.info("Cleaned up temp files")
                except Exception as e:
                    logger.warning(f"Cleanup error: {e}")



class BabySongScheduler:
    """Scheduled automation for daily song publishing."""

    def __init__(self):
        """Initialize the scheduler."""
        self.config = get_config()
        self.pipeline = BabySongPipeline()
        self.categories = self.config.songs.get("categories", [])
        self._category_index = 0
        self._setup_logging()

    def start(self):
        """Start the scheduler for automated daily publishing.

        Uses APScheduler with CronTrigger for configured publish times.
        """
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BlockingScheduler()

        # Get schedule config
        schedule_config = self.config.schedule
        publish_times = schedule_config.get("publish_times", ["08:00", "17:00"])
        timezone = schedule_config.get("timezone", "America/New_York")

        # Add a job for each publish time
        for i, time_str in enumerate(publish_times):
            hour, minute = time_str.split(":")
            trigger = CronTrigger(
                hour=int(hour),
                minute=int(minute),
                timezone=timezone,
            )
            scheduler.add_job(
                self._run_pipeline,
                trigger=trigger,
                id=f"song_publish_{i}",
                name=f"Publish song at {time_str}",
                misfire_grace_time=3600,  # 1 hour grace period
            )
            logger.info(f"Scheduled job: Publish at {time_str} ({timezone})")

        logger.info("="*60)
        logger.info("Baby Song Scheduler Started!")
        logger.info(f"Publishing {len(publish_times)} videos/day")
        logger.info(f"Times: {', '.join(publish_times)} ({timezone})")
        logger.info(f"Categories: {len(self.categories)} available")
        logger.info("="*60)
        logger.info("Press Ctrl+C to stop.")

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")
            scheduler.shutdown()

    def _run_pipeline(self):
        """Execute the pipeline with the next category in rotation."""
        # Rotate through categories
        if self.categories:
            category = self.categories[self._category_index % len(self.categories)]
            self._category_index += 1
        else:
            category = None

        logger.info(f"Scheduled run - Category: {category}")

        try:
            video_id = self.pipeline.create_and_upload(category=category)
            if video_id:
                logger.info(f"Scheduled upload success: {video_id}")
            else:
                logger.error("Scheduled upload failed")
        except Exception as e:
            logger.error(f"Scheduled run error: {e}", exc_info=True)

    def _setup_logging(self):
        """Configure logging for the scheduler."""
        log_level = self.config.output.get("log_level", "INFO")

        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Add file handler
        log_dir = self.config.project_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"scheduler_{datetime.now().strftime('%Y%m%d')}.log"

        file_handler = logging.FileHandler(str(log_file))
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logging.getLogger().addHandler(file_handler)

        logger.info(f"Logging to: {log_file}")
