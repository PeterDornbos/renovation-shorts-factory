"""Render six supplied scene images with sample-aligned narration and captions."""
import argparse
import json
import math
from pathlib import Path
import resource
import subprocess
import tempfile
import textwrap
import time

try:
    from .video_manifest import load_manifest, local_asset
except ImportError:
    from video_manifest import load_manifest, local_asset

WIDTH, HEIGHT, FPS = 1080, 1920, 30
TRANSITION = 0.25


def run(command, cwd=None):
    subprocess.run(command, cwd=cwd, check=True)


def probe(path):
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-show_chapters",
        "-of", "json", str(path)], text=True))


def validate_timeline(timeline, manifest, duration):
    if not isinstance(timeline, list) or len(timeline) != 6:
        raise ValueError("Timeline must have six scenes")
    previous = 0.0
    for i, (entry, scene) in enumerate(zip(timeline, manifest["scenes"])):
        if any(type(entry.get(edge)) not in (float, int) or not math.isfinite(entry[edge]) for edge in ("start", "end")):
            raise ValueError("Scene times must be finite numbers")
        if (entry["scene"] != i + 1 or entry["narration"] != scene["narration"]
                or entry["image"] != scene["image"]):
            raise ValueError("Timeline and manifest do not match")
        if abs(entry["start"] - previous) > 0.001 or entry["end"] - entry["start"] < 0.6:
            raise ValueError("Scene timing must be contiguous and at least 0.6 seconds long")
        previous = entry["end"]
    if abs(previous - duration) > 0.002 or not 1 <= duration <= 60:
        raise ValueError("Timeline duration must match the complete narration (1–60s)")


def ass_time(seconds):
    ticks = round(seconds * 100)
    return f"{ticks // 360000}:{ticks // 6000 % 60:02}:{ticks // 100 % 60:02}.{ticks % 100:02}"


def write_captions(path, timeline):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H70000000,-1,0,0,0,100,100,0,0,3,3,0,2,90,90,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for entry in timeline:
        wrapped = textwrap.wrap(entry["narration"], width=27, break_long_words=False)
        if len(wrapped) > 4 or any(len(line) > 32 for line in wrapped):
            raise ValueError("Scene narration is too long for readable captions; use shorter wording")
        text = r"\N".join(wrapped)
        lines.append(f"Dialogue: 0,{ass_time(entry['start'])},{ass_time(entry['end'])},Default,,0,0,0,,{text}")
    path.write_text(header + "\n".join(lines) + "\n")


def validate_output(path, timeline, duration):
    info = probe(path)
    video = [s for s in info["streams"] if s["codec_type"] == "video"]
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    if (len(video) != 1 or video[0]["codec_name"] != "h264"
            or (video[0]["width"], video[0]["height"]) != (WIDTH, HEIGHT)):
        raise ValueError("Output must have one 1080×1920 video track")
    if len(audio) != 1 or audio[0]["codec_name"] != "aac":
        raise ValueError("Output must have one AAC narration track")
    actual = float(info["format"]["duration"])
    if not 1 <= actual <= 60.1 or abs(actual - duration) > 0.15:
        raise ValueError("Video duration does not match the complete narration")
    if abs(float(audio[0]["duration"]) - duration) > 0.15:
        raise ValueError("Audio track duration does not match narration")
    chapters = info.get("chapters", [])
    if len(chapters) != 6:
        raise ValueError("Output must contain six scene chapters")
    for i, (chapter, entry) in enumerate(zip(chapters, timeline)):
        if chapter.get("tags", {}).get("title") != f"Scene {i + 1}":
            raise ValueError("Scene chapter identity is incorrect")
        if any(abs(float(chapter[f"{edge}_time"]) - entry[edge]) > 0.01 for edge in ("start", "end")):
            raise ValueError("Scene chapter timings do not match narration")
    # Exercise the entire encoded file, not only the container metadata.
    run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"])
    return {"scene_count": 6, "width": WIDTH, "height": HEIGHT,
            "audio_codec": audio[0]["codec_name"], "duration_seconds": actual,
            "full_decode": "passed", "bytes": path.stat().st_size}


def render(manifest_path, narration, timeline_path, output_dir):
    from PIL import Image, ImageOps
    manifest_path = Path(manifest_path).resolve()
    manifest = load_manifest(manifest_path, check_assets=True)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    narration = Path(narration).resolve()
    timeline = json.loads(Path(timeline_path).read_text())
    duration = float(probe(narration)["format"]["duration"])
    validate_timeline(timeline, manifest, duration)
    metrics = {"status": "failed", "target_duration_seconds": manifest["target_duration_seconds"],
               "narration_duration_seconds": duration, "transition_seconds": TRANSITION,
               "caption_alignment": "exact scene intervals, not word-level alignment"}
    started = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory(prefix="short-render-") as tmp:
            work = Path(tmp)
            write_captions(work / "captions.ass", timeline)
            metadata = [";FFMETADATA1"]
            for i, entry in enumerate(timeline):
                metadata += ["[CHAPTER]", "TIMEBASE=1/1000",
                             f"START={round(entry['start'] * 1000)}",
                             f"END={round(entry['end'] * 1000)}", f"title=Scene {i + 1}"]
            (work / "chapters.txt").write_text("\n".join(metadata) + "\n")
            command = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-y", "-filter_complex_threads", "1"]
            filters = []
            for i, (scene, entry) in enumerate(zip(manifest["scenes"], timeline)):
                image = local_asset(manifest_path, scene["image"])
                with Image.open(image) as source:
                    ImageOps.exif_transpose(source).convert("RGB").save(work / f"scene{i}.png")
                # Overlap around audio boundaries; total picture length still equals narration.
                length = entry["end"] - entry["start"] + TRANSITION / 2 * ((i > 0) + (i < 5))
                command += ["-loop", "1", "-framerate", str(FPS), "-t", str(length + 1 / FPS), "-i", f"scene{i}.png"]
                filters.append(f"[{i}:v]scale={WIDTH}:{HEIGHT},setsar=1,format=yuv420p,settb=AVTB[v{i}]")
            command += ["-i", str(narration)]
            command += ["-f", "ffmetadata", "-i", "chapters.txt"]
            last = "v0"
            for i in range(1, 6):
                label = f"fade{i}"
                offset = timeline[i]["start"] - TRANSITION / 2
                filters.append(f"[{last}][v{i}]xfade=transition=fade:duration={TRANSITION}:offset={offset}[{label}]")
                last = label
            filters.append(f"[{last}]ass=captions.ass,format=yuv420p[outv]")
            music = manifest.get("music")
            if music:
                command += ["-stream_loop", "-1", "-i", str(local_asset(manifest_path, music["path"]))]
                filters += [f"[8:a]volume={music.get('volume', 0.10)}[music]",
                            "[6:a][music]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:latency=1[outa]"]
                audio_map = "[outa]"
            else:
                audio_map = "6:a:0"
            command += ["-filter_complex", ";".join(filters), "-map", "[outv]", "-map", audio_map,
                        "-map_metadata", "7", "-map_chapters", "7", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "20", "-threads", "2", "-r", str(FPS), "-c:a", "aac", "-b:a", "128k",
                        "-t", str(duration), "-movflags", "+faststart", str(output_dir / "renovation.mp4")]
            run(command, cwd=work)
            (output_dir / "captions.ass").write_text((work / "captions.ass").read_text())
            metrics["validation"] = validate_output(output_dir / "renovation.mp4", timeline, duration)
            low, high = manifest["target_duration_seconds"]
            metrics["duration_in_target"] = low <= duration <= high
            if not metrics["duration_in_target"]:
                metrics["warning"] = "Revise manifest narration wording to aim for 18–20s; speech was not clipped or stretched."
            metrics["music"] = music or None
            metrics["status"] = "passed"
            return metrics
    except Exception as exc:
        metrics["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        metrics["render_and_validation_seconds"] = time.perf_counter() - started
        metrics["python_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        metrics["subprocess_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
        (output_dir / "render_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/renovation.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/short"))
    parser.add_argument("--narration", type=Path, required=True)
    parser.add_argument("--timeline", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(render(args.manifest, args.narration, args.timeline, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
