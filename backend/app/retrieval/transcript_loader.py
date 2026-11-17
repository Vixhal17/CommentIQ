import re
from pathlib import Path
from typing import List, Union
from pydantic import BaseModel

class TranscriptSegment(BaseModel):
    start_time: float  # Start time in seconds
    text: str


def parse_timestamp_to_seconds(ts_str: str) -> float:
    """
    Parses timestamp formats into float seconds:
    - "01:23" -> 83.0
    - "01:23:45" -> 5025.0
    - "00:01:23,450" (SRT format) -> 83.45
    - "00:01:23.450" -> 83.45
    """
    cleaned = ts_str.strip().replace(",", ".")
    parts = cleaned.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return float(minutes) * 60.0 + float(seconds)
    elif len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours) * 3600.0 + float(minutes) * 60.0 + float(seconds)
    return float(cleaned)


class TranscriptLoader:
    """
    Parses transcripts from .txt (with [MM:SS] timestamps) or standard .srt files.
    Never scrapes third-party videos; strictly processes user-provided transcripts.
    """

    TXT_TIMESTAMP_REGEX = re.compile(r"^\[?(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?)\]?\s*(.*)$")
    SRT_TIMECODE_REGEX = re.compile(r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})")

    def load_from_file(self, file_path: Union[str, Path]) -> List[TranscriptSegment]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Transcript file not found: {path}")

        suffix = path.suffix.lower()
        content = path.read_text(encoding="utf-8")

        if suffix == ".srt":
            return self._parse_srt(content)
        elif suffix in (".txt", ".transcript"):
            return self._parse_txt(content)
        else:
            raise ValueError(f"Unsupported transcript format '{suffix}'. Supported: .srt, .txt")

    def _parse_txt(self, content: str) -> List[TranscriptSegment]:
        segments: List[TranscriptSegment] = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            match = self.TXT_TIMESTAMP_REGEX.match(line)
            if match:
                ts_str, text = match.groups()
                seconds = parse_timestamp_to_seconds(ts_str)
                cleaned_text = text.strip()
                if cleaned_text:
                    segments.append(TranscriptSegment(start_time=seconds, text=cleaned_text))
            else:
                # Line without timestamp: append to previous segment if exists, else start at 0.0
                if segments:
                    segments[-1].text += " " + line
                else:
                    segments.append(TranscriptSegment(start_time=0.0, text=line))
        return segments

    def _parse_srt(self, content: str) -> List[TranscriptSegment]:
        segments: List[TranscriptSegment] = []
        blocks = re.split(r"\n\s*\n", content.strip())

        for block in blocks:
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue

            timecode_line_idx = -1
            for idx, l in enumerate(lines):
                if "-->" in l:
                    timecode_line_idx = idx
                    break

            if timecode_line_idx != -1:
                tc_match = self.SRT_TIMECODE_REGEX.search(lines[timecode_line_idx])
                if tc_match:
                    start_str = tc_match.group(1)
                    start_seconds = parse_timestamp_to_seconds(start_str)
                    subtitle_text = " ".join(lines[timecode_line_idx + 1:]).strip()
                    if subtitle_text:
                        segments.append(TranscriptSegment(start_time=start_seconds, text=subtitle_text))
        return segments

