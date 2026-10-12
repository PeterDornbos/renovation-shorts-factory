import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave

from PIL import Image

from scripts.render_short import render, validate_output, validate_timeline, write_captions
from scripts.video_manifest import load_manifest

ROOT = Path(__file__).resolve().parents[1]


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".test-assets-", dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "video.json"
        self.data = {"version": 1, "scenes": [
            {"image": f"{i}.png", "narration": f"Renovation scene {i + 1} looks bright and welcoming."}
            for i in range(6)]}
        self.save()

    def save(self):
        self.manifest.write_text(json.dumps(self.data))

    def assets(self):
        colors = [(220, 30, 30), (30, 220, 30), (30, 30, 220),
                  (220, 220, 30), (220, 30, 220), (30, 220, 220)]
        for i, color in enumerate(colors):
            Image.new("RGB", (90, 160), color).save(self.root / f"{i}.png")
        return colors

    def test_missing_wrong_ratio_duplicate_and_path_escape_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing supplied image"):
            load_manifest(self.manifest, check_assets=True)
        self.assets()
        Image.new("RGB", (100, 100), "red").save(self.root / "0.png")
        with self.assertRaisesRegex(ValueError, "9:16"):
            load_manifest(self.manifest, check_assets=True)
        self.assets()
        shutil.copyfile(self.root / "0.png", self.root / "1.png")
        with self.assertRaisesRegex(ValueError, "different scene"):
            load_manifest(self.manifest, check_assets=True)
        self.data["scenes"][0]["image"] = "../../../etc/passwd"
        self.save()
        with self.assertRaisesRegex(ValueError, "inside the repository"):
            load_manifest(self.manifest)

    def test_structure_and_music_license(self):
        self.data["scenes"].pop()
        self.save()
        with self.assertRaisesRegex(ValueError, "six scenes"):
            load_manifest(self.manifest)
        self.data["scenes"].append({"image": "5.png", "narration": "Another scene"})
        self.data["music"] = {"path": "music.wav"}
        self.save()
        with self.assertRaisesRegex(ValueError, "license"):
            load_manifest(self.manifest)

    def test_timeline_mismatch_and_unreadable_caption(self):
        timeline = [{"scene": i + 1, **s, "start": i * 3, "end": (i + 1) * 3}
                    for i, s in enumerate(self.data["scenes"])]
        validate_timeline(timeline, self.data, 18)
        timeline[1]["start"] += 0.1
        with self.assertRaisesRegex(ValueError, "contiguous"):
            validate_timeline(timeline, self.data, 18)
        timeline[0]["narration"] = "word " * 50
        with self.assertRaisesRegex(ValueError, "readable captions"):
            write_captions(self.root / "captions.ass", timeline)

    def test_preflight_failure_retains_metrics_without_synthesis(self):
        self.data["scenes"][0]["image"] = "missing.png"
        self.save()
        output = self.root / "preflight"
        result = subprocess.run([__import__("sys").executable, "scripts/produce_short.py",
                                 "--manifest", str(self.manifest), "--validate-only",
                                 "--output-dir", str(output)], cwd=ROOT, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        metrics = json.loads((output / "pipeline_metrics.json").read_text())
        self.assertEqual(metrics["status"], "failed")
        self.assertIn("Missing supplied image", metrics["error"])
        self.assertFalse((output / "renovation.wav").exists())

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is not installed")
    def test_real_1080_portrait_render_with_six_scenes_and_music(self):
        # Synthetic colors and tones are test fixtures only, never production defaults.
        colors = self.assets()
        wav = self.root / "narration.wav"
        import math
        import struct
        for name, seconds in (("narration.wav", 18), ("music.wav", 1)):
            with wave.open(str(self.root / name), "wb") as audio:
                audio.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                audio.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(i * 2 * math.pi * 440 / 24000)))
                                           for i in range(24000 * seconds)))
        self.data["music"] = {"path": "music.wav", "license": "Synthetic test tone", "volume": 0.10}
        self.save()
        timeline = [{"scene": i + 1, **s, "start": i * 3, "end": (i + 1) * 3}
                    for i, s in enumerate(self.data["scenes"])]
        timeline_path = self.root / "timeline.json"
        timeline_path.write_text(json.dumps(timeline))
        metrics = render(self.manifest, wav, timeline_path, self.root / "output")
        self.assertEqual(metrics["status"], "passed")
        self.assertTrue(metrics["duration_in_target"])
        self.assertEqual(metrics["validation"]["scene_count"], 6)
        video = self.root / "output" / "renovation.mp4"
        # Check each actual decoded scene midpoint uses its supplied image.
        for i, expected in enumerate(colors):
            pixels = subprocess.check_output([
                "ffmpeg", "-v", "error", "-ss", str(i * 3 + 1.5), "-i", str(video),
                "-vf", "crop=2:2:100:100", "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
            self.assertTrue(all(abs(a - b) < 15 for a, b in zip(pixels[:3], expected)))
        with self.assertRaisesRegex(ValueError, "duration"):
            validate_output(video, timeline, 17)
        # Exercise the direct narration-only audio mapping too.
        del self.data["music"]
        self.save()
        plain = render(self.manifest, wav, timeline_path, self.root / "plain")
        self.assertEqual(plain["status"], "passed")
        self.assertIsNone(plain["music"])


if __name__ == "__main__":
    unittest.main()
