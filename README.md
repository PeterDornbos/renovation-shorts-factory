# Renovation Shorts Factory

Turn a JSON script and **six supplied renovation images** into a narrated portrait
Short with one manual GitHub Actions run. The pipeline uses the working Chatterbox
Nano CPU implementation, FFmpeg, and Python 3.11. It does not generate images, use
stock replacements, call paid APIs, use GPUs, upload videos to a platform, or schedule runs.

## Supply the script and images

Start with [`manifests/renovation.json`](manifests/renovation.json). Commit your six
separate images at these paths (or change the manifest paths):

```text
assets/renovation/01.png
assets/renovation/02.png
assets/renovation/03.png
assets/renovation/04.png
assets/renovation/05.png
assets/renovation/06.png
```

**Images have not been supplied in this repository yet.** The default video workflow
will report the missing files until you add them. There is no fallback footage.
Use six stages of the same renovation, in order. Check that camera perspective,
room geometry, doors, windows, cabinet layout, and permanent architectural features
stay consistent. The renderer preserves your images, applies EXIF orientation, and
resizes to 1080×1920 without cropping or inventing content. Architectural consistency
requires your visual review; software cannot establish it from dimensions alone.

Each image must be an exact **9:16** portrait (for example 1080×1920 or 720×1280).
PNG and JPEG are supported through Pillow. Paths are relative to the manifest file,
must stay inside this repository, and cannot be remote URLs. Six distinct paths and
six distinct image contents are required. Use only assets you have permission to use.

The manifest structure is:

```json
{
  "version": 1,
  "title": "A kitchen gets a fresh start",
  "target_duration_seconds": [18, 20],
  "scenes": [
    {"image": "../assets/renovation/01.png", "narration": "This dated kitchen is ready for a bright, welcoming start."},
    {"image": "../assets/renovation/02.png", "narration": "First, we clear the clutter and carefully prepare every surface."},
    {"image": "../assets/renovation/03.png", "narration": "Fresh cabinet finishes add warmth while keeping the familiar layout."},
    {"image": "../assets/renovation/04.png", "narration": "New countertops and a clean backsplash give a crisp finish."},
    {"image": "../assets/renovation/05.png", "narration": "Soft lighting highlights the details and makes everyday cooking inviting."},
    {"image": "../assets/renovation/06.png", "narration": "Now this refreshed kitchen becomes the welcoming heart of home."}
  ]
}
```

Keep each scene to a short sentence, about 10–12 words. The bundled script is longer
than the original approximately 44-word narration, which produced 13.04 seconds in
the first hosted CPU test (about 55 seconds to generate, as reported). Aim for
18–20 seconds by changing the words and rerunning. Actual speaking speed and pauses
vary; word counts do not guarantee duration.

Nano is loaded **once**, then generates each scene's sentence using the same bundled
voice. The sentences are concatenated without speech clipping or rate changes. Their
sample counts define scene boundaries and captions exactly. Captions show the whole
sentence during its scene, with high-contrast 60px text, wrapping, and a lower-screen
safe margin. They are synchronized at scene level, not word-level karaoke captions.
Transitions crossfade images for 0.25 seconds around these boundaries, keeping the
complete video duration equal to narration.

The 18–20-second goal is recorded in metrics. Falling outside it produces a warning
and retains a usable full-length MP4 instead of repeating the old duration-only
failure. The supported hard limit is 1–60 seconds, with each scene at least 0.6 seconds.
Listen before using the video; revise wording if it is too short, too long, or awkward.
Long sentences that cannot fit in four readable caption lines fail with a clear message.

### Optional background music

Omit `music` for narration only. To add a supplied royalty-free track, add this field
to the manifest and commit the audio file:

```json
"music": {
  "path": "../assets/music/renovation.wav",
  "license": "Track title, creator, license URL, and any required attribution",
  "volume": 0.10
}
```

The license note is required; the pipeline does not verify legal rights or download
music. The file loops beneath the narration at low volume (0–0.25), with limiting to
avoid clipping. Music ends with the video; speech remains complete. Preserve required
attribution when eventually using the video.

## Run on GitHub and download the MP4

1. Merge the workflow into the default branch and commit your manifest and images.
2. Open **Actions → Produce renovation Short → Run workflow**.
3. Select the branch containing your assets and enter its manifest path, such as
   `manifests/renovation.json`.
4. Download **renovation-short-&lt;run-id&gt;** from the completed run's **Artifacts** section.
5. Open `renovation.mp4` and review the six images, narration, captions, and pacing.

The artifact also contains `renovation.wav`, `timeline.json`, `captions.ass`, a copy of
the input manifest, Nano `metrics.json`, `render_metrics.json`, and
`pipeline_metrics.json`. Diagnostics are uploaded on failure when available, including
missing-asset preflight failures. Artifacts expire after **7 days**. An installation
failure may occur before diagnostics can be created. No publishing step or recurring
schedule exists. The older **Test Chatterbox Nano voiceover** workflow remains available
for narration-only experiments and now reads the same default manifest.

### Cost and dependencies

This public repository uses standard `ubuntu-24.04` GitHub-hosted CPU runners, open-source
software, public model weights, and no API keys. Standard hosted runners are normally
free for public repositories. If the repository becomes private, runs and storage
consume your included account allowances; avoid paid overages and check GitHub quotas.
Short artifact retention and a 30-minute job timeout limit waste. No paid account,
subscription, GPU service, or image-generation API is needed.

The existing Nano source revision and CPU Torch/Torchaudio 2.6.0 are retained. The
[official README](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/README.md),
[Nano example](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/example_tts_nano.py),
and [loader](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/tts_turbo.py)
verify the actual Nano API:

```python
from chatterbox.tts_turbo import ChatterboxTurboTTS
model = ChatterboxTurboTTS.from_pretrained(device="cpu", nano=True)
wav = model.generate(scene_narration)
```

It is the 110M English Nano model, not the original `ChatterboxTTS` class. It uses the
checkpoint's bundled voice, without requiring a reference recording. There is no
invented American-accent parameter. The first hosted test's voice was judged natural
by the user; the new six-sentence cadence still needs listening review. Keep the
built-in Perth watermark. See the [model card](https://huggingface.co/ResembleAI/chatterbox-nano)
for licensing and limitations. Transitive dependencies (including upstream Perth's
`master` reference) and model weights remain partially unpinned, as in the working setup.

## Local or cloud development

Use the existing checkout; cloud tasks are already isolated and need no Git worktree.
On Linux, install Python 3.11, FFmpeg with libx264/libass/AAC, and DejaVu fonts.
Ubuntu system packages: `ffmpeg fonts-dejavu-core`.

```bash
cd /path/to/renovation-shorts-factory
python3.11 -m venv .venv
source .venv/bin/activate
bash scripts/setup_voiceover.sh
python -m unittest discover -s tests -v
python scripts/produce_short.py --manifest manifests/renovation.json --validate-only
HF_HUB_DISABLE_XET=1 python scripts/produce_short.py --manifest manifests/renovation.json
```

No server is needed. Use `--output-dir` for a separate output directory per local run.
The pipeline overwrites outputs in the selected directory; treat it as generated data.
For narration-only timing experiments (images are not needed):

```bash
HF_HUB_DISABLE_XET=1 python scripts/generate_voiceover.py --manifest manifests/renovation.json
```

To render a previously generated narration with its matching timeline:

```bash
python scripts/render_short.py --manifest manifests/renovation.json \
  --narration artifacts/voiceover/renovation.wav \
  --timeline artifacts/voiceover/timeline.json --output-dir artifacts/short
```

Validation checks six distinct 9:16 inputs, six contiguous sample-derived scene intervals,
six matching MP4 chapter markers, one 1080×1920 H.264 picture track, one AAC audio track,
matching audio/video duration, and successful decoding of the entire output. Integration
tests render six synthetic color fixtures and check decoded scene midpoint pixels;
these fixtures are never used as production renovation assets. No automated test
establishes architectural consistency, narration accuracy, or subjective voice quality.

Metrics record model loading, synthesis, rendering/validation, total pipeline time,
real-time factor, sample rate, scene count, dimensions, actual duration, target attainment,
file size, seed, CPU threads, and process memory. Memory values are Linux peak RSS per
process/child maximum, not a simultaneous sum of the whole process tree.

## Troubleshooting

- **Missing image / wrong aspect ratio / duplicate image:** supply all six distinct
  portraits at the manifest paths. The preflight stops before downloading the model.
- **Narration outside 18–20 seconds:** check `duration_in_target` and listen to the WAV.
  Add or remove words in the JSON; do not clip speech or claim the target passed.
- **Unreadable caption error:** shorten that scene's sentence or long individual words.
- **Model download 403:** allow `huggingface.co` and its redirected download hosts in
  restricted cloud environments, including `us.aws.cdn.hf.co`, `cas-bridge.xethub.hf.co`,
  `cdn-lfs.huggingface.co`, and `cdn-lfs-us-1.huggingface.co`. No token is normally needed
  for public weights. Dependencies need GitHub, PyPI, and `download.pytorch.org`.
- **Font/FFmpeg error:** install DejaVu Sans and an FFmpeg build with libass/libx264.
  In a filesystem-restricted cloud machine, set `XDG_CACHE_HOME` to a writable directory.
- **Memory or timeout:** the renderer uses one filter thread and two encoder threads;
  use standard-sized source images and inspect runtime metrics. First downloads take
  longer than cached runs. Six scene-wise synthesis calls may take longer than the
  previously measured single-paragraph generation.
- **Failed job:** read the failing step and downloaded JSON diagnostics. A generated
  MP4 with failed validation is not an approved output. No hosted run of the new
  complete pipeline or final renovation video is claimed until real assets are supplied
  and that run succeeds.
