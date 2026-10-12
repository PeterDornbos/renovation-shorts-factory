import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import torch
from scripts.generate_voiceover import main, validate_audio


class VoiceoverTests(unittest.TestCase):
    def test_duration_and_invalid_audio(self):
        self.assertEqual(validate_audio(torch.ones(1, 24000 * 17), 24000), 17)
        for wav in (torch.zeros(1, 10), torch.ones(10), torch.full((1, 10), float("nan"))):
            with self.assertRaises(ValueError):
                validate_audio(wav, 24000)

    def test_failed_import_retains_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sys, "argv", ["generate", "--output-dir", tmp]), patch.dict(sys.modules, {"chatterbox.tts_turbo": None}):
                with self.assertRaises(ModuleNotFoundError):
                    main()
            metrics = json.loads((Path(tmp) / "metrics.json").read_text())
            self.assertEqual(metrics["status"], "failed")
            self.assertIn("error", metrics)
            self.assertGreater(metrics["total_seconds"], 0)

    def test_generation_saves_wav_and_checks_duration(self):
        import soundfile as sf
        for seconds, expected in ((17, "passed"), (22, "failed")):
            with self.subTest(seconds=seconds), tempfile.TemporaryDirectory() as tmp:
                model = MagicMock(sr=24000)
                model.generate.return_value = torch.full((1, 24000 * seconds), 0.1)
                module = MagicMock()
                module.ChatterboxTurboTTS.from_pretrained.return_value = model
                with patch.object(sys, "argv", ["generate", "--output-dir", tmp]), patch.dict(sys.modules, {"chatterbox.tts_turbo": module}):
                    if expected == "failed":
                        with self.assertRaisesRegex(RuntimeError, "target is"):
                            main()
                    else:
                        main()
                module.ChatterboxTurboTTS.from_pretrained.assert_called_once_with(device="cpu", nano=True)
                self.assertEqual(sf.info(Path(tmp) / "renovation.wav").duration, seconds)
                metrics = json.loads((Path(tmp) / "metrics.json").read_text())
                self.assertEqual(metrics["status"], expected)
                self.assertEqual(metrics["duration_in_target"], expected == "passed")

    def test_cli_help_does_not_load_model(self):
        result = subprocess.run([sys.executable, "scripts/generate_voiceover.py", "--help"], capture_output=True)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
