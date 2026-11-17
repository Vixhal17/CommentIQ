import io
import json
import logging
import re
import tempfile
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

import httpx
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

from backend.app.retrieval.transcript_loader import TranscriptSegment
from backend.app.retrieval.chunker import TranscriptChunker, Chunk
from backend.config.settings import settings

logger = logging.getLogger("yt_agent.youtube_transcriber")


class TranscriptResult(BaseModel):
    video_id: str
    title: str
    author: str
    source: str  # "youtube_captions" | "groq_whisper" | "fallback"
    raw_snippet_count: int
    chunks: List[Chunk]


class YouTubeTranscriber:
    """
    Two-Tier YouTube Video Transcriber:
    - Tier 1: Instant zero-cost caption extraction via YouTubeTranscriptApi.
    - Tier 2: Groq Whisper API (whisper-large-v3) audio transcription fallback when captions are disabled.
    """

    @staticmethod
    def extract_video_id(url_or_id: str) -> Optional[str]:
        """Extracts 11-character YouTube video ID from various URL patterns or plain ID."""
        if not url_or_id:
            return None
        cleaned = url_or_id.strip()

        # Plain 11-character ID
        if re.match(r"^[a-zA-Z0-9_-]{11}$", cleaned):
            return cleaned

        # Common YouTube URL patterns
        patterns = [
            r"(?:v=|\/v\/|embed\/|shorts\/|youtu\.be\/|\/e\/|watch\?v=|\&v=)([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def fetch_video_metadata(video_id: str) -> Dict[str, str]:
        """Fetches video title and channel name via lightweight YouTube oEmbed API."""
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        try:
            req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                return {
                    "title": data.get("title", f"YouTube Video {video_id}"),
                    "author": data.get("author_name", "YouTube Creator"),
                }
        except Exception as e:
            logger.warning(f"oEmbed metadata fetch failed for {video_id}: {e}")
            return {
                "title": f"YouTube Video ({video_id})",
                "author": "YouTube Creator",
            }

    @staticmethod
    def fetch_youtube_captions(video_id: str) -> Optional[List[TranscriptSegment]]:
        """Tier 1: Fetches official or auto-generated English captions via YouTubeTranscriptApi."""
        try:
            api = YouTubeTranscriptApi()
            # Try fetching standard captions
            snippets = api.fetch(video_id)
            if snippets:
                segments = []
                for s in snippets:
                    text = getattr(s, "text", "") or ""
                    start = float(getattr(s, "start", 0.0))
                    text_clean = text.strip()
                    if text_clean and not text_clean.startswith("[Music]"):
                        segments.append(TranscriptSegment(start_time=start, text=text_clean))
                if segments:
                    logger.info(f"Successfully extracted {len(segments)} caption snippets for {video_id}")
                    return segments
        except Exception as e:
            logger.info(f"YouTube captions unavailable for {video_id}: {e}. Proceeding to Tier 2 Whisper fallback.")
        return None

    @staticmethod
    def transcribe_audio_with_groq(
        video_id: str,
        groq_api_key: Optional[str] = None,
    ) -> Optional[List[TranscriptSegment]]:
        """
        Tier 2 Fallback: Downloads audio stream via yt-dlp and transcribes
        using Groq's high-speed Whisper Large v3 endpoint.
        """
        api_key = groq_api_key or settings.GROQ_API_KEY
        if not api_key or "your_" in api_key.lower():
            logger.warning("Groq API key not configured. Skipping Tier 2 Whisper audio transcription.")
            return None

        with tempfile.TemporaryDirectory() as tmpdir:
            out_template = str(Path(tmpdir) / f"{video_id}.%(ext)s")
            ydl_opts = {
                "format": "ba[ext=m4a]/ba[ext=mp3]/ba[ext=webm]/ba",
                "outtmpl": out_template,
                "quiet": True,
                "no_warnings": True,
                "max_filesize": 25 * 1024 * 1024,  # Groq 25MB audio limit
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            except Exception as dl_err:
                logger.error(f"yt-dlp audio download failed for {video_id}: {dl_err}")
                return None

            # Find downloaded audio file
            audio_files = list(Path(tmpdir).glob(f"{video_id}.*"))
            if not audio_files:
                logger.error(f"No audio file was created by yt-dlp for {video_id}")
                return None

            audio_path = audio_files[0]
            logger.info(f"Audio downloaded for {video_id} ({audio_path.stat().st_size} bytes). Calling Groq Whisper API...")

            try:
                whisper_url = "https://api.groq.com/openai/v1/audio/transcriptions"
                headers = {"Authorization": f"Bearer {api_key}"}

                with open(audio_path, "rb") as f:
                    files = {"file": (audio_path.name, f, "audio/m4a")}
                    data = {
                        "model": "whisper-large-v3",
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "segment",
                        "language": "en",
                    }
                    with httpx.Client(timeout=180.0) as client:
                        resp = client.post(whisper_url, headers=headers, files=files, data=data)
                        if resp.status_code != 200:
                            logger.error(f"Groq Whisper API returned {resp.status_code}: {resp.text}")
                            return None
                        result = resp.json()

                segments_data = result.get("segments", [])
                segments = []
                for s in segments_data:
                    start_time = float(s.get("start", 0.0))
                    text_str = str(s.get("text", "")).strip()
                    if text_str:
                        segments.append(TranscriptSegment(start_time=start_time, text=text_str))

                logger.info(f"Groq Whisper successfully transcribed {len(segments)} segments for {video_id}")
                return segments
            except Exception as whisper_err:
                logger.error(f"Groq Whisper transcription failed for {video_id}: {whisper_err}")
                return None

    @classmethod
    def transcribe(
        cls,
        url_or_id: str,
        groq_api_key: Optional[str] = None,
        chunk_target_chars: int = 800,
        chunk_overlap_chars: int = 120,
    ) -> TranscriptResult:
        """
        Full ingestion pipeline:
        1. Extract video ID.
        2. Fetch video title & creator via oEmbed.
        3. Attempt Tier 1 (YouTube Captions).
        4. If captions fail, attempt Tier 2 (Groq Whisper API).
        5. Aggregate into timestamped chunks with formatted [MM:SS] markers.
        """
        video_id = cls.extract_video_id(url_or_id)
        if not video_id:
            raise ValueError(f"Invalid YouTube URL or Video ID: '{url_or_id}'")

        metadata = cls.fetch_video_metadata(video_id)
        title = metadata["title"]
        author = metadata["author"]

        # 1. Try Tier 1: Captions
        segments = cls.fetch_youtube_captions(video_id)
        source = "youtube_captions"

        # 2. Try Tier 2: Groq Whisper Fallback
        if not segments:
            segments = cls.transcribe_audio_with_groq(video_id, groq_api_key=groq_api_key)
            source = "groq_whisper"

        if not segments:
            raise RuntimeError(
                f"Could not extract transcript for video '{video_id}'. "
                "No captions were found, and audio transcription could not be completed."
            )

        # 3. Chunk segments with timestamp preservation
        chunker = TranscriptChunker(target_chars=chunk_target_chars, overlap_chars=chunk_overlap_chars)
        raw_chunks = chunker.chunk_segments(segments)

        # Prepend [MM:SS] marker to every chunk text for consistent citation
        formatted_chunks = []
        for c in raw_chunks:
            timestamp_prefix = c.formatted_timestamp
            chunk_body = c.text
            if not chunk_body.startswith("["):
                full_text = f"{timestamp_prefix} {chunk_body}"
            else:
                full_text = chunk_body
            formatted_chunks.append(Chunk(text=full_text, start_time=c.start_time))

        return TranscriptResult(
            video_id=video_id,
            title=title,
            author=author,
            source=source,
            raw_snippet_count=len(segments),
            chunks=formatted_chunks,
        )
