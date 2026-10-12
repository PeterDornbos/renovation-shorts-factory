"""Strict local manifest loading: no URLs, external paths, or replacement assets."""
import hashlib
import json
from pathlib import Path


def local_asset(manifest, value):
    if not isinstance(value, str) or not value or ":" in value or Path(value).is_absolute():
        raise ValueError("Asset paths must be relative local paths")
    path = (manifest.parent / value).resolve()
    root = Path(__file__).resolve().parents[1]
    if not path.is_relative_to(root):
        raise ValueError("Assets must stay inside the repository")
    return path


def load_manifest(path, check_assets=False):
    path = Path(path).resolve()
    if not path.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("Manifest must stay inside the repository")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Manifest must be a JSON object")
    if data.get("version") != 1:
        raise ValueError("Manifest version must be 1")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != 6:
        raise ValueError("Manifest must contain exactly six scenes")
    target = data.get("target_duration_seconds", [18, 20])
    if (not isinstance(target, list) or len(target) != 2
            or any(type(v) not in (int, float) for v in target)
            or not 0 < target[0] <= target[1] <= 60):
        raise ValueError("Duration target must be an ordered pair within 0–60 seconds")
    paths = []
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("Each scene must be an object")
        text = scene.get("narration")
        if not isinstance(text, str) or not text.strip() or len(text) > 240:
            raise ValueError("Each scene needs 1–240 characters of narration")
        if any(ord(c) < 32 for c in text) or any(c in text for c in "{}[]\\"):
            raise ValueError("Narration cannot contain control characters or caption markup")
        paths.append(local_asset(path, scene.get("image")))
    if len(set(paths)) != 6:
        raise ValueError("Supply six separate image files")
    music = data.get("music")
    if music is not None:
        if not isinstance(music, dict) or not isinstance(music.get("license"), str) or not music["license"].strip():
            raise ValueError("Optional music needs a license/permission note")
        music_path = local_asset(path, music.get("path"))
        volume = music.get("volume", 0.10)
        if type(volume) not in (int, float) or not 0 <= volume <= 0.25:
            raise ValueError("Music volume must be between 0 and 0.25")
        if check_assets and not music_path.is_file():
            raise ValueError(f"Missing supplied music: {music_path}")
    if check_assets:
        from PIL import Image, ImageOps
        hashes = []
        for image in paths:
            if not image.is_file():
                raise ValueError(f"Missing supplied image: {image}")
            with Image.open(image) as source:
                source = ImageOps.exif_transpose(source)
                w, h = source.size
                if w * 16 != h * 9:
                    raise ValueError(f"Image must have 9:16 dimensions: {image} ({w}x{h})")
                hashes.append(hashlib.sha256(source.convert("RGB").tobytes()).hexdigest())
        if len(set(hashes)) != 6:
            raise ValueError("The six images must contain different scene assets")
    data["target_duration_seconds"] = target
    return data
