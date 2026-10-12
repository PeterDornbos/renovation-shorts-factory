"""Validate supplied assets, synthesize narration, render and validate a Short."""
import argparse
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

try:
    from .video_manifest import load_manifest
except ImportError:
    from video_manifest import load_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/renovation.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/short"))
    parser.add_argument("--validate-only", action="store_true", help="Check manifest and assets without installing or loading Nano")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = args.manifest.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    metrics = {"status": "failed", "python": platform.python_version(), "manifest": str(manifest)}
    try:
        load_manifest(manifest, check_assets=True)
        (output / "manifest.json").write_text(manifest.read_text())
        if args.validate_only:
            metrics["status"] = "assets_validated"
            return
        for script, extra in (
            ("generate_voiceover.py", []),
            ("render_short.py", ["--narration", str(output / "renovation.wav"), "--timeline", str(output / "timeline.json")]),
        ):
            subprocess.run([sys.executable, str(root / "scripts" / script), "--manifest", str(manifest),
                            "--output-dir", str(output), *extra], cwd=root, check=True)
        metrics["status"] = "passed"
        metrics["duration_in_target"] = json.loads((output / "render_metrics.json").read_text())["duration_in_target"]
    except Exception as exc:
        metrics["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        metrics["total_seconds"] = time.perf_counter() - started
        metrics["python_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        metrics["subprocess_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
        (output / "pipeline_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")


if __name__ == "__main__":
    main()
