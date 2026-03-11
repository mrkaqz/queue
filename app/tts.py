import asyncio
import os
from pathlib import Path
from app.number_to_words import to_tts_text

AUDIO_DIR = Path(os.environ.get("QUEUE_DATA_DIR", Path(__file__).parent.parent / "data")) / "audio"


def _audio_path(number: int, language: str, voice: str) -> Path:
    safe_voice = voice.replace("-", "_").replace("+", "plus")
    return AUDIO_DIR / f"{number}_{language}_{safe_voice}.mp3"


async def get_or_generate(number: int, language: str, voice_th: str, voice_en: str) -> list[str]:
    """Return a list of audio file paths (relative to DATA_DIR parent) for playback.

    For 'th+en', returns two files [thai_path, english_path].
    For 'th' or 'en', returns one file.
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    async def generate(text: str, voice: str, path: Path):
        if path.exists():
            return
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(path))
        except Exception as e:
            print(f"[TTS] Error generating audio: {e}")

    paths = []

    if language in ("th", "th+en"):
        text_th = to_tts_text(number, "th")
        path_th = _audio_path(number, "th", voice_th)
        await generate(text_th, voice_th, path_th)
        if path_th.exists():
            paths.append(f"/audio/{path_th.name}")

    if language in ("en", "th+en"):
        text_en = to_tts_text(number, "en")
        path_en = _audio_path(number, "en", voice_en)
        await generate(text_en, voice_en, path_en)
        if path_en.exists():
            paths.append(f"/audio/{path_en.name}")

    return paths


async def warmup(numbers: list[int], language: str, voice_th: str, voice_en: str):
    """Pre-generate audio for a list of numbers (e.g., 1-100 on startup)."""
    tasks = [get_or_generate(n, language, voice_th, voice_en) for n in numbers]
    await asyncio.gather(*tasks)
