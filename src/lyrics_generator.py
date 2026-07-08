"""AI-powered lyrics generator for children's songs using OpenAI GPT."""

import json
import logging
import random
from dataclasses import dataclass, field
from typing import List, Optional

from openai import OpenAI

from .config import get_config

logger = logging.getLogger(__name__)


@dataclass
class SongLyrics:
    """Represents a generated song with all metadata."""

    title: str
    lyrics: str
    category: str
    educational_topic: str
    description: str
    mood: str
    tempo_suggestion: int
    verses: List[str] = field(default_factory=list)
    chorus: str = ""
    word_count: int = 0
    estimated_duration: int = 120
    suggested_title: str = ""
    suggested_tags: List[str] = field(default_factory=list)


class LyricsGenerator:
    """Generates children's song lyrics using OpenAI GPT."""

    # Topics for each category
    CATEGORY_TOPICS = {
        "counting_songs": [
            "counting to 10", "counting animals", "counting fingers",
            "counting stars", "counting toys", "counting steps",
            "counting fruit", "counting colors", "skip counting by 2",
            "counting backwards from 5"
        ],
        "alphabet_songs": [
            "the letter A", "the letter B", "learning vowels",
            "alphabet animals", "alphabet foods", "phonics fun",
            "writing letters", "uppercase and lowercase",
            "alphabet adventure", "letters in my name"
        ],
        "animal_songs": [
            "farm animals", "jungle animals", "ocean creatures",
            "birds flying", "puppies and kittens", "dinosaurs",
            "butterflies", "baby animals", "animal sounds",
            "pets we love"
        ],
        "color_songs": [
            "rainbow colors", "mixing colors", "colors in nature",
            "red things", "blue things", "yellow sunshine",
            "green garden", "purple grapes", "orange sunset",
            "colorful world"
        ],
        "shape_songs": [
            "circles everywhere", "squares and rectangles", "triangles",
            "stars and hearts", "shapes in nature", "shapes at home",
            "round things", "shape adventures", "finding shapes",
            "drawing shapes"
        ],
        "action_songs": [
            "clap your hands", "jump and hop", "spin around",
            "touch your toes", "dance and wiggle", "march together",
            "stretch up high", "wave hello", "stomp your feet",
            "shake and shimmy"
        ],
        "lullabies": [
            "sleepy time", "goodnight moon", "counting sheep",
            "dreaming", "stars at night", "cozy blanket",
            "bedtime hugs", "nighttime friends", "peaceful dreams",
            "rocking gently"
        ],
        "classic_nursery": [
            "twinkle star", "itsy bitsy spider", "wheels on bus",
            "old macdonald", "row your boat", "humpty dumpty",
            "jack and jill", "baa baa black sheep",
            "mary had a lamb", "rain rain go away"
        ],
        "body_parts": [
            "head shoulders knees toes", "my hands", "my feet",
            "eyes ears nose", "wiggle fingers", "bend and stretch",
            "my face", "arms and legs", "belly button",
            "teeth brushing"
        ],
        "food_songs": [
            "fruits and veggies", "yummy breakfast", "healthy eating",
            "pizza party", "apple picking", "banana song",
            "snack time", "cooking together", "ice cream treat",
            "drinking water"
        ],
        "vehicle_songs": [
            "cars and trucks", "trains going", "airplanes flying",
            "boats sailing", "fire trucks", "school bus",
            "bicycles", "rocket ships", "construction vehicles",
            "ambulance helpers"
        ],
        "weather_songs": [
            "sunny day", "rainy day fun", "snow falling",
            "windy weather", "rainbow after rain", "thunder and lightning",
            "cloud shapes", "seasons changing", "puddle jumping",
            "sunshine morning"
        ],
        "family_songs": [
            "mommy and daddy", "grandparents love", "baby sister",
            "big brother", "family hug", "helping at home",
            "family dinner", "bedtime routine", "weekend fun",
            "I love my family"
        ],
        "friendship_songs": [
            "making friends", "sharing is caring", "playing together",
            "best friends", "being kind", "saying please and thank you",
            "taking turns", "helping others", "happy together",
            "playground fun"
        ],
    }

    def __init__(self):
        """Initialize the lyrics generator."""
        self.config = get_config()
        ai_config = self.config.ai
        self.model = ai_config.get("model", "gpt-4o-mini")
        self.max_tokens = ai_config.get("max_tokens", 1500)
        self.temperature = ai_config.get("temperature", 0.8)
        self.client = OpenAI(api_key=self.config.openai_api_key)

    def generate_song(
        self, category: str = None, topic: str = None
    ) -> SongLyrics:
        """Generate a complete children's song.

        Args:
            category: Song category (e.g., 'counting_songs'). Random if None.
            topic: Specific topic for the song. Auto-selected if None.

        Returns:
            SongLyrics dataclass with complete song data.
        """
        if category is None:
            categories = self.config.songs.get("categories", list(self.CATEGORY_TOPICS.keys()))
            category = random.choice(categories)

        if topic is None:
            topic = self._get_topic_for_category(category)

        logger.info(f"Generating song - Category: {category}, Topic: {topic}")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": self._build_prompt(category, topic)},
                ],
            )

            content = response.choices[0].message.content
            song = self._parse_response(content, category, topic)
            logger.info(f"Generated song: '{song.title}' ({song.word_count} words)")
            return song

        except Exception as e:
            logger.error(f"Error generating song: {e}")
            logger.info("Using fallback song generation")
            return self._generate_fallback_song(category, topic)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the AI model."""
        rules = self.config.songs.get("rules", [])
        rules_text = "\n".join(f"- {rule}" for rule in rules)
        duration = self.config.songs.get("duration_seconds", 120)
        repeat_chorus = self.config.songs.get("repeat_chorus", 3)

        return f"""You are a professional children's songwriter specializing in educational nursery rhymes for ages 0-5.

IMPORTANT RULES:
{rules_text}

SONG STRUCTURE:
- Target duration: {duration} seconds when sung
- Include 2-3 short verses (4 lines each)
- Include a catchy chorus (4 lines) that repeats {repeat_chorus} times
- Use simple, repetitive language
- Include action cues where children can participate

OUTPUT FORMAT:
Respond with a JSON object containing:
{{
    "title": "Song title (catchy, simple)",
    "verses": ["verse 1 text", "verse 2 text", ...],
    "chorus": "chorus text",
    "mood": "happy/playful/calm/energetic",
    "tempo_suggestion": 100,
    "educational_topic": "what the song teaches",
    "description": "2-3 sentence YouTube description of the song",
    "suggested_title": "YouTube-optimized title",
    "suggested_tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}"""

    def _build_prompt(self, category: str, topic: str) -> str:
        """Build the user prompt for song generation.

        Args:
            category: Song category.
            topic: Specific topic.

        Returns:
            Formatted prompt string.
        """
        channel_name = self.config.channel.get("name", "Little Star Nursery Rhymes")
        target_age = self.config.channel.get("target_age", "0-5")

        return f"""Write a children's song for the YouTube channel "{channel_name}".

Category: {category.replace('_', ' ').title()}
Topic: {topic}
Target Age: {target_age} years old
Duration: About 2 minutes when sung at a gentle pace

The song should be:
- Fun and engaging for toddlers and preschoolers
- Educational about {topic}
- Easy to sing along with
- Have clear verse/chorus structure
- Include simple actions children can do

Make it unique and creative while being age-appropriate."""

    def _get_topic_for_category(self, category: str) -> str:
        """Get a random topic for the given category.

        Args:
            category: Song category.

        Returns:
            A topic string.
        """
        topics = self.CATEGORY_TOPICS.get(category, ["fun learning"])
        return random.choice(topics)

    def _parse_response(self, content: str, category: str, topic: str) -> SongLyrics:
        """Parse the AI response into a SongLyrics dataclass.

        Args:
            content: JSON string from the AI response.
            category: Song category.
            topic: Song topic.

        Returns:
            SongLyrics instance.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse AI response as JSON, using fallback")
            return self._generate_fallback_song(category, topic)

        verses = data.get("verses", [])
        chorus = data.get("chorus", "")

        # Build full lyrics text
        lyrics_parts = []
        for i, verse in enumerate(verses):
            lyrics_parts.append(f"[Verse {i + 1}]\n{verse}")
            if i == 0 or i < len(verses) - 1:
                lyrics_parts.append(f"[Chorus]\n{chorus}")
        # Final chorus
        lyrics_parts.append(f"[Chorus]\n{chorus}")
        full_lyrics = "\n\n".join(lyrics_parts)

        word_count = len(full_lyrics.split())
        # Estimate ~2.5 words per second for children's songs
        estimated_duration = int(word_count / 2.5)

        title = data.get("title", f"Fun {topic.title()} Song")

        return SongLyrics(
            title=title,
            lyrics=full_lyrics,
            category=category,
            educational_topic=data.get("educational_topic", topic),
            description=data.get("description", f"A fun song about {topic} for kids!"),
            mood=data.get("mood", "happy"),
            tempo_suggestion=data.get("tempo_suggestion", 100),
            verses=verses,
            chorus=chorus,
            word_count=word_count,
            estimated_duration=estimated_duration,
            suggested_title=data.get("suggested_title", title),
            suggested_tags=data.get("suggested_tags", []),
        )

    def _generate_fallback_song(self, category: str, topic: str) -> SongLyrics:
        """Generate a template-based fallback song when AI generation fails.

        Args:
            category: Song category.
            topic: Song topic.

        Returns:
            SongLyrics instance with template-based content.
        """
        logger.info(f"Generating fallback song for category={category}, topic={topic}")

        topic_title = topic.replace("_", " ").title()

        # Template-based verses
        verses = [
            f"Come along and sing with me,\n"
            f"Learning about {topic} is so much fun you see,\n"
            f"Clap your hands and stomp your feet,\n"
            f"This {topic} song just can't be beat!",

            f"Every day we learn something new,\n"
            f"About {topic}, me and you,\n"
            f"Spin around and touch the ground,\n"
            f"The best {topic} song we've found!",

            f"Now it's time to say goodbye,\n"
            f"But don't you worry, don't you cry,\n"
            f"We'll sing again another day,\n"
            f"Learning {topic} the fun way!",
        ]

        chorus = (
            f"La la la, {topic_title}!\n"
            f"La la la, sing with me!\n"
            f"La la la, {topic_title}!\n"
            f"Learning is so fun, you see!"
        )

        # Build full lyrics
        lyrics_parts = []
        for i, verse in enumerate(verses):
            lyrics_parts.append(f"[Verse {i + 1}]\n{verse}")
            lyrics_parts.append(f"[Chorus]\n{chorus}")
        full_lyrics = "\n\n".join(lyrics_parts)

        word_count = len(full_lyrics.split())
        title = f"The {topic_title} Song"

        return SongLyrics(
            title=title,
            lyrics=full_lyrics,
            category=category,
            educational_topic=topic,
            description=f"A fun and educational song about {topic} for babies, toddlers, and preschoolers!",
            mood="happy",
            tempo_suggestion=100,
            verses=verses,
            chorus=chorus,
            word_count=word_count,
            estimated_duration=int(word_count / 2.5),
            suggested_title=f"{title} | Fun {category.replace('_', ' ').title()} for Kids",
            suggested_tags=[
                topic, category.replace("_", " "), "kids songs",
                "nursery rhymes", "learning songs"
            ],
        )
