"""Creates colorful animated videos for children's songs using moviepy and Pillow."""

import logging
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import get_config
from .lyrics_generator import SongLyrics

logger = logging.getLogger(__name__)


# Emoji characters associated with each song category
CATEGORY_CHARACTERS = {
    "counting_songs": ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "🔢", "🖐️", "✋"],
    "alphabet_songs": ["🔤", "📝", "✏️", "📖", "🅰️", "🅱️", "🔡", "📚"],
    "animal_songs": ["🐶", "🐱", "🐮", "🐷", "🐔", "🦁", "🐸", "🦋"],
    "color_songs": ["🌈", "🎨", "❤️", "💙", "💚", "💛", "💜", "🧡"],
    "shape_songs": ["⭐", "❤️", "🔵", "🔺", "⬛", "💎", "🟡", "🔷"],
    "action_songs": ["👏", "🦶", "💃", "🕺", "🙌", "🤸", "🏃", "👋"],
    "lullabies": ["🌙", "⭐", "💤", "🧸", "🌟", "☁️", "🛏️", "😴"],
    "classic_nursery": ["⭐", "🕷️", "🚌", "🐑", "🌧️", "👸", "🥚", "🐄"],
    "body_parts": ["👋", "👀", "👃", "👂", "🦶", "🖐️", "💪", "🦷"],
    "food_songs": ["🍎", "🍌", "🥕", "🍕", "🧁", "🍓", "🥦", "🍪"],
    "vehicle_songs": ["🚗", "🚂", "✈️", "🚢", "🚒", "🚌", "🚀", "🚲"],
    "weather_songs": ["☀️", "🌧️", "❄️", "🌈", "⛈️", "💨", "☁️", "🌤️"],
    "family_songs": ["👨‍👩‍👧‍👦", "❤️", "🏠", "👶", "🤗", "👨‍👩‍👧", "👴", "👵"],
    "friendship_songs": ["🤝", "💕", "😊", "🎈", "🎉", "👫", "🌻", "💖"],
}



class VideoGenerator:
    """Generates colorful animated videos for children's songs."""

    def __init__(self):
        """Initialize the video generator."""
        self.config = get_config()
        video_config = self.config.video
        self.width, self.height = video_config.get("resolution", [1920, 1080])
        self.fps = video_config.get("fps", 30)
        self.backgrounds = video_config.get("colors", {}).get(
            "backgrounds",
            ["#FFE5E5", "#E5FFE5", "#E5E5FF", "#FFFFE5", "#FFE5FF", "#E5FFFF", "#FFF0E5"],
        )
        self.text_primary = video_config.get("colors", {}).get("text_primary", "#333333")
        self.accent_color = video_config.get("colors", {}).get("accent", "#FF6B6B")
        self.show_lyrics = video_config.get("show_lyrics", True)
        self.intro_duration = video_config.get("intro_duration", 3)
        self.outro_duration = video_config.get("outro_duration", 5)
        self.outro_text = video_config.get("outro_text", "Subscribe for more fun songs!")
        self.decorations = video_config.get(
            "decorations",
            ["stars", "hearts", "musical_notes", "clouds", "flowers", "butterflies", "rainbows"],
        )


    def create_video(
        self, song: SongLyrics, audio_path: str, output_path: str
    ) -> str:
        """Create a complete video for a song.

        Args:
            song: SongLyrics instance with lyrics and metadata.
            audio_path: Path to the audio WAV file.
            output_path: Path to save the output video.

        Returns:
            Path to the generated video file.
        """
        from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

        logger.info(f"Creating video for: {song.title}")

        # Load audio to get duration
        audio_clip = AudioFileClip(audio_path)
        total_duration = audio_clip.duration

        # Plan scenes based on lyrics structure
        scenes = self._plan_scenes(song, total_duration)

        # Render each scene as an ImageClip
        video_clips = []
        for scene in scenes:
            frame = self._render_scene(scene, song)
            frame_array = np.array(frame)
            clip = ImageClip(frame_array).set_duration(scene["duration"])
            video_clips.append(clip)

        # Concatenate all clips
        final_video = concatenate_videoclips(video_clips, method="compose")
        final_video = final_video.set_audio(audio_clip)

        # Write output video
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        final_video.write_videofile(
            output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )

        # Clean up
        audio_clip.close()
        final_video.close()

        logger.info(f"Video saved: {output_path} ({total_duration:.1f}s)")
        return output_path


    def generate_thumbnail(self, song: SongLyrics, output_path: str) -> str:
        """Generate a YouTube thumbnail for the song.

        Args:
            song: SongLyrics instance.
            output_path: Path to save the thumbnail image.

        Returns:
            Path to the generated thumbnail.
        """
        logger.info(f"Generating thumbnail for: {song.title}")

        img = Image.new("RGB", (1280, 720))
        draw = ImageDraw.Draw(img)

        # Gradient background
        bg_color1 = self._hex_to_rgb(random.choice(self.backgrounds))
        bg_color2 = self._hex_to_rgb(random.choice(self.backgrounds))
        self._draw_gradient(draw, 1280, 720, bg_color1, bg_color2)

        # Add decorations
        self._draw_decorations(draw, 1280, 720, count=15)

        # Title text (large, centered)
        font_large = self._get_font(72)
        font_small = self._get_font(36)

        # Draw title with outline for visibility
        title = song.title.upper()
        self._draw_text_centered(
            draw, title, 720 // 3, font_large,
            self._hex_to_rgb(self.text_primary),
            outline_color=(255, 255, 255),
            max_width=1100,
        )

        # Category text
        category_text = song.category.replace("_", " ").title()
        self._draw_text_centered(
            draw, f"🎵 {category_text} 🎵", int(720 * 0.6), font_small,
            self._hex_to_rgb(self.accent_color),
        )

        # Channel name at bottom
        channel_name = self.config.channel.get("name", "Little Star Nursery Rhymes")
        self._draw_text_centered(
            draw, channel_name, int(720 * 0.85), font_small,
            self._hex_to_rgb(self.text_primary),
        )

        # Save thumbnail
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "JPEG", quality=95)
        logger.info(f"Thumbnail saved: {output_path}")
        return output_path


    def _plan_scenes(
        self, song: SongLyrics, total_duration: float
    ) -> List[Dict]:
        """Plan scene list from lyrics structure.

        Structure: title → verse → chorus → verse → chorus → outro

        Args:
            song: SongLyrics instance.
            total_duration: Total audio duration in seconds.

        Returns:
            List of scene dictionaries with type, text, duration, bg_color.
        """
        scenes = []

        # Calculate durations
        intro_dur = float(self.intro_duration)
        outro_dur = float(self.outro_duration)
        content_duration = total_duration - intro_dur - outro_dur

        # Title scene
        scenes.append({
            "type": "title",
            "text": song.title,
            "duration": intro_dur,
            "bg_color": random.choice(self.backgrounds),
        })

        # Content scenes: verse/chorus alternating
        num_content_scenes = len(song.verses) * 2  # verse + chorus each
        if num_content_scenes == 0:
            num_content_scenes = 1

        scene_duration = max(3.0, content_duration / num_content_scenes)

        for i, verse in enumerate(song.verses):
            # Verse scene
            scenes.append({
                "type": "verse",
                "text": verse,
                "duration": scene_duration,
                "bg_color": self.backgrounds[i % len(self.backgrounds)],
                "verse_num": i + 1,
            })
            # Chorus scene
            if song.chorus:
                scenes.append({
                    "type": "chorus",
                    "text": song.chorus,
                    "duration": scene_duration,
                    "bg_color": self.backgrounds[(i + 1) % len(self.backgrounds)],
                })

        # Outro scene
        scenes.append({
            "type": "outro",
            "text": self.outro_text,
            "duration": outro_dur,
            "bg_color": random.choice(self.backgrounds),
        })

        # Adjust durations to match total
        total_planned = sum(s["duration"] for s in scenes)
        if total_planned > 0 and abs(total_planned - total_duration) > 0.5:
            scale_factor = total_duration / total_planned
            for scene in scenes:
                scene["duration"] = max(1.0, scene["duration"] * scale_factor)

        return scenes


    def _render_scene(self, scene: Dict, song: SongLyrics) -> Image.Image:
        """Render a single scene frame.

        Args:
            scene: Scene dictionary with type, text, duration, bg_color.
            song: SongLyrics instance for metadata.

        Returns:
            PIL Image of the rendered frame.
        """
        scene_type = scene.get("type", "verse")

        if scene_type == "title":
            return self._render_title_frame(song, scene)
        elif scene_type == "outro":
            return self._render_outro_frame(scene)
        else:
            return self._render_lyrics_frame(scene, song)

    def _render_title_frame(self, song: SongLyrics, scene: Dict) -> Image.Image:
        """Render the title/intro frame.

        Args:
            song: SongLyrics instance.
            scene: Scene dictionary.

        Returns:
            PIL Image of the title frame.
        """
        img = Image.new("RGB", (self.width, self.height))
        draw = ImageDraw.Draw(img)

        bg_color1 = self._hex_to_rgb(scene.get("bg_color", "#FFE5E5"))
        bg_color2 = self._hex_to_rgb(random.choice(self.backgrounds))
        self._draw_gradient(draw, self.width, self.height, bg_color1, bg_color2)

        # Add decorations
        self._draw_decorations(draw, self.width, self.height, count=20)

        # Title text
        font_title = self._get_font(80)
        font_sub = self._get_font(40)

        # Get category emojis
        emojis = CATEGORY_CHARACTERS.get(song.category, ["🎵", "⭐", "🌟"])
        emoji_str = " ".join(random.sample(emojis, min(3, len(emojis))))

        self._draw_text_centered(
            draw, emoji_str, self.height // 4, font_title,
            self._hex_to_rgb(self.text_primary),
        )

        self._draw_text_centered(
            draw, song.title, self.height // 2, font_title,
            self._hex_to_rgb(self.text_primary),
            outline_color=(255, 255, 255),
            max_width=self.width - 200,
        )

        channel = self.config.channel.get("name", "Little Star Nursery Rhymes")
        self._draw_text_centered(
            draw, f"🎵 {channel} 🎵", int(self.height * 0.75), font_sub,
            self._hex_to_rgb(self.accent_color),
        )

        return img


    def _render_lyrics_frame(self, scene: Dict, song: SongLyrics) -> Image.Image:
        """Render a frame showing lyrics (verse or chorus).

        Args:
            scene: Scene dictionary with text and type info.
            song: SongLyrics instance.

        Returns:
            PIL Image of the lyrics frame.
        """
        img = Image.new("RGB", (self.width, self.height))
        draw = ImageDraw.Draw(img)

        bg_color = self._hex_to_rgb(scene.get("bg_color", "#E5FFE5"))
        bg_color2 = self._hex_to_rgb(random.choice(self.backgrounds))
        self._draw_gradient(draw, self.width, self.height, bg_color, bg_color2)

        # Add decorations (fewer than title)
        self._draw_decorations(draw, self.width, self.height, count=10)

        # Scene type label
        font_label = self._get_font(30)
        font_lyrics = self._get_font(44)

        scene_type = scene.get("type", "verse")
        if scene_type == "chorus":
            label = "🎶 Chorus 🎶"
        else:
            verse_num = scene.get("verse_num", 1)
            label = f"🎵 Verse {verse_num} 🎵"

        self._draw_text_centered(
            draw, label, 80, font_label,
            self._hex_to_rgb(self.accent_color),
        )

        # Draw lyrics text (multiline)
        if self.show_lyrics:
            text = scene.get("text", "")
            lines = text.strip().split("\n")
            y_start = self.height // 4
            line_height = 70

            for i, line in enumerate(lines):
                y = y_start + i * line_height
                if y < self.height - 100:
                    self._draw_text_centered(
                        draw, line.strip(), y, font_lyrics,
                        self._hex_to_rgb(self.text_primary),
                        outline_color=(255, 255, 255),
                        max_width=self.width - 200,
                    )

        # Category emojis at bottom
        emojis = CATEGORY_CHARACTERS.get(song.category, ["🎵"])
        emoji_str = "  ".join(random.sample(emojis, min(4, len(emojis))))
        self._draw_text_centered(
            draw, emoji_str, self.height - 100, font_label,
            self._hex_to_rgb(self.text_primary),
        )

        return img

    def _render_outro_frame(self, scene: Dict) -> Image.Image:
        """Render the outro/subscribe frame.

        Args:
            scene: Scene dictionary.

        Returns:
            PIL Image of the outro frame.
        """
        img = Image.new("RGB", (self.width, self.height))
        draw = ImageDraw.Draw(img)

        bg_color = self._hex_to_rgb(scene.get("bg_color", "#FFE5FF"))
        bg_color2 = self._hex_to_rgb("#FFFFE5")
        self._draw_gradient(draw, self.width, self.height, bg_color, bg_color2)

        # Lots of decorations for outro
        self._draw_decorations(draw, self.width, self.height, count=25)

        font_large = self._get_font(60)
        font_medium = self._get_font(44)

        # Subscribe text
        self._draw_text_centered(
            draw, "⭐ Thank You For Watching! ⭐",
            self.height // 3, font_large,
            self._hex_to_rgb(self.text_primary),
            outline_color=(255, 255, 255),
        )

        self._draw_text_centered(
            draw, self.outro_text,
            self.height // 2, font_medium,
            self._hex_to_rgb(self.accent_color),
        )

        # Channel name
        channel = self.config.channel.get("name", "Little Star Nursery Rhymes")
        self._draw_text_centered(
            draw, f"🌟 {channel} 🌟",
            int(self.height * 0.7), font_medium,
            self._hex_to_rgb(self.text_primary),
        )

        return img


    def _draw_gradient(
        self,
        draw: ImageDraw.Draw,
        width: int,
        height: int,
        color1: Tuple[int, int, int],
        color2: Tuple[int, int, int],
    ):
        """Draw a vertical gradient background.

        Args:
            draw: PIL ImageDraw instance.
            width: Image width.
            height: Image height.
            color1: Top color RGB tuple.
            color2: Bottom color RGB tuple.
        """
        for y in range(height):
            ratio = y / height
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

    def _draw_decorations(
        self, draw: ImageDraw.Draw, width: int, height: int, count: int = 15
    ):
        """Draw random decorations on the frame.

        Args:
            draw: PIL ImageDraw instance.
            width: Image width.
            height: Image height.
            count: Number of decorations to draw.
        """
        for _ in range(count):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(15, 40)
            decoration = random.choice(self.decorations)

            if decoration == "stars":
                self._draw_star(draw, x, y, size)
            elif decoration == "hearts":
                self._draw_heart(draw, x, y, size)
            elif decoration == "musical_notes":
                self._draw_note(draw, x, y, size)
            elif decoration == "clouds":
                self._draw_cloud(draw, x, y, size)
            elif decoration == "flowers":
                self._draw_flower(draw, x, y, size)
            elif decoration == "butterflies":
                self._draw_butterfly(draw, x, y, size)
            elif decoration == "rainbows":
                self._draw_rainbow(draw, x, y, size)

    def _draw_star(self, draw: ImageDraw.Draw, x: int, y: int, size: int):
        """Draw a star decoration."""
        color = (255, 215, 0)  # Gold
        points = []
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5
            r = size if i % 2 == 0 else size // 2
            px = x + int(r * math.cos(angle))
            py = y - int(r * math.sin(angle))
            points.append((px, py))
        if len(points) >= 3:
            draw.polygon(points, fill=color, outline=(255, 200, 0))

    def _draw_heart(self, draw: ImageDraw.Draw, x: int, y: int, size: int):
        """Draw a heart decoration."""
        color = (255, 105, 180)  # Pink
        # Simple heart using two circles and a triangle
        r = size // 3
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
        draw.ellipse([x + r // 2, y - r, x + r + r, y + r], fill=color)
        draw.polygon(
            [(x - r, y), (x + r + r, y), (x + r // 2, y + size)],
            fill=color,
        )


    def _draw_note(self, draw: ImageDraw.Draw, x: int, y: int, size: int):
        """Draw a musical note decoration."""
        color = (100, 100, 200)  # Blue-ish
        # Note head (ellipse)
        draw.ellipse(
            [x - size // 3, y, x + size // 3, y + size // 2],
            fill=color,
        )
        # Stem
        draw.line([(x + size // 3, y + size // 4), (x + size // 3, y - size)], fill=color, width=2)
        # Flag
        draw.arc(
            [x + size // 3, y - size, x + size, y - size // 2],
            start=270, end=90, fill=color, width=2,
        )

    def _draw_cloud(self, draw: ImageDraw.Draw, x: int, y: int, size: int):
        """Draw a cloud decoration."""
        color = (255, 255, 255, 200)
        # Cloud as overlapping circles
        r = size // 2
        draw.ellipse([x - r, y - r // 2, x + r, y + r // 2], fill=(255, 255, 255))
        draw.ellipse([x - r * 2, y, x, y + r], fill=(255, 255, 255))
        draw.ellipse([x, y, x + r * 2, y + r], fill=(255, 255, 255))

    def _draw_flower(self, draw: ImageDraw.Draw, x: int, y: int, size: int):
        """Draw a flower decoration."""
        petal_color = random.choice([(255, 182, 193), (255, 160, 122), (186, 85, 211), (255, 218, 185)])
        center_color = (255, 255, 0)
        r = size // 3
        # Petals
        for angle in range(0, 360, 60):
            px = x + int(r * math.cos(math.radians(angle)))
            py = y + int(r * math.sin(math.radians(angle)))
            draw.ellipse([px - r // 2, py - r // 2, px + r // 2, py + r // 2], fill=petal_color)
        # Center
        draw.ellipse([x - r // 3, y - r // 3, x + r // 3, y + r // 3], fill=center_color)

    def _draw_butterfly(self, draw: ImageDraw.Draw, x: int, y: int, size: int):
        """Draw a butterfly decoration."""
        wing_color = random.choice([(255, 165, 0), (148, 0, 211), (0, 191, 255), (255, 105, 180)])
        r = size // 2
        # Wings
        draw.ellipse([x - r, y - r // 2, x, y + r // 2], fill=wing_color)
        draw.ellipse([x, y - r // 2, x + r, y + r // 2], fill=wing_color)
        # Body
        draw.line([(x, y - r // 2), (x, y + r // 2)], fill=(50, 50, 50), width=2)

    def _draw_rainbow(self, draw: ImageDraw.Draw, x: int, y: int, size: int):
        """Draw a rainbow decoration."""
        colors = [
            (255, 0, 0), (255, 127, 0), (255, 255, 0),
            (0, 255, 0), (0, 0, 255), (75, 0, 130), (148, 0, 211),
        ]
        for i, color in enumerate(colors):
            r = size - i * 3
            if r > 0:
                draw.arc(
                    [x - r, y - r, x + r, y + r],
                    start=180, end=0, fill=color, width=3,
                )


    def _draw_text_centered(
        self,
        draw: ImageDraw.Draw,
        text: str,
        y: int,
        font: ImageFont.ImageFont,
        color: Tuple[int, int, int],
        outline_color: Optional[Tuple[int, int, int]] = None,
        max_width: Optional[int] = None,
    ):
        """Draw text centered horizontally on the image.

        Args:
            draw: PIL ImageDraw instance.
            text: Text to draw.
            y: Y position for the text.
            font: Font to use.
            color: Text color RGB tuple.
            outline_color: Optional outline color for readability.
            max_width: Maximum text width before wrapping.
        """
        if max_width:
            # Simple word wrap
            words = text.split()
            lines = []
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                try:
                    bbox = draw.textbbox((0, 0), test_line, font=font)
                    text_width = bbox[2] - bbox[0]
                except AttributeError:
                    text_width = len(test_line) * 20  # Fallback estimate
                if text_width > max_width and current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    current_line = test_line
            if current_line:
                lines.append(current_line)

            line_height = 60
            for i, line in enumerate(lines):
                self._draw_single_line_centered(
                    draw, line, y + i * line_height, font, color, outline_color
                )
        else:
            self._draw_single_line_centered(draw, text, y, font, color, outline_color)

    def _draw_single_line_centered(
        self,
        draw: ImageDraw.Draw,
        text: str,
        y: int,
        font: ImageFont.ImageFont,
        color: Tuple[int, int, int],
        outline_color: Optional[Tuple[int, int, int]] = None,
    ):
        """Draw a single line of text centered."""
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
        except AttributeError:
            text_width = len(text) * 20

        x = (self.width - text_width) // 2

        # Draw outline if specified
        if outline_color:
            for dx in [-2, -1, 0, 1, 2]:
                for dy in [-2, -1, 0, 1, 2]:
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

        draw.text((x, y), text, font=font, fill=color)

    def _get_font(self, size: int) -> ImageFont.ImageFont:
        """Get a font at the specified size.

        Args:
            size: Font size in pixels.

        Returns:
            PIL ImageFont instance.
        """
        # Try common system font paths
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]

        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, size)
            except (IOError, OSError):
                continue

        # Fallback to default font
        try:
            return ImageFont.truetype("arial.ttf", size)
        except (IOError, OSError):
            return ImageFont.load_default()

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color string to RGB tuple.

        Args:
            hex_color: Color in format '#RRGGBB'.

        Returns:
            RGB tuple (r, g, b).
        """
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
