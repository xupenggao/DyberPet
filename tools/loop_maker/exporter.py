"""Export frames as DyberPet-compatible PNG sequence + act_conf.json."""

import json
import os

import cv2
import numpy as np
from PIL import Image


def export_frame_sequence(
    frames: list[np.ndarray],
    output_dir: str,
    name: str,
    size: tuple[int, int] | None = None,
) -> list[str]:
    """Save frames as numbered PNGs in DyberPet format.

    Files: {output_dir}/action/{name}_0.png, {name}_1.png, ...

    Args:
        frames: RGB or RGBA numpy arrays.
        output_dir: Output root directory.
        name: Animation name prefix.
        size: Optional (width, height) to resize.

    Returns:
        List of saved file paths.
    """
    action_dir = os.path.join(output_dir, "action")
    os.makedirs(action_dir, exist_ok=True)

    saved = []
    for idx, frame in enumerate(frames):
        if size is not None:
            if frame.shape[2] == 4:
                # RGBA: resize with alpha channel using INTER_AREA
                frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
            else:
                frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)

        pil_img = Image.fromarray(frame)
        filename = f"{name}_{idx}.png"
        filepath = os.path.join(action_dir, filename)
        pil_img.save(filepath, optimize=True)
        saved.append(filepath)

    return saved


def generate_act_conf_entry(
    name: str,
    num_frames: int,
    frame_refresh: float = 0.08,
    act_num: int = 1,
) -> dict:
    """Generate a single act_conf.json entry."""
    return {
        name: {
            "images": name,
            "act_num": act_num,
            "frame_refresh": frame_refresh,
        }
    }


def generate_act_conf_file(
    name: str,
    num_frames: int,
    output_dir: str,
    frame_refresh: float = 0.08,
    act_num: int = 1,
) -> str:
    """Write act_conf.json to output directory.

    Returns the path to the generated file.
    """
    entry = generate_act_conf_entry(name, num_frames, frame_refresh, act_num)
    filepath = os.path.join(output_dir, "act_conf.json")

    # Merge with existing file if present
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing.update(entry)
        entry = existing

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2, ensure_ascii=False)

    return filepath
