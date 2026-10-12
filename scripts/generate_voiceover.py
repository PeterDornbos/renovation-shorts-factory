"""Generate a CPU-only Nano narration; retain diagnostics even on failure."""
import argparse
import json
import os
from pathlib import Path
import platform
import resource
import time

NARRATION = (
    "This dated kitchen is getting a fresh start. We're opening up the space, "
    "refinishing the cabinets, and adding warm lighting. New countertops and a "
    "clean backsplash bring it all together. Watch this renovation turn an everyday "
    "room into the heart of the home."
)


def validate_audio(wav, sample_rate):
    import torch
    if wav.ndim != 2 or wav.shape[0] != 1 or wav.shape[1] == 0:
        raise ValueError("Expected nonempty mono audio")
    if not torch.isfinite(wav).all() or wav.abs().max().item() == 0:
        raise ValueError("Audio is silent or contains nonfinite samples")
    return wav.shape[1] / sample_rate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/voiceover"))
    parser.add_argument("--threads", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics = {"status": "failed", "model": "ResembleAI/chatterbox-nano",
               "device": "cpu", "python": platform.python_version(),
               "cpu_count": os.cpu_count(), "threads": args.threads, "seed": args.seed,
               "text": NARRATION, "target_duration_seconds": [15, 20],
               "chatterbox_revision": "5de7a54aa4e5e2baadb0182dde554908b48b85c2"}
    started = time.perf_counter()
    try:
        import random
        import numpy as np
        import soundfile as sf
        import torch
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        random.seed(args.seed)
        np.random.seed(args.seed)
        torch.manual_seed(args.seed)
        torch.set_num_threads(args.threads)
        metrics["torch_version"] = torch.__version__
        loading = time.perf_counter()
        model = ChatterboxTurboTTS.from_pretrained(device="cpu", nano=True)
        metrics["model_load_seconds"] = time.perf_counter() - loading
        if model.conds is None:
            raise RuntimeError("Nano checkpoint lacks bundled voice conditioning")
        generating = time.perf_counter()
        with torch.inference_mode():
            wav = model.generate(NARRATION)
        metrics["generation_seconds"] = time.perf_counter() - generating
        duration = validate_audio(wav, model.sr)
        metrics.update(audio_duration_seconds=duration, sample_rate=model.sr,
                       realtime_factor=metrics["generation_seconds"] / duration)
        path = args.output_dir / "renovation.wav"
        sf.write(path, wav.squeeze(0).numpy(), model.sr, subtype="PCM_16")
        # Inspect the actual saved artifact, not just the in-memory tensor.
        saved = sf.info(path)
        if saved.frames != wav.shape[1] or saved.samplerate != model.sr:
            raise RuntimeError("Saved WAV does not match generated audio")
        metrics["wav_bytes"] = path.stat().st_size
        metrics["duration_in_target"] = 15 <= duration <= 20
        if not metrics["duration_in_target"]:
            raise RuntimeError(f"Narration is {duration:.2f}s; target is 15–20s. Review WAV and adjust text/pacing.")
        metrics["status"] = "passed"
    except Exception as exc:
        metrics["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        metrics["total_seconds"] = time.perf_counter() - started
        metrics["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        (args.output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
        print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
