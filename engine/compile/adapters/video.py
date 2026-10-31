"""Video → evidence: the clip downloaded on this PC, its narration, and keyframes where the screen changes.

Downloads go to cache/ (gitignored): the video is the author's, we only link to it. YouTube rate-limits captions, so
they are tried first but never fail the job: Transcribe on the clip's audio is the fallback. Needs yt-dlp and
imageio-ffmpeg (`pip install "engine[compile]"`).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Optional

from engine import config
from engine.compile.adapters import SourceError
from engine.compile.timeline import Evidence, Item

SOURCES = config.CACHE / "sources"
FRAME_W = 1280
DIFF_W, DIFF_H = 320, 180
PIXEL_DELTA = 12             # a grey level change this big counts as a changed pixel
BUSY_SHARE = 0.25            # a pixel changing in this share of all seconds is a webcam or video, not the steps
SETTLED_SHARE = 0.0003
MAX_GAP_S = 60               # keep a frame at least this often
TYPING_GAP_S = 6             # or this often while the screen keeps changing
MIN_GAP_S = 2
START_SHARE = 0.002          # share of the screen that must change; raised until the frames fit
CHUNK_S = 570                # Transcribe takes at most 10 minutes per request
WAV_RATE = 16000


def seconds(t: Optional[str]) -> Optional[float]:
    """'10:30', '1:02:03' or '630' → seconds."""
    if t in (None, ""):
        return None
    out = 0.0
    for p in str(t).split(":"):
        out = out * 60 + float(p)
    return out


def ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except ImportError as e:
        raise SourceError('Reading videos needs ffmpeg: pip install "engine[compile]"') from e
    return imageio_ffmpeg.get_ffmpeg_exe()


def _ffmpeg_folder() -> Optional[str]:
    """yt-dlp only accepts a binary literally named ffmpeg, and imageio-ffmpeg's isn't, so keep a copy under cache/."""
    if shutil.which("ffmpeg"):
        return None
    src = Path(ffmpeg_exe())
    folder = config.CACHE / "bin"
    dst = folder / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
    return str(folder)


def _ydl():
    try:
        import yt_dlp
        from yt_dlp.utils import download_range_func
    except ImportError as e:
        raise SourceError('Reading video links needs yt-dlp: pip install "engine[compile]"') from e
    return yt_dlp, download_range_func


def clip_path(url: str, start: Optional[float], end: Optional[float], out_root: Path = SOURCES) -> Path:
    """Where that clip of that video is kept on this PC."""
    return out_root / hashlib.sha256(f"{url}|{start}|{end}".encode()).hexdigest()[:12] / "video.mp4"


def download(url: str, start: Optional[float], end: Optional[float], out_root: Path = SOURCES) -> tuple[Path, dict]:
    """The clip and its details. A clip already downloaded is reused."""
    yt_dlp, ranges = _ydl()
    location = _ffmpeg_folder()
    video = clip_path(url, start, end, out_root)
    folder = video.parent
    details = folder / "details.json"
    if video.exists() and details.exists():
        return video, json.loads(details.read_text(encoding="utf-8"))
    opts = {"format": "bv*[height<=1080][vcodec^=avc1]+ba[acodec^=mp4a]/b[height<=1080][ext=mp4]/b",
            "merge_output_format": "mp4", "outtmpl": {"default": str(folder / "video.%(ext)s")},
            "noplaylist": True, "quiet": True, "no_warnings": True}
    if location:
        opts["ffmpeg_location"] = location
    if start is not None or end is not None:
        opts["download_ranges"] = ranges(None, [(start or 0, end if end is not None else float("inf"))])
        opts["force_keyframes_at_cuts"] = True
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        raise SourceError(f"Couldn't download that video ({e.__class__.__name__}). You can drop the video file here instead.") from e
    d = {k: info.get(k) for k in ("id", "title", "uploader", "upload_date", "duration")}
    details.write_text(json.dumps(d), encoding="utf-8")
    return video, d


def parse_vtt(text: str) -> list[dict]:
    """Timed lines from captions. Auto-captions roll: each cue repeats the last, so only new lines are kept."""
    turns, last = [], None
    for m in re.finditer(r"(\d+):(\d\d):(\d\d)\.\d+ --> (\d+):(\d\d):(\d\d)\.\d+[^\n]*\n(.*?)(?:\n\n|\Z)", text, re.S):
        h1, m1, s1, h2, m2, s2, body = m.groups()
        start = int(h1) * 3600 + int(m1) * 60 + int(s1)
        end = int(h2) * 3600 + int(m2) * 60 + int(s2)
        for line in body.splitlines():
            line = re.sub(r"<[^>]+>", "", line).strip()
            if line and line != last:
                turns.append({"t": float(start), "end": float(end), "text": line})
                last = line
    return turns


def captions(url: str, start: Optional[float], end: Optional[float], folder: Path) -> list[dict]:
    """Timed lines in original-video time, or [] whenever they can't be had."""
    yt_dlp, _ = _ydl()
    opts = {"skip_download": True, "writesubtitles": True, "writeautomaticsub": True, "subtitleslangs": ["en"],
            "subtitlesformat": "vtt", "outtmpl": {"default": str(folder / "captions.%(ext)s")}, "noplaylist": True,
            "quiet": True, "no_warnings": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception:
        return []
    found = next(iter(sorted(folder.glob("captions*.vtt"))), None)
    if not found:
        return []
    lo, hi = start or 0, end if end is not None else float("inf")
    return [t for t in parse_vtt(found.read_text(encoding="utf-8", errors="replace")) if lo <= t["t"] <= hi]


def audio_chunks(video: Path) -> list[tuple[float, bytes]]:
    """(seconds from the clip's start, mono 16-bit WAV), each short enough for one Transcribe request."""
    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(WAV_RATE),
                          "-c:a", "pcm_s16le", "-map_metadata", "-1", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    per_chunk = CHUNK_S * WAV_RATE * 2
    out = []
    for i in range(0, len(raw), per_chunk):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(WAV_RATE)
            w.writeframes(raw[i:i + per_chunk])
        out.append((i / (WAV_RATE * 2), buf.getvalue()))
    return out


def transcribe(video: Path, offset: float, client) -> list[dict]:
    """Narration turns from Transcribe, in original-video time."""
    turns = []
    for at, wav in audio_chunks(video):
        got = client.transcribe(wav, tag="compile-narration")
        for turn in got.turns:
            if turn.get("transcript"):
                turns.append({"t": offset + at + turn.get("startMs", 0) / 1000,
                              "end": offset + at + turn.get("endMs", 0) / 1000, "text": turn["transcript"].strip()})
    return turns


def _grey_frames(video: Path):
    """One small grey frame per second, as a numpy array."""
    import numpy as np

    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", str(video), "-vf", f"fps=1,scale={DIFF_W}:{DIFF_H},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, DIFF_H, DIFF_W)


def pick_keyframes(changes: list[float], settled: list[bool], share: float, min_gap: int = MIN_GAP_S,
                   typing_gap: int = TYPING_GAP_S, max_gap: int = MAX_GAP_S) -> list[int]:
    """Which seconds to keep. `changes[i]` = how much of the screen differs from the second before. A frame is kept
    once enough has changed and the screen has come to rest, or after `typing_gap` if it never rests. A screen that
    doesn't change gets a frame only every `max_gap`: someone talking over a still screen needs no more."""
    kept = [0] if changes else []
    since = 0.0
    for i in range(1, len(changes)):
        since += changes[i]
        gap = i - kept[-1]
        ready = since >= share and ((gap >= min_gap and settled[i]) or gap >= typing_gap)
        if ready or gap >= max_gap:
            kept.append(i)
            since = 0.0
    return kept


def keyframe_times(frames, max_frames: int) -> list[int]:
    """Seconds where the screen has changed and come to rest; the threshold rises until the frames fit. Pixels that
    change most of the time (a webcam corner, a playing video) say nothing about the steps, so they don't count."""
    import numpy as np

    n = len(frames)
    if n == 0:
        return []
    grey = np.asarray(frames, dtype=np.int16)
    moved = np.abs(grey[1:] - grey[:-1]) > PIXEL_DELTA if n > 1 else np.zeros((0, *grey.shape[1:]), dtype=bool)
    busy = moved.mean(axis=0) > BUSY_SHARE if n > 1 else np.zeros(grey.shape[1:], dtype=bool)
    between = [0.0] + [float(m[~busy].mean()) for m in moved]
    settled = [(between[i + 1] if i + 1 < n else 0.0) < SETTLED_SHARE for i in range(n)]
    share = START_SHARE
    while True:
        kept = pick_keyframes(between, settled, share)
        if n - 1 not in kept and n > 1:
            kept.append(n - 1)   # how it ends
        if len(kept) <= max_frames or share > 1:
            return kept[:max_frames]
        share *= 1.3


def grab_jpeg(video: Path, at: float, width: int = FRAME_W) -> bytes:
    return subprocess.run([ffmpeg_exe(), "-v", "error", "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1",
                           "-vf", f"scale={width}:-2", "-q:v", "4", "-f", "image2", "-c:v", "mjpeg", "-"],
                          capture_output=True, check=True).stdout


def from_video(video: Path, *, client, url: Optional[str] = None, offset: float = 0.0, end: Optional[float] = None,
               turns: Optional[list[dict]] = None, details: Optional[dict] = None, max_frames: int = 150,
               progress=lambda note: None) -> Evidence:
    """`offset` = where the clip starts in the original video, so every time is the original's."""
    video = Path(video)
    if not video.exists():
        raise SourceError(f"No video file at {video}.")
    progress("Finding the moments the screen changes")
    times = keyframe_times(_grey_frames(video), max_frames)
    items = [Item("image", t=offset + t, image=grab_jpeg(video, t)) for t in times]
    if turns is None:
        progress("Transcribing the narration")
        turns = transcribe(video, offset, client)
    items += [Item("narration", x["text"], t=x["t"], end=x.get("end")) for x in turns]
    d = details or {}
    pub = d.get("upload_date")
    first = offset
    last = end if end is not None else offset + (d.get("duration") or (times[-1] if times else 0))
    key = hashlib.sha256(f"{url or video.name}|{offset}|{end}".encode()).hexdigest()[:16]
    notes = [] if turns else ["no narration found: frames only"]
    return Evidence(type="video", hash=key, items=items, url=url, title=d.get("title"), author=d.get("uploader"),
                    published=f"{pub[:4]}-{pub[4:6]}-{pub[6:]}" if pub else None,
                    segment=f"{_clock(first)}-{_clock(last)}" if offset or end is not None else None, notes=notes)


def _clock(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def from_url(url: str, *, client, start: Optional[str] = None, end: Optional[str] = None, narration: str = "auto",
             max_frames: int = 150, progress=lambda note: None) -> Evidence:
    lo, hi = seconds(start), seconds(end)
    progress("Downloading the video")
    video, details = download(url, lo, hi)
    turns = None
    if narration in ("auto", "captions"):
        progress("Reading the captions")
        turns = captions(url, lo, hi, video.parent) or None
    if narration == "transcribe":
        turns = None
    return from_video(video, client=client, url=url, offset=lo or 0.0, end=hi, turns=turns, details=details,
                      max_frames=max_frames, progress=progress)
