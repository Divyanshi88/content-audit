"""Step 3 (optional): look inside the downloaded reels.

- transcribe speech with faster-whisper (local, free; handles Hindi/Hinglish/English)
- grab a few frames (hook at 0.5s, middle, end) so Claude can judge visuals/format
"""
import json
import subprocess
from pathlib import Path


def extract_frames(video: Path, out_dir: Path, duration_s=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    d = duration_s or 15
    frames = []
    for label, t in (("hook", 0.5), ("mid", d / 2), ("end", max(d - 1, 1))):
        target = out_dir / f"{video.stem}_{label}.jpg"
        if not target.exists():
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
                            "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(target)], check=False)
        if target.exists():
            frames.append(str(target))
    return frames


def transcribe_all(posts, out_dir: Path, model_size="small", limit=30):
    from faster_whisper import WhisperModel

    cache = out_dir / "transcripts.json"
    done = json.loads(cache.read_text()) if cache.exists() else {}
    model = None
    reels = [p for p in posts if p.get("video_file")][:limit]
    for i, p in enumerate(reels):
        if p["shortcode"] in done:
            continue
        if model is None:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(p["video_file"], vad_filter=True)
        text = " ".join(s.text.strip() for s in segments)
        done[p["shortcode"]] = {"language": info.language, "text": text}
        print(f"  transcribed {i + 1}/{len(reels)} {p['shortcode']} [{info.language}] {text[:60]!r}")
        cache.write_text(json.dumps(done, indent=2, ensure_ascii=False))
    return done


def analyze_media(data, out_dir: Path, transcribe=True, frames=True, limit=30):
    posts = data["posts"]
    transcripts = transcribe_all(posts, out_dir, limit=limit) if transcribe else {}
    for p in posts:
        t = transcripts.get(p["shortcode"])
        p["transcript"] = t["text"] if t else None
        p["spoken_language"] = t["language"] if t else None
        if frames and p.get("video_file"):
            p["frames"] = extract_frames(Path(p["video_file"]), out_dir / "frames", p.get("duration_s"))
    return data
