"""Synthesizes children's melodies and background music using numpy audio generation."""

import logging
import random
import struct
import wave
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from .config import get_config
from .lyrics_generator import SongLyrics

logger = logging.getLogger(__name__)

# Sample rate for all audio generation
SAMPLE_RATE = 44100

# Note frequencies (Hz) from C3 to C6
NOTE_FREQUENCIES = {
    "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61,
    "G3": 196.00, "A3": 220.00, "B3": 246.94,
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23,
    "G4": 392.00, "A4": 440.00, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "F5": 698.46,
    "G5": 783.99, "A5": 880.00, "B5": 987.77,
    "C6": 1046.50,
}

# Musical scales
SCALES = {
    "C_major": ["C", "D", "E", "F", "G", "A", "B"],
    "G_major": ["G", "A", "B", "C", "D", "E", "F#"],
    "F_major": ["F", "G", "A", "Bb", "C", "D", "E"],
    "A_minor": ["A", "B", "C", "D", "E", "F", "G"],
    "D_major": ["D", "E", "F#", "G", "A", "B", "C#"],
}

# Common chord progressions for children's music
CHILDREN_PROGRESSIONS = [
    [1, 4, 5, 1],       # I-IV-V-I (classic)
    [1, 5, 6, 4],       # I-V-vi-IV (pop)
    [1, 4, 1, 5],       # I-IV-I-V (simple)
    [1, 6, 4, 5],       # I-vi-IV-V (doo-wop)
    [1, 4, 5, 4],       # I-IV-V-IV (folk)
]

# Melody patterns for different moods
MELODY_PATTERNS = {
    "happy": [
        [0, 2, 4, 5, 4, 2, 0, 2],
        [0, 4, 2, 5, 4, 2, 4, 0],
        [4, 5, 4, 2, 0, 2, 4, 5],
    ],
    "playful": [
        [0, 2, 4, 7, 4, 2, 0, -1],
        [4, 2, 0, 2, 4, 5, 7, 4],
        [0, 4, 0, 4, 2, 5, 2, 0],
    ],
    "calm": [
        [0, 2, 4, 2, 0, -1, 0, 2],
        [4, 2, 0, 2, 4, 2, 0, -3],
        [0, 2, 0, -1, 0, 2, 4, 2],
    ],
    "energetic": [
        [0, 4, 7, 4, 0, 4, 7, 9],
        [7, 4, 0, 4, 7, 9, 7, 4],
        [0, 2, 4, 5, 7, 5, 4, 2],
    ],
}


class MusicGenerator:
    """Generates background music for children's songs."""

    def __init__(self):
        """Initialize the music generator."""
        self.config = get_config()
        music_config = self.config.music
        self.key = music_config.get("key", "C_major")
        self.background_volume = music_config.get("background_volume", 0.3)
        self.intro_volume = music_config.get("intro_volume", 0.6)
        self.outro_volume = music_config.get("outro_volume", 0.4)
        self.tempo_bpm = self.config.songs.get("tempo_bpm", 100)
        self.scale = SCALES.get(self.key, SCALES["C_major"])

    def generate_full_track(self, song: SongLyrics, duration: float) -> np.ndarray:
        """Generate a complete background music track for a song.

        Args:
            song: SongLyrics instance with mood and tempo info.
            duration: Duration of the track in seconds.

        Returns:
            Numpy array of audio samples (mono, float32).
        """
        logger.info(f"Generating {duration:.1f}s music track (mood: {song.mood})")

        tempo = song.tempo_suggestion or self.tempo_bpm
        mood = song.mood if song.mood in MELODY_PATTERNS else "happy"

        # Generate individual layers
        melody = self._generate_melody(duration, mood, tempo)
        chords = self._generate_chords(duration, tempo)
        bass = self._generate_bass(duration, tempo)
        rhythm = self._generate_rhythm(duration, tempo)

        # Mix all layers together
        track = self._mix_layers(
            [melody, chords, bass, rhythm],
            [0.4, 0.3, 0.2, 0.15],
            duration,
        )

        # Apply volume
        track = track * self.background_volume

        logger.info(f"Generated music track: {len(track)} samples")
        return track

    def generate_intro_jingle(self, duration: float = 3.0) -> np.ndarray:
        """Generate a short intro jingle.

        Args:
            duration: Duration in seconds (default 3).

        Returns:
            Numpy array of audio samples.
        """
        logger.info(f"Generating intro jingle ({duration}s)")

        num_samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)

        # Ascending arpeggio with xylophone timbre
        notes = ["C5", "E5", "G5", "C6"]
        note_duration = duration / len(notes)
        jingle = np.zeros(num_samples, dtype=np.float32)

        for i, note in enumerate(notes):
            freq = NOTE_FREQUENCIES.get(note, 523.25)
            start = int(i * note_duration * SAMPLE_RATE)
            end = int((i + 1) * note_duration * SAMPLE_RATE)
            end = min(end, num_samples)
            length = end - start

            note_t = np.linspace(0, note_duration, length, dtype=np.float32)
            # Xylophone-like timbre (fundamental + harmonics with decay)
            tone = (
                np.sin(2 * np.pi * freq * note_t) * 0.6
                + np.sin(2 * np.pi * freq * 2 * note_t) * 0.3
                + np.sin(2 * np.pi * freq * 3 * note_t) * 0.1
            )
            # Quick attack, medium decay
            envelope = np.exp(-3.0 * note_t)
            jingle[start:end] += tone * envelope

        # Add a sparkle effect
        sparkle_freq = NOTE_FREQUENCIES["C6"]
        sparkle = np.sin(2 * np.pi * sparkle_freq * t) * 0.1
        sparkle *= np.exp(-2.0 * t)
        jingle += sparkle

        # Normalize and apply volume
        max_val = np.max(np.abs(jingle))
        if max_val > 0:
            jingle = jingle / max_val
        jingle *= self.intro_volume

        return jingle

    def generate_outro_music(self, duration: float = 5.0) -> np.ndarray:
        """Generate outro music with a gentle fadeout.

        Args:
            duration: Duration in seconds (default 5).

        Returns:
            Numpy array of audio samples.
        """
        logger.info(f"Generating outro music ({duration}s)")

        num_samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)

        # Descending arpeggio
        notes = ["C6", "G5", "E5", "C5", "G4", "E4", "C4"]
        note_duration = duration / len(notes)
        outro = np.zeros(num_samples, dtype=np.float32)

        for i, note in enumerate(notes):
            freq = NOTE_FREQUENCIES.get(note, 261.63)
            start = int(i * note_duration * SAMPLE_RATE)
            end = int((i + 1) * note_duration * SAMPLE_RATE)
            end = min(end, num_samples)
            length = end - start

            note_t = np.linspace(0, note_duration, length, dtype=np.float32)
            # Bell-like timbre
            tone = (
                np.sin(2 * np.pi * freq * note_t) * 0.5
                + np.sin(2 * np.pi * freq * 2.0 * note_t) * 0.3
                + np.sin(2 * np.pi * freq * 3.0 * note_t) * 0.15
                + np.sin(2 * np.pi * freq * 4.0 * note_t) * 0.05
            )
            envelope = np.exp(-2.0 * note_t)
            outro[start:end] += tone * envelope

        # Add gentle pad underneath
        pad_freq = NOTE_FREQUENCIES["C4"]
        pad = np.sin(2 * np.pi * pad_freq * t) * 0.15
        pad += np.sin(2 * np.pi * pad_freq * 1.5 * t) * 0.1  # Fifth
        outro += pad

        # Apply fadeout
        fadeout = np.linspace(1.0, 0.0, num_samples, dtype=np.float32)
        outro *= fadeout

        # Normalize and apply volume
        max_val = np.max(np.abs(outro))
        if max_val > 0:
            outro = outro / max_val
        outro *= self.outro_volume

        return outro

    def _generate_melody(
        self, duration: float, mood: str, tempo: int
    ) -> np.ndarray:
        """Generate a xylophone-timbre melody line.

        Args:
            duration: Duration in seconds.
            mood: Mood for melody pattern selection.
            tempo: Tempo in BPM.

        Returns:
            Numpy array of melody audio.
        """
        num_samples = int(SAMPLE_RATE * duration)
        melody = np.zeros(num_samples, dtype=np.float32)

        beat_duration = 60.0 / tempo
        note_duration = beat_duration * 0.8  # Slight staccato

        patterns = MELODY_PATTERNS.get(mood, MELODY_PATTERNS["happy"])
        pattern = random.choice(patterns)

        # Get base octave notes from scale
        base_notes = []
        for note_name in self.scale:
            key = f"{note_name}5"
            if key in NOTE_FREQUENCIES:
                base_notes.append(NOTE_FREQUENCIES[key])
            else:
                # Try octave 4
                key4 = f"{note_name}4"
                if key4 in NOTE_FREQUENCIES:
                    base_notes.append(NOTE_FREQUENCIES[key4])

        if not base_notes:
            base_notes = [523.25, 587.33, 659.25, 698.46, 783.99, 880.00, 987.77]

        current_time = 0.0
        pattern_idx = 0

        while current_time < duration:
            # Get scale degree from pattern
            degree = pattern[pattern_idx % len(pattern)]
            # Clamp to available notes
            note_idx = degree % len(base_notes)
            freq = base_notes[note_idx]

            start = int(current_time * SAMPLE_RATE)
            length = int(note_duration * SAMPLE_RATE)
            end = min(start + length, num_samples)
            actual_length = end - start

            if actual_length > 0:
                note_t = np.linspace(0, note_duration, actual_length, dtype=np.float32)
                # Xylophone timbre: strong fundamental with metallic harmonics
                tone = (
                    np.sin(2 * np.pi * freq * note_t) * 0.5
                    + np.sin(2 * np.pi * freq * 2 * note_t) * 0.25
                    + np.sin(2 * np.pi * freq * 3 * note_t) * 0.15
                    + np.sin(2 * np.pi * freq * 5.43 * note_t) * 0.1  # Inharmonic partial
                )
                # Sharp attack, quick decay (xylophone envelope)
                envelope = np.exp(-5.0 * note_t)
                melody[start:end] += tone * envelope

            current_time += beat_duration
            pattern_idx += 1

            # Occasionally add variation
            if pattern_idx % len(pattern) == 0:
                pattern = random.choice(patterns)

        return melody

    def _generate_chords(self, duration: float, tempo: int) -> np.ndarray:
        """Generate piano chord accompaniment.

        Args:
            duration: Duration in seconds.
            tempo: Tempo in BPM.

        Returns:
            Numpy array of chord audio.
        """
        num_samples = int(SAMPLE_RATE * duration)
        chords = np.zeros(num_samples, dtype=np.float32)

        # Each chord lasts 2 beats
        chord_duration = (60.0 / tempo) * 2
        progression = random.choice(CHILDREN_PROGRESSIONS)

        # Map scale degrees to frequencies (octave 4)
        scale_freqs = []
        for note_name in self.scale:
            key = f"{note_name}4"
            if key in NOTE_FREQUENCIES:
                scale_freqs.append(NOTE_FREQUENCIES[key])
            else:
                scale_freqs.append(261.63)  # Default C4

        current_time = 0.0
        chord_idx = 0

        while current_time < duration:
            degree = progression[chord_idx % len(progression)] - 1  # 0-indexed
            root_idx = degree % len(scale_freqs)

            # Build major triad (root, third, fifth)
            root_freq = scale_freqs[root_idx]
            third_freq = scale_freqs[(root_idx + 2) % len(scale_freqs)]
            fifth_freq = scale_freqs[(root_idx + 4) % len(scale_freqs)]

            start = int(current_time * SAMPLE_RATE)
            length = int(chord_duration * SAMPLE_RATE)
            end = min(start + length, num_samples)
            actual_length = end - start

            if actual_length > 0:
                chord_t = np.linspace(0, chord_duration, actual_length, dtype=np.float32)
                # Piano-like timbre
                chord_tone = np.zeros(actual_length, dtype=np.float32)
                for freq in [root_freq, third_freq, fifth_freq]:
                    chord_tone += (
                        np.sin(2 * np.pi * freq * chord_t) * 0.3
                        + np.sin(2 * np.pi * freq * 2 * chord_t) * 0.1
                        + np.sin(2 * np.pi * freq * 3 * chord_t) * 0.05
                    )
                # Piano envelope: quick attack, slow decay
                envelope = np.exp(-1.5 * chord_t)
                envelope[:min(100, actual_length)] = np.linspace(
                    0, 1, min(100, actual_length)
                )
                chords[start:end] += chord_tone * envelope

            current_time += chord_duration
            chord_idx += 1

        return chords

    def _generate_bass(self, duration: float, tempo: int) -> np.ndarray:
        """Generate bass line.

        Args:
            duration: Duration in seconds.
            tempo: Tempo in BPM.

        Returns:
            Numpy array of bass audio.
        """
        num_samples = int(SAMPLE_RATE * duration)
        bass = np.zeros(num_samples, dtype=np.float32)

        beat_duration = 60.0 / tempo
        # Bass plays on beats 1 and 3 (every 2 beats)
        bass_interval = beat_duration * 2

        progression = random.choice(CHILDREN_PROGRESSIONS)

        # Bass notes in octave 3
        scale_freqs = []
        for note_name in self.scale:
            key = f"{note_name}3"
            if key in NOTE_FREQUENCIES:
                scale_freqs.append(NOTE_FREQUENCIES[key])
            else:
                scale_freqs.append(130.81)  # Default C3

        current_time = 0.0
        chord_idx = 0
        beats_per_chord = 4
        beat_count = 0

        while current_time < duration:
            degree = progression[chord_idx % len(progression)] - 1
            root_idx = degree % len(scale_freqs)
            freq = scale_freqs[root_idx]

            start = int(current_time * SAMPLE_RATE)
            length = int(bass_interval * 0.8 * SAMPLE_RATE)
            end = min(start + length, num_samples)
            actual_length = end - start

            if actual_length > 0:
                bass_t = np.linspace(0, bass_interval * 0.8, actual_length, dtype=np.float32)
                # Simple bass tone
                tone = (
                    np.sin(2 * np.pi * freq * bass_t) * 0.7
                    + np.sin(2 * np.pi * freq * 2 * bass_t) * 0.2
                    + np.sin(2 * np.pi * freq * 0.5 * bass_t) * 0.1  # Sub harmonic
                )
                envelope = np.exp(-2.0 * bass_t)
                bass[start:end] += tone * envelope

            current_time += bass_interval
            beat_count += 2
            if beat_count >= beats_per_chord:
                beat_count = 0
                chord_idx += 1

        return bass

    def _generate_rhythm(self, duration: float, tempo: int) -> np.ndarray:
        """Generate a simple rhythm track (kick, clap, hihat).

        Args:
            duration: Duration in seconds.
            tempo: Tempo in BPM.

        Returns:
            Numpy array of rhythm audio.
        """
        num_samples = int(SAMPLE_RATE * duration)
        rhythm = np.zeros(num_samples, dtype=np.float32)

        beat_duration = 60.0 / tempo
        current_time = 0.0
        beat_count = 0

        while current_time < duration:
            start = int(current_time * SAMPLE_RATE)

            if beat_count % 4 == 0:
                # Kick drum (low frequency burst)
                kick_length = min(int(0.1 * SAMPLE_RATE), num_samples - start)
                if kick_length > 0:
                    kick_t = np.linspace(0, 0.1, kick_length, dtype=np.float32)
                    kick_freq = 80 * np.exp(-10 * kick_t)  # Pitch drops
                    kick = np.sin(2 * np.pi * kick_freq * kick_t) * np.exp(-15 * kick_t)
                    rhythm[start:start + kick_length] += kick * 0.4

            elif beat_count % 4 == 2:
                # Clap (noise burst)
                clap_length = min(int(0.05 * SAMPLE_RATE), num_samples - start)
                if clap_length > 0:
                    clap_t = np.linspace(0, 0.05, clap_length, dtype=np.float32)
                    clap = np.random.randn(clap_length).astype(np.float32) * np.exp(-20 * clap_t)
                    rhythm[start:start + clap_length] += clap * 0.2

            # Hi-hat on every beat
            hihat_length = min(int(0.02 * SAMPLE_RATE), num_samples - start)
            if hihat_length > 0:
                hihat_t = np.linspace(0, 0.02, hihat_length, dtype=np.float32)
                hihat = np.random.randn(hihat_length).astype(np.float32) * np.exp(-50 * hihat_t)
                rhythm[start:start + hihat_length] += hihat * 0.1

            current_time += beat_duration
            beat_count += 1

        return rhythm

    def _mix_layers(
        self,
        layers: List[np.ndarray],
        volumes: List[float],
        duration: float,
    ) -> np.ndarray:
        """Mix multiple audio layers together.

        Args:
            layers: List of audio numpy arrays.
            volumes: Volume multiplier for each layer.
            duration: Target duration in seconds.

        Returns:
            Mixed audio numpy array.
        """
        num_samples = int(SAMPLE_RATE * duration)
        mixed = np.zeros(num_samples, dtype=np.float32)

        for layer, volume in zip(layers, volumes):
            if len(layer) >= num_samples:
                mixed += layer[:num_samples] * volume
            else:
                mixed[:len(layer)] += layer * volume

        # Normalize to prevent clipping
        max_val = np.max(np.abs(mixed))
        if max_val > 0.95:
            mixed = mixed * (0.95 / max_val)

        return mixed

    def _save_wav(self, audio: np.ndarray, output_path: str) -> str:
        """Save audio numpy array as a WAV file.

        Args:
            audio: Numpy array of audio samples (float32, -1.0 to 1.0).
            output_path: Path to save the WAV file.

        Returns:
            Path to the saved WAV file.
        """
        output_path = str(output_path)
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
