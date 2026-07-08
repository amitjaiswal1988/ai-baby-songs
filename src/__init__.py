"""AI Baby Songs - Automated YouTube Nursery Rhymes Channel"""
__version__ = "1.0.0"

# Lazy imports - modules are imported when accessed, not at package load time
# This prevents import errors when optional dependencies aren't installed yet


def __getattr__(name):
    """Lazy import handler."""
    if name == "get_config" or name == "Config":
        from .config import get_config, Config
        return get_config if name == "get_config" else Config
    elif name == "LyricsGenerator":
        from .lyrics_generator import LyricsGenerator
        return LyricsGenerator
    elif name == "SongLyrics":
        from .lyrics_generator import SongLyrics
        return SongLyrics
    elif name == "MusicGenerator":
        from .music_generator import MusicGenerator
        return MusicGenerator
    elif name == "SingingVoice":
        from .singing_voice import SingingVoice
        return SingingVoice
    elif name == "VideoGenerator":
        from .video_generator import VideoGenerator
        return VideoGenerator
    elif name == "YouTubeUploader":
        from .youtube_uploader import YouTubeUploader
        return YouTubeUploader
    elif name == "YouTubeSetup":
        from .youtube_uploader import YouTubeSetup
        return YouTubeSetup
    elif name == "BabySongPipeline":
        from .scheduler import BabySongPipeline
        return BabySongPipeline
    elif name == "BabySongScheduler":
        from .scheduler import BabySongScheduler
        return BabySongScheduler
    raise AttributeError(f"module 'src' has no attribute '{name}'")


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
