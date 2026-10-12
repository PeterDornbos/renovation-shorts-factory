# Renovation Shorts Factory

## Free CPU voiceover experiment

This manually triggered GitHub Actions workflow tests Resemble AI **Chatterbox Nano**
for a 15–20-second English renovation narration. It uses Python 3.11, open-source
local inference, and standard `ubuntu-24.04` CPU runners. No paid API, GPU, subscription,
video generation, upload, publishing, or schedule is configured.

### Run on GitHub

1. Merge this workflow into the default branch, then enable Actions if necessary.
2. Open **Actions → Test Chatterbox Nano voiceover → Run workflow**.
3. After completion, download `chatterbox-nano-voiceover-<run-id>` from the run's
   **Artifacts** section. It contains `renovation.wav` and `metrics.json`.
4. Listen to the WAV to assess naturalness, American English accent, pronunciation,
   and pacing. These subjective qualities are not established by a successful job.

Public repositories normally receive free standard hosted runners. Private repositories
consume the account's included Actions minutes and artifact allowance. Check those quotas
and avoid paid overages; this experiment does not guarantee unlimited free compute.
Artifacts expire after 14 days. Initial model/dependency downloads can take several minutes;
the job stops after 30 minutes. No Hugging Face token is configured for the public weights.

### Verified Nano API

The [official README](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/README.md),
[Nano example](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/example_tts_nano.py),
and [loader source](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/tts_turbo.py)
confirm that Nano uses the Turbo class with an explicit Nano flag:

```python
from chatterbox.tts_turbo import ChatterboxTurboTTS
model = ChatterboxTurboTTS.from_pretrained(device="cpu", nano=True)
wav = model.generate(text)
```

This is **not** the original `ChatterboxTTS` API. Nano is a 110M English model, downloaded
from `ResembleAI/chatterbox-nano`. The official Nano example uses the checkpoint's bundled
voice conditioning; no recording or voice cloning is needed here. The script fails clearly
if that conditioning is missing. It uses the default voice, targeting American English;
there is no invented accent parameter. Model outputs need listening review.

The Chatterbox source is pinned to the verified revision because earlier package releases
may not include Nano. CPU-only Torch/Torchaudio 2.6.0 are installed first and remain compatible
with upstream requirements. Upstream transitive dependencies (including Perth's `master`
reference) and model weights are not fully locked; future upstream changes may require
revalidation. See the [model card](https://huggingface.co/ResembleAI/chatterbox-nano) for
model licensing and limitations. Keep the built-in Perth audio watermark.

### Local/cloud development

Use the existing checkout; cloud tasks are already isolated and need no Git worktree.
On Linux with Python 3.11:

```bash
cd /path/to/renovation-shorts-factory
python3.11 -m venv .venv
source .venv/bin/activate
bash scripts/setup_voiceover.sh
python -m unittest discover -s tests -v
HF_HUB_DISABLE_XET=1 python scripts/generate_voiceover.py
```

Dependency installation needs GitHub, PyPI, and `download.pytorch.org`. Model loading needs
`huggingface.co` and its download hosts (including `cdn-lfs.huggingface.co`,
`cdn-lfs-us-1.huggingface.co`, and `cas-bridge.xethub.hf.co`). Restricted cloud environments
must permit those destinations. No long-running service is required.

Edit `NARRATION` in `scripts/generate_voiceover.py` to change the approximately 45-word
renovation script. Generation is seeded but may vary across hardware/library versions.
The script validates nonempty, finite, nonsilent mono audio, saves PCM16 WAV, checks the
saved file, and **fails** if actual duration falls outside 15–20 seconds. It retains the
original WAV and failure metrics for diagnosis instead of silently padding, clipping,
or changing the speaking rate. Adjust the narration after listening and rerun if needed.

Metrics include load/download time, synthesis time, total time, sample rate, audio duration,
real-time factor (generation time divided by duration), peak process RSS, seed, CPU threads,
and Torch version. Peak RSS excludes child processes and is Linux-specific. The workflow
uploads diagnostics even if generation fails; a failed installation may leave no artifacts.
Unit tests exercise audio validation and failure reporting without downloading model weights.
A successful unit test run does not establish model download access, synthesis quality,
or actual hosted-runner performance.
