"""AI Baby Songs - CLI Entry Point.

Automated nursery rhyme generation and YouTube upload system.
"""

import argparse
import logging
import sys

from src.config import get_config

logger = logging.getLogger(__name__)



def setup_logging(level: str = "INFO"):
    """Configure logging for the application."""
    try:
        import colorlog

        handler = colorlog.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        ))
        logging.basicConfig(level=getattr(logging, level, logging.INFO), handlers=[handler])
    except ImportError:
        logging.basicConfig(
            level=getattr(logging, level, logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )


def cmd_run(args):
    """Run a single pipeline execution (generate + upload)."""
    from src.scheduler import BabySongPipeline

    pipeline = BabySongPipeline()
    video_id = pipeline.create_and_upload(
        category=args.category,
        topic=getattr(args, "topic", None),
    )

    if video_id:
        print(f"\n✅ Success! Video uploaded: https://www.youtube.com/watch?v={video_id}")
    else:
        print("\n❌ Pipeline failed. Check logs for details.")
        sys.exit(1)


def cmd_schedule(args):
    """Start the automated scheduler."""
    from src.scheduler import BabySongScheduler

    print("🎵 Starting AI Baby Songs Scheduler...")
    print("   Videos will be generated and uploaded automatically.")
    print("   Press Ctrl+C to stop.\n")

    scheduler = BabySongScheduler()
    scheduler.start()


def cmd_create_only(args):
    """Create a song without uploading."""
    from src.scheduler import BabySongPipeline

    pipeline = BabySongPipeline()
    result = pipeline.create_only(
        category=args.category,
        topic=getattr(args, "topic", None),
    )

    if result:
        song, video_path, thumb_path = result
        print(f"\n✅ Song created successfully!")
        print(f"   Title: {song.title}")
        print(f"   Category: {song.category}")
        print(f"   Video: {video_path}")
        print(f"   Thumbnail: {thumb_path}")
    else:
        print("\n❌ Creation failed. Check logs for details.")
        sys.exit(1)



def cmd_test_lyrics(args):
    """Test lyrics generation only."""
    from src.lyrics_generator import LyricsGenerator

    generator = LyricsGenerator()
    song = generator.generate_song(category=args.category)

    print(f"\n{'='*60}")
    print(f"🎵 {song.title}")
    print(f"{'='*60}")
    print(f"Category: {song.category}")
    print(f"Topic: {song.educational_topic}")
    print(f"Mood: {song.mood}")
    print(f"Tempo: {song.tempo_suggestion} BPM")
    print(f"Words: {song.word_count}")
    print(f"Est. Duration: {song.estimated_duration}s")
    print(f"\n{'='*60}")
    print("LYRICS:")
    print(f"{'='*60}")
    print(song.lyrics)
    print(f"\n{'='*60}")
    print(f"YouTube Title: {song.suggested_title}")
    print(f"Tags: {', '.join(song.suggested_tags)}")
    print(f"Description: {song.description}")
    print(f"{'='*60}\n")


def cmd_test_audio(args):
    """Test audio generation only (lyrics + voice + music)."""
    from src.lyrics_generator import LyricsGenerator
    from src.singing_voice import SingingVoice

    print("🎵 Generating test audio...")

    generator = LyricsGenerator()
    song = generator.generate_song(category=args.category)
    print(f"   Song: {song.title}")

    voice = SingingVoice()
    audio_path = voice.generate_full_song_audio(song)

    print(f"\n✅ Audio generated: {audio_path}")
    print(f"   Title: {song.title}")
    print(f"   Category: {song.category}")


def cmd_setup_youtube(args):
    """Run YouTube API setup wizard."""
    from src.youtube_uploader import YouTubeSetup

    client_secret = getattr(args, "client_secret", None)
    setup = YouTubeSetup(client_secret_path=client_secret)

    print("🔧 YouTube API Setup")
    print("="*60)

    token = setup.generate_refresh_token()
    if token is None:
        print("\n❌ Setup failed. Follow the instructions above.")
        sys.exit(1)


def cmd_list_voices(args):
    """List available TTS voices."""
    import asyncio
    import edge_tts

    async def list_voices():
        voices = await edge_tts.list_voices()
        language = getattr(args, "language", None) or "en"

        print(f"\n🎤 Available voices (language: {language}):")
        print(f"{'='*60}")

        filtered = [v for v in voices if v["Locale"].startswith(language)]
        for voice in sorted(filtered, key=lambda v: v["ShortName"]):
            gender = voice.get("Gender", "Unknown")
            name = voice["ShortName"]
            locale = voice["Locale"]
            print(f"  {name:<30} {gender:<8} {locale}")

        print(f"\n  Total: {len(filtered)} voices")
        print(f"  Current: {get_config().voice.get('primary_voice', 'en-US-AnaNeural')}")

    asyncio.run(list_voices())



def cmd_batch(args):
    """Generate multiple songs in batch mode."""
    from src.scheduler import BabySongPipeline

    count = args.count or 5
    category = args.category

    print(f"🎵 Batch mode: Creating {count} songs")
    if category:
        print(f"   Category: {category}")
    print(f"{'='*60}")

    pipeline = BabySongPipeline()
    successes = 0
    failures = 0

    for i in range(count):
        print(f"\n[{i+1}/{count}] Creating song...")
        try:
            result = pipeline.create_and_upload(category=category)
            if result:
                successes += 1
                print(f"  ✅ Uploaded: https://www.youtube.com/watch?v={result}")
            else:
                failures += 1
                print(f"  ❌ Failed")
        except Exception as e:
            failures += 1
            print(f"  ❌ Error: {e}")

    print(f"\n{'='*60}")
    print(f"Batch complete: {successes} succeeded, {failures} failed")
    print(f"{'='*60}")


def cmd_create_from_audio(args):
    """Create video from a Suno.ai MP3 file and upload to YouTube."""
    import os
    from datetime import datetime
    from src.video_generator import VideoGenerator
    from src.youtube_uploader import YouTubeUploader
    from src.lyrics_generator import SongLyrics, LyricsGenerator

    audio_path = args.audio
    if not audio_path:
        print("❌ --audio required! Example:")
        print("   python main.py --create-from-audio --audio input\\my_song.mp3")
        sys.exit(1)

    if not os.path.exists(audio_path):
        print(f"❌ File not found: {audio_path}")
        sys.exit(1)

    print(f"🎵 Creating video from: {audio_path}")

    # Generate or use provided title
    title = args.title
    if not title:
        # Extract title from filename
        title = os.path.splitext(os.path.basename(audio_path))[0]
        title = title.replace("_", " ").replace("-", " ").title()

    print(f"   Title: {title}")

    # Generate lyrics for metadata (or use category)
    category = args.category or "classic_nursery"
    print(f"   Category: {category}")

    # Create a SongLyrics object for metadata
    song = SongLyrics(
        title=title,
        lyrics=f"[Singing]\n{title}",
        category=category,
        educational_topic=category.replace("_", " "),
        description=f"A fun children's song: {title}",
        mood="happy",
        tempo_suggestion=100,
        verses=[title],
        chorus=title,
        word_count=len(title.split()),
        estimated_duration=120,
        suggested_title=f"{title} | Nursery Rhymes for Kids",
        suggested_tags=["nursery rhymes", "kids songs", "baby songs",
                       "children music", category.replace("_", " "), title.lower()],
    )

    # Create video
    config = get_config()
    video_gen = VideoGenerator()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = title.replace(" ", "_").lower()[:30]
    video_path = str(config.output_dir / f"{safe_title}_{timestamp}.mp4")

    print(f"\n🎬 Creating video...")
    video_gen.create_video(song, audio_path, video_path)
    print(f"   ✅ Video: {video_path}")

    # Generate thumbnail
    thumb_path = video_path.replace(".mp4", "_thumb.jpg")
    video_gen.generate_thumbnail(song, thumb_path)
    print(f"   ✅ Thumbnail: {thumb_path}")

    # Ask if user wants to upload
    print(f"\n📤 Upload to YouTube?")
    print(f"   Title: {song.suggested_title}")
    answer = input("   Type 'y' to upload, anything else to skip: ").strip().lower()

    if answer == 'y':
        uploader = YouTubeUploader()
        video_id = uploader.upload_video(video_path, song, thumb_path)
        if video_id:
            print(f"\n🎉 UPLOADED! https://www.youtube.com/watch?v={video_id}")
        else:
            print(f"\n❌ Upload failed. Check YouTube API setup.")
    else:
        print(f"\n✅ Video saved (not uploaded): {video_path}")
        print(f"   Play it: start {video_path}")


def cmd_auto(args):
    """Run FULL AUTO pipeline once: lyrics + singing + cartoon + upload."""
    from src.full_pipeline import FullAutoPipeline

    print("🚀 FULL AUTO MODE: AI does everything!")
    print("   Lyrics → Singing → Cartoon Video → YouTube Upload")
    print("=" * 50)

    pipeline = FullAutoPipeline()
    video_id = pipeline.run(category=args.category)

    if video_id:
        print(f"\n🎉 SUCCESS! Video LIVE on YouTube!")
        print(f"   https://www.youtube.com/watch?v={video_id}")
    else:
        print(f"\n❌ Failed. Check logs for details.")
        sys.exit(1)


def cmd_auto_schedule(args):
    """Start FULL AUTO scheduler — daily cartoon videos, zero manual work."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from src.full_pipeline import FullAutoPipeline

    config = get_config()
    schedule = config.schedule
    publish_times = schedule.get("publish_times", ["08:00", "17:00"])
    categories = config.songs.get("categories", [])
    timezone = schedule.get("timezone", "America/New_York")

    pipeline = FullAutoPipeline()
    scheduler = BlockingScheduler()
    category_index = [0]

    def run_job():
        cat = categories[category_index[0] % len(categories)]
        category_index[0] += 1
        pipeline.run(category=cat)

    for i, time_str in enumerate(publish_times):
        hour, minute = time_str.split(":")
        scheduler.add_job(
            run_job,
            trigger=CronTrigger(hour=int(hour), minute=int(minute), timezone=timezone),
            id=f"auto_video_{i}",
            name=f"Auto Video at {time_str}",
        )

    print("🚀 FULL AUTO SCHEDULER STARTED!")
    print(f"   Videos per day: {len(publish_times)}")
    print(f"   Times: {', '.join(publish_times)}")
    print(f"   Categories: {len(categories)}")
    print(f"   Quality: HIGH (Suno singing + Kling cartoon)")
    print("=" * 50)
    print("   AI will create and upload videos automatically.")
    print("   You do NOTHING. Just earn money.")
    print("=" * 50)
    print("   Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped.")
        scheduler.shutdown()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="ai-baby-songs",
        description="AI Baby Songs - Automated nursery rhyme generator for YouTube",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --run                           # Generate and upload one song
  python main.py --run --category animal_songs   # Specific category
  python main.py --schedule                      # Start automated scheduler
  python main.py --create-only                   # Create without uploading
  python main.py --test-lyrics                   # Test lyrics generation
  python main.py --test-audio                    # Test audio generation
  python main.py --setup-youtube                 # Setup YouTube credentials
  python main.py --list-voices                   # List available TTS voices
  python main.py --batch --count 10              # Generate 10 songs
        """,
    )

    # Mutually exclusive mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--run", action="store_true",
        help="Generate and upload a single song",
    )
    mode_group.add_argument(
        "--schedule", action="store_true",
        help="Start the automated daily scheduler",
    )
    mode_group.add_argument(
        "--create-only", action="store_true",
        help="Create a song without uploading to YouTube",
    )
    mode_group.add_argument(
        "--test-lyrics", action="store_true",
        help="Test lyrics generation only",
    )
    mode_group.add_argument(
        "--test-audio", action="store_true",
        help="Test audio generation (lyrics + voice + music)",
    )
    mode_group.add_argument(
        "--setup-youtube", action="store_true",
        help="Run YouTube API setup wizard",
    )
    mode_group.add_argument(
        "--list-voices", action="store_true",
        help="List available TTS voices for edge-tts",
    )
    mode_group.add_argument(
        "--batch", action="store_true",
        help="Generate multiple songs in batch mode",
    )
    mode_group.add_argument(
        "--create-from-audio", action="store_true",
        help="Create video from Suno.ai MP3 file (with lyrics + upload)",
    )
    mode_group.add_argument(
        "--auto", action="store_true",
        help="FULL AUTO: AI lyrics + Suno singing + Kling cartoon + YouTube upload",
    )
    mode_group.add_argument(
        "--auto-schedule", action="store_true",
        help="Start FULL AUTO scheduler (daily cartoon videos, zero manual work)",
    )

    # Optional arguments
    parser.add_argument(
        "--category", type=str, default=None,
        help="Song category (e.g., counting_songs, animal_songs, lullabies)",
    )
    parser.add_argument(
        "--count", type=int, default=5,
        help="Number of songs for batch mode (default: 5)",
    )
    parser.add_argument(
        "--client-secret", type=str, default=None,
        help="Path to client_secret.json for YouTube setup",
    )
    parser.add_argument(
        "--language", type=str, default="en",
        help="Language filter for --list-voices (default: en)",
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to config.yaml (default: ./config.yaml)",
    )
    parser.add_argument(
        "--audio", type=str, default=None,
        help="Path to MP3/WAV audio file (for --create-from-audio)",
    )
    parser.add_argument(
        "--title", type=str, default=None,
        help="Song title (for --create-from-audio)",
    )

    args = parser.parse_args()

    # Initialize config with custom path if provided
    if args.config:
        get_config(args.config)
    else:
        get_config()

    # Setup logging
    config = get_config()
    log_level = config.output.get("log_level", "INFO")
    setup_logging(log_level)

    # Route to appropriate command
    if args.run:
        cmd_run(args)
    elif args.schedule:
        cmd_schedule(args)
    elif args.create_only:
        cmd_create_only(args)
    elif args.test_lyrics:
        cmd_test_lyrics(args)
    elif args.test_audio:
        cmd_test_audio(args)
    elif args.setup_youtube:
        cmd_setup_youtube(args)
    elif args.list_voices:
        cmd_list_voices(args)
    elif args.batch:
        cmd_batch(args)
    elif args.create_from_audio:
        cmd_create_from_audio(args)
    elif args.auto:
        cmd_auto(args)
    elif args.auto_schedule:
        cmd_auto_schedule(args)


if __name__ == "__main__":
    main()
