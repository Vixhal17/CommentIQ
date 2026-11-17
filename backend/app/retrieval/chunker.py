from typing import List
from pydantic import BaseModel
from backend.app.retrieval.transcript_loader import TranscriptSegment

class Chunk(BaseModel):
    text: str
    start_time: float  # In seconds

    @property
    def formatted_timestamp(self) -> str:
        """Returns [MM:SS] formatted timestamp."""
        total_sec = int(self.start_time)
        minutes = total_sec // 60
        seconds = total_sec % 60
        return f"[{minutes:02d}:{seconds:02d}]"


class TranscriptChunker:
    """
    Splits transcript segments into chunks of ~300 tokens (~1200 chars)
    with ~15% overlap while preserving the start timestamp for grounding.
    """

    def __init__(self, target_chars: int = 1200, overlap_chars: int = 180):
        self.target_chars = target_chars
        self.overlap_chars = overlap_chars

    def chunk_segments(self, segments: List[TranscriptSegment]) -> List[Chunk]:
        if not segments:
            return []

        chunks: List[Chunk] = []
        current_texts: List[str] = []
        current_len: int = 0
        chunk_start_time: float = segments[0].start_time

        for seg in segments:
            seg_len = len(seg.text)
            if current_len + seg_len > self.target_chars and current_texts:
                # Emit current chunk
                combined_text = " ".join(current_texts)
                chunks.append(Chunk(text=combined_text, start_time=chunk_start_time))

                # Compute overlap for the next chunk
                overlap_text = ""
                overlap_tokens = []
                words = combined_text.split()
                # Take words from end until ~overlap_chars
                accum = 0
                for w in reversed(words):
                    accum += len(w) + 1
                    overlap_tokens.insert(0, w)
                    if accum >= self.overlap_chars:
                        break

                current_texts = [" ".join(overlap_tokens), seg.text]
                current_len = sum(len(t) for t in current_texts) + len(current_texts) - 1
                chunk_start_time = seg.start_time
            else:
                if not current_texts:
                    chunk_start_time = seg.start_time
                current_texts.append(seg.text)
                current_len += seg_len + 1

        if current_texts:
            chunks.append(Chunk(text=" ".join(current_texts), start_time=chunk_start_time))

        return chunks

