"""
Full Automated Pipeline
Combines: OpenAI (lyrics) + Suno (singing) + Kling (cartoon video) + YouTube (upload)
Zero manual work required.
"""
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import get_config
from .lyrics_generator import LyricsGenerator, SongLyrics
from .suno_api import SunoAPI
from .kling_api import KlingAPI, get_scene_prompts
from .youtube_uploader import YouTubeUploader

logger = logging.getLogger(__name__)


class FullAutoPipeline:
    """
    100% Automated Pipeline:
    1. AI writes lyrics (OpenAI)
    2. Suno AI sings the song (real voice)
    3. Kling AI creates cartoon video clips
    4. Combine audio + video
    5. Upload to YouTube

    Zero manual work. Just run and earn.
    """

    def __init__(self):
        self.config = get_config()
        self.lyrics_gen = LyricsGenerator()
        self.suno = SunoAPI()
        self.kling = KlingAPI()
        self.uploader = YouTubeUploader()

    def run(self, category: str = None) -> Optional[str]:
        """
        Run the full pipeline: lyrics → singing → video → upload.

        Args:
            category: Song category. Random if None.

        Returns:
            YouTube video ID if successful.
        """
        start_time = time.time()

        logger.info("=" * 60)
        logger.info("🚀 FULL AUTO PIPELINE STARTED")
        logger.info(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   Category: {category or 'random'}")
        logger.info("=" * 60)

        try:
            # STEP 1: Generate lyrics
            logger.info("\n✍️  STEP 1/5: Generating lyrics...")
            song = self.lyrics_gen.generate_song(category=category)
            logger.info(f"   Title: {song.title}")
            logger.info(f"   Category: {song.category}")
            logger.info(f"   Words: {song.word_count}")

            # STEP 2: Generate singing audio (Suno AI)
            logger.info("\n🎤 STEP 2/5: Generating singing voice (Suno AI)...")
            style = self._get_style_for_category(song.category)
            audio_path = self.suno.generate_song(
                lyrics=song.lyrics,
                title=song.title,
                style=style,
            )

            if not audio_path:
                logger.error("   Suno generation failed!")
                return None
            logger.info(f"   Audio: {audio_path}")

            # STEP 3: Generate cartoon video clips (Kling AI)
            logger.info("\n🎬 STEP 3/5: Generating cartoon clips (Kling AI)...")
            scene_prompts = get_scene_prompts(song.category, song.title)
            video_clips = self.kling.generate_scene_clips(
                scenes=scene_prompts,
                duration_per_clip=5,
            )
            logger.info(f"   Clips generated: {len(video_clips)}")

            # STEP 4: Combine audio + video clips into final video
            logger.info("\n🎞️  STEP 4/5: Combining audio + video...")
            video_path = self._combine_audio_video(audio_path, video_clips, song)
            if not video_path:
                logger.error("   Video combination failed!")
                return None
            logger.info(f"   Final video: {video_path}")

            # STEP 5: Upload to YouTube
            logger.info("\n📤 STEP 5/5: Uploading to YouTube...")
            thumb_path = self._generate_thumbnail(song, video_path)
            video_id = self.uploader.upload_video(video_path, song, thumb_path)

            elapsed = time.time() - start_time
            logger.info("\n" + "=" * 60)
            if video_id:
                logger.info(f"🎉 SUCCESS! Video uploaded in {elapsed:.0f}s")
                logger.info(f"   https://www.youtube.com/watch?v={video_id}")
            else:
                logger.error(f"❌ Upload failed after {elapsed:.0f}s")
            logger.info("=" * 60)

            self._cleanup()
            return video_id

        except Exception as e:
            logger.error(f"\n❌ PIPELINE ERROR: {e}", exc_info=True)
            self._cleanup()
            return None

    def _combine_audio_video(
        self, audio_path: str, video_clips: list, song: SongLyrics
    ) -> Optional[str]:
        """Combine Kling video clips with Suno audio into final video."""
        try:
            from moviepy.editor import (
                AudioFileClip, VideoFileClip, concatenate_videoclips,
                ImageClip, CompositeVideoClip
            )
            import numpy as np
            from .video_generator import VideoGenerator

            audio_clip = AudioFileClip(audio_path)
            total_duration = audio_clip.duration

            if video_clips:
                # Load and loop video clips to match audio duration
                clips = []
                for clip_path in video_clips:
                    try:
                        clip = VideoFileClip(clip_path)
                        clip = clip.resize(height=1080)
                        clips.append(clip)
                    except Exception as e:
                        logger.warning(f"   Could not load clip {clip_path}: {e}")

                if clips:
                    # Loop clips to fill audio duration
                    looped_clips = []
                    current_duration = 0
                    clip_idx = 0
                    while current_duration < total_duration:
                        clip = clips[clip_idx % len(clips)]
                        looped_clips.append(clip)
                        current_duration += clip.duration
                        clip_idx += 1

                    video = concatenate_videoclips(looped_clips, method="compose")
                    video = video.subclip(0, min(video.duration, total_duration))
                    video = video.set_audio(audio_clip)
                else:
                    # Fallback to text-based video
                    video = self._fallback_video(audio_clip, song, total_duration)
            else:
                # No clips generated — use text-based video as fallback
                logger.warning("   No Kling clips available, using fallback video")
                video = self._fallback_video(audio_clip, song, total_duration)

            # Output path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = song.title.replace(" ", "_").lower()[:30]
            output_path = str(self.config.output_dir / f"{safe_title}_{timestamp}.mp4")

            video.write_videofile(
                output_path,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )
            video.close()
            audio_clip.close()

            return output_path

        except Exception as e:
            logger.error(f"   Combine error: {e}")
            return None

    def _fallback_video(self, audio_clip, song, total_duration):
        """Create fallback text-based video if Kling clips fail."""
        from .video_generator import VideoGenerator
        from moviepy.editor import ImageClip, concatenate_videoclips
        import numpy as np

        vg = VideoGenerator()
        scenes = vg._plan_scenes(song, total_duration)

        clips = []
        for scene in scenes:
            frame = vg._render_scene(scene, song)
            clip = ImageClip(np.array(frame)).set_duration(scene["duration"])
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose")
        video = video.set_audio(audio_clip)
        return video

    def _generate_thumbnail(self, song: SongLyrics, video_path: str) -> Optional[str]:
        """Generate thumbnail for the video."""
        try:
            from .video_generator import VideoGenerator
            vg = VideoGenerator()
            thumb_path = video_path.replace(".mp4", "_thumb.jpg")
            vg.generate_thumbnail(song, thumb_path)
            return thumb_path
        except Exception as e:
            logger.warning(f"Thumbnail generation failed: {e}")
            return None

    def _get_style_for_category(self, category: str) -> str:
        """Get Suno music style based on song category."""
        styles = {
            "counting_songs": "hindi children's counting song, cute child voice singing, happy bouncy, educational, xylophone, piano, clapping",
            "alphabet_songs": "hindi alphabet song for kids, sweet girl child singing, phonics, cheerful, ukulele, bells",
            "animal_songs": "hindi children's farm animal song, cute baby voice, animal sounds, happy, acoustic guitar, tambourine",
            "color_songs": "hindi color learning song, little girl singing, bright cheerful, rainbow theme, xylophone, hand claps",
            "shape_songs": "hindi shapes song for toddlers, cute child voice, educational, upbeat, piano, bells",
            "action_songs": "hindi action song for kids, energetic child singing, clapping stomping, bouncy rhythm, drums, xylophone",
            "lullabies": "hindi lullaby for babies, soft sweet female voice, gentle soothing, music box, harp, peaceful",
            "classic_nursery": "hindi nursery rhyme, cute little girl singing, traditional melody, happy, ukulele, bells, bouncy",
            "body_parts": "hindi body parts song, cute child singing, educational fun, pointing actions, piano, claps",
            "food_songs": "hindi food song for kids, cheerful child voice, healthy eating, fun bouncy, xylophone, tambourine",
            "vehicle_songs": "hindi vehicle song, excited child singing, bus train sounds, upbeat, drums, horn sounds, bouncy",
            "weather_songs": "hindi weather song for kids, sweet child voice, nature sounds, gentle cheerful, flute, bells",
            "family_songs": "hindi family song, warm sweet child singing, love theme, gentle happy, ukulele, soft piano",
            "friendship_songs": "hindi friendship song for kids, cheerful children singing together, sharing caring, upbeat, claps, guitar",
        }
        return styles.get(category, "hindi children's nursery rhyme, cute child singing, happy upbeat, xylophone, clapping, Bollywood kids style")

    def _cleanup(self):
        """Clean up temp files."""
        if not self.config.output.get("keep_temp_files", False):
            clips_dir = self.config.temp_dir / "clips"
            if clips_dir.exists():
                try:
                    shutil.rmtree(clips_dir)
                    clips_dir.mkdir(parents=True, exist_ok=True)
                except:
                    pass
