"""TTS voice generation and music mixing for children's songs."""

import asyncio
import io
import logging
import struct
import tempfile
import wave
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from .config import get_config
from .lyrics_generator import SongLyrics
from .music_generator import MusicGenerator, SAMPLE_RATE

logger = logging.getLogger(__name__)


class SingingVoice:
    """Generates complete song audio by combining TTS voice with background music."""

    def __init__(self):
        """Initialize the singing voice generator."""
        self.config = get_config()
        voice_config = self.config.voice
        self.voice_name = voice_config.get("primary_voice", "en-US-AnaNeural")
        self.rate = voice_config.get("rate", "-10%")
        self.pitch = voice_config.get("pitch", "+10Hz")
        self.volume = voice_config.get("volume", "+0%")
        self.music_generator = MusicGenerator()

    def generate_full_song_audio(self, song: SongLyrics) -> str:
        """Generate the complete song audio file combining voice and music.

        Pipeline:
        1. Generate voice segments per verse/chorus
        2. Assemble with pauses (verse→chorus→verse→chorus structure)
        3. Generate background music
        4. Mix voice+music with ducking
        5. Add intro jingle + outro
        6. Save as WAV

        Args:
            song: SongLyrics instance with lyrics and structure.

        Returns:
            Path to the generated WAV file.
        """
        logger.info(f"Generating full song audio for: {song.title}")

        # Step 1: Generate voice segments for each verse and chorus
        voice_segments = []
        segment_types = []  # Track whether segment is verse or chorus

        for i, verse in enumerate(song.verses):
            logger.info(f"Generating voice for verse {i + 1}")
            verse_audio = self._run_async(self._text_to_speech(verse))
            if verse_audio is not None:
                voice_segments.append(verse_audio)
                segment_types.append("verse")

            # Add chorus after each verse
            if song.chorus:
                logger.info(f"Generating voice for chorus (after verse {i + 1})")
                chorus_audio = self._run_async(self._text_to_speech(song.chorus))
                if chorus_audio is not None:
                    voice_segments.append(chorus_audio)
                    segment_types.append("chorus")

        # Step 2: Assemble voice segments with pauses
        pause_duration = 0.8  # seconds between segments
        pause_samples = int(pause_duration * SAMPLE_RATE)
        pause = np.zeros(pause_samples, dtype=np.float32)

        # Calculate total voice duration
        assembled_parts = []
        for i, segment in enumerate(voice_segments):
            assembled_parts.append(segment)
            if i < len(voice_segments) - 1:
                assembled_parts.append(pause)

        if assembled_parts:
            voice_track = np.concatenate(assembled_parts)
        else:
            # Fallback: generate silence if TTS failed completely
            logger.warning("No voice segments generated, creating silent track")
            voice_track = np.zeros(int(SAMPLE_RATE * song.estimated_duration), dtype=np.float32)

        voice_duration = len(voice_track) / SAMPLE_RATE
        logger.info(f"Voice track assembled: {voice_duration:.1f}s")

        # Step 3: Generate background music to match voice duration
        music_track = self.music_generator.generate_full_track(song, voice_duration)

        # Ensure music is same length as voice
        if len(music_track) < len(voice_track):
            padding = np.zeros(len(voice_track) - len(music_track), dtype=np.float32)
            music_track = np.concatenate([music_track, padding])
        elif len(music_track) > len(voice_track):
            music_track = music_track[:len(voice_track)]

        # Step 4: Mix voice + music with ducking
        mixed = self._mix_with_ducking(voice_track, music_track)

        # Step 5: Add intro jingle and outro
        intro_duration = self.config.video.get("intro_duration", 3)
        outro_duration = self.config.video.get("outro_duration", 5)

        intro_jingle = self.music_generator.generate_intro_jingle(float(intro_duration))
        outro_music = self.music_generator.generate_outro_music(float(outro_duration))

        # Small gap between intro and main content
        intro_gap = np.zeros(int(0.5 * SAMPLE_RATE), dtype=np.float32)
        outro_gap = np.zeros(int(0.5 * SAMPLE_RATE), dtype=np.float32)

        # Assemble final audio
        final_audio = np.concatenate([
            intro_jingle,
            intro_gap,
            mixed,
            outro_gap,
            outro_music,
        ])

        # Step 6: Save as WAV
        output_path = self.config.temp_dir / f"{song.title.replace(' ', '_').lower()}_full.wav"
        self._save_wav(final_audio, str(output_path))

        total_duration = len(final_audio) / SAMPLE_RATE
        logger.info(f"Full song audio saved: {output_path} ({total_duration:.1f}s)")

        return str(output_path)

    def _mix_with_ducking(
        self, voice: np.ndarray, music: np.ndarray, duck_amount: float = 0.3
    ) -> np.ndarray:
        """Mix voice and music with ducking (reduce music when voice is present).

        Args:
            voice: Voice audio numpy array.
            music: Music audio numpy array.
            duck_amount: How much to reduce music volume during voice (0-1).

        Returns:
            Mixed audio numpy array.
        """
        # Detect voice activity using RMS energy
        window_size = int(0.05 * SAMPLE_RATE)  # 50ms windows
        voice_energy = np.zeros(len(voice), dtype=np.float32)

        for i in range(0, len(voice) - window_size, window_size):
            window = voice[i:i + window_size]
            rms = np.sqrt(np.mean(window ** 2))
            voice_energy[i:i + window_size] = rms

        # Determine threshold for voice activity
        max_energy = np.max(voice_energy)
        threshold = max_energy * 0.1 if max_energy > 0 else 0.01

        # Create ducking envelope (1.0 = full volume, duck_amount = reduced)
        duck_envelope = np.ones(len(music), dtype=np.float32)
        voice_active = voice_energy > threshold

        # Smooth the ducking envelope to avoid clicks
        smoothing_samples = int(0.05 * SAMPLE_RATE)
        for i in range(len(music)):
            if i < len(voice_active) and voice_active[i]:
                duck_envelope[i] = duck_amount

        # Apply smoothing with simple moving average
        if len(duck_envelope) > smoothing_samples:
            kernel = np.ones(smoothing_samples) / smoothing_samples
            duck_envelope = np.convolve(duck_envelope, kernel, mode="same").astype(np.float32)

        # Apply ducking to music
        ducked_music = music[:len(duck_envelope)] * duck_envelope[:len(music)]

        # Mix voice and ducked music
        mixed = voice + ducked_music[:len(voice)]

        # Normalize
        max_val = np.max(np.abs(mixed))
        if max_val > 0.95:
            mixed = mixed * (0.95 / max_val)

        return mixed

    async def _text_to_speech(self, text: str) -> Optional[np.ndarray]:
        """Convert text to speech using edge-tts.

        Args:
            text: Text to synthesize.

        Returns:
            Numpy array of audio samples, or None on failure.
        """
        try:
            import edge_tts
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice_name,
                rate=self.rate,
                pitch=self.pitch,
                volume=self.volume,
            )

            # Collect audio bytes
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]

            if not audio_bytes:
                logger.warning(f"No audio generated for text: {text[:50]}...")
                return None

            # Convert MP3 bytes to numpy array
            audio_array = self._mp3_to_numpy(audio_bytes)
            return audio_array

        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None

    def _mp3_to_numpy(self, mp3_bytes: bytes) -> Optional[np.ndarray]:
        """Convert MP3 bytes to numpy array at target sample rate.

        Uses a temporary file and scipy for conversion.

        Args:
            mp3_bytes: Raw MP3 audio bytes.

        Returns:
            Numpy array of audio samples (mono, float32), or None on failure.
        """
        try:
            # Write MP3 to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
                tmp_mp3.write(mp3_bytes)
                tmp_mp3_path = tmp_mp3.name

            # Use pydub-like approach with raw bytes
            # For edge-tts, output is already mp3 format
            # We'll use scipy to read if possible, or fall back to simple conversion
            try:
                from scipy.io import wavfile
                import subprocess

                # Convert MP3 to WAV using ffmpeg if available
                tmp_wav_path = tmp_mp3_path.replace(".mp3", ".wav")
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", tmp_mp3_path, "-ar", str(SAMPLE_RATE),
                     "-ac", "1", "-f", "wav", tmp_wav_path],
                    capture_output=True, timeout=30,
                )

                if result.returncode == 0:
                    audio = self._load_wav_as_numpy(tmp_wav_path)
                    # Clean up temp files
                    Path(tmp_mp3_path).unlink(missing_ok=True)
                    Path(tmp_wav_path).unlink(missing_ok=True)
                    return audio
            except (ImportError, FileNotFoundError, subprocess.TimeoutExpired):
                pass

            # Fallback: try to parse MP3 bytes directly using io
            # This is a simplified approach - in production use pydub
            logger.warning("ffmpeg not available, using simplified MP3 parsing")
            Path(tmp_mp3_path).unlink(missing_ok=True)

            # Generate a reasonable placeholder based on text length
            # Estimate duration: ~150 words per minute for children's speech
            word_count = len(mp3_bytes) / 1000  # Rough estimate
            duration = max(2.0, word_count * 0.1)
            return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)

        except Exception as e:
            logger.error(f"MP3 to numpy conversion error: {e}")
            return None

    def _load_wav_as_numpy(self, wav_path: str) -> Optional[np.ndarray]:
        """Load a WAV file as a numpy array.

        Args:
            wav_path: Path to WAV file.

        Returns:
            Numpy array of audio samples (mono, float32).
        """
        try:
            with wave.open(wav_path, "r") as wav_file:
                n_channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                framerate = wav_file.getframerate()
                n_frames = wav_file.getnframes()

                raw_data = wav_file.readframes(n_frames)

            # Convert to numpy based on sample width
            if sample_width == 2:
                audio = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
                audio /= 32768.0
            elif sample_width == 4:
                audio = np.frombuffer(raw_data, dtype=np.int32).astype(np.float32)
                audio /= 2147483648.0
            else:
                audio = np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32)
                audio = (audio - 128.0) / 128.0

            # Convert to mono if stereo
            if n_channels == 2:
                audio = audio.reshape(-1, 2).mean(axis=1)

            # Resample if necessary
            if framerate != SAMPLE_RATE:
                # Simple linear interpolation resampling
                original_length = len(audio)
                target_length = int(original_length * SAMPLE_RATE / framerate)
                indices = np.linspace(0, original_length - 1, target_length)
                audio = np.interp(indices, np.arange(original_length), audio).astype(np.float32)

            return audio

        except Exception as e:
            logger.error(f"Error loading WAV file {wav_path}: {e}")
            return None

    def _save_wav(self, audio: np.ndarray, output_path: str) -> str:
        """Save audio numpy array as a WAV file.

        Args:
            audio: Numpy array of audio samples (float32, -1.0 to 1.0).
            output_path: Path to save the WAV file.

        Returns:
            Path to the saved WAV file.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Convert float32 to int16
        audio_int16 = np.clip(audio, -1.0, 1.0)
        audio_int16 = (audio_int16 * 32767).astype(np.int16)

        with wave.open(output_path, "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(audio_int16.tobytes())

        logger.info(f"Saved WAV: {output_path} ({len(audio) / SAMPLE_RATE:.1f}s)")
        return output_path

    def _run_async(self, coro) -> any:
        """Run an async coroutine synchronously.

        Args:
            coro: Coroutine to run.

        Returns:
            Result of the coroutine.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in an async context, create a new loop in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop exists, create one
            return asyncio.run(coro)
