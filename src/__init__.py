"""AI Baby Songs - Automated nursery rhyme generation and YouTube upload system."""

from .config import get_config, Config
from .lyrics_generator import LyricsGenerator, SongLyrics
from .music_generator import MusicGenerator
from .singing_voice import SingingVoice
from .video_generator import VideoGenerator
from .youtube_uploader import YouTubeUploader, YouTubeSetup
from .scheduler import BabySongPipeline, BabySongScheduler

__all__ = [
    "get_config",
    "Config",
    "LyricsGenerator",
    "SongLyrics",
    "MusicGenerator",
    "SingingVoice",
    "VideoGenerator",
    "YouTubeUploader",
    "YouTubeSetup",
    "BabySongPipeline",
    "BabySongScheduler",
]
