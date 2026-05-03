"""Green screen chroma key and AI background removal."""

import cv2
import numpy as np


def remove_green_screen(
    frame: np.ndarray,
    hue_range: tuple[int, int] = (35, 85),
    saturation_min: int = 40,
    value_min: int = 40,
    feather: int = 3,
    spill_remove: bool = True,
) -> np.ndarray:
    """Remove green screen background, returning RGBA with transparent bg.

    Args:
        frame: RGB numpy array (H, W, 3).
        hue_range: HSV hue range for green detection (0-180). Default (35, 85).
        saturation_min: Minimum saturation to count as green (0-255).
        value_min: Minimum brightness to count as green (0-255).
        feather: Edge feathering radius in pixels. 0 = hard edge.
        spill_remove: Remove green color spill on foreground edges.

    Returns:
        RGBA numpy array (H, W, 4) with transparent background.
    """
    # RGB -> BGR for OpenCV, then to HSV
    bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # Green mask in HSV
    lower_green = np.array([hue_range[0], saturation_min, value_min])
    upper_green = np.array([hue_range[1], 255, 255])
    mask = cv2.inRange(hsv, lower_green, upper_green)

    # Morphological cleanup: close small holes, remove noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Edge feathering for smooth alpha transitions
    if feather > 0:
        mask = cv2.GaussianBlur(mask, (0, 0), feather)
        # Re-threshold to keep binary for interior, soft at edges
        _, mask = cv2.threshold(mask, 128, 255, cv2.THRESH_BINARY)

    # Invert: green pixels become 0 (transparent), foreground becomes 255
    alpha = cv2.bitwise_not(mask)

    # Optional: remove green color spill on foreground edges
    result = frame.copy()
    if spill_remove:
        result = _remove_spill(result, alpha)

    # Combine into RGBA
    rgba = np.dstack([result, alpha])
    return rgba


def _remove_spill(frame: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Reduce green color spill on semi-transparent edge pixels."""
    result = frame.astype(np.float32)
    green_channel = result[:, :, 1]

    # Where alpha is low (near background), suppress green channel
    alpha_f = alpha.astype(np.float32) / 255.0
    spill_mask = (alpha_f > 0) & (alpha_f < 1.0)

    # Desaturate green in spill regions
    avg_other = (result[:, :, 0] + result[:, :, 2]) / 2.0
    green_spill = green_channel - avg_other
    green_spill = np.maximum(green_spill, 0)

    reduction = green_spill * (1.0 - alpha_f) * 0.8
    result[:, :, 1] -= reduction

    return np.clip(result, 0, 255).astype(np.uint8)


def remove_green_screen_batch(
    frames: list[np.ndarray],
    **kwargs,
) -> list[np.ndarray]:
    """Apply green screen removal to a list of frames.

    Returns list of RGBA numpy arrays.
    """
    results = []
    for i, frame in enumerate(frames):
        rgba = remove_green_screen(frame, **kwargs)
        results.append(rgba)
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(frames)} frames")
    return results


def remove_bg_ai(
    frames: list[np.ndarray],
) -> list[np.ndarray]:
    """AI-based background removal using rembg. Optional dependency.

    Returns list of RGBA numpy arrays.
    """
    try:
        from rembg import remove
    except ImportError:
        raise RuntimeError(
            "rembg is not installed. Install with: pip install rembg"
        )

    results = []
    for i, frame in enumerate(frames):
        output = remove(frame)
        # rembg returns RGBA
        if output.shape[2] == 3:
            alpha = np.full((output.shape[0], output.shape[1], 1), 255, dtype=np.uint8)
            output = np.dstack([output, alpha])
        results.append(output)
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(frames)} frames")
    return results


def auto_detect_green_range(frames: list[np.ndarray]) -> tuple[int, int]:
    """Sample frames to auto-detect the green screen hue range.

    Returns (hue_min, hue_max) for use with remove_green_screen.
    """
    # Sample a few frames and check the top/bottom edge pixels
    sample_indices = [0, len(frames) // 2, len(frames) - 1]
    hue_values = []

    for idx in sample_indices:
        if idx >= len(frames):
            continue
        frame = frames[idx]
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # Sample corner pixels and edge strips
        h, w = hsv.shape[:2]
        samples = [
            hsv[:5, :].reshape(-1, 3),       # top edge
            hsv[-5:, :].reshape(-1, 3),       # bottom edge
            hsv[:, :5].reshape(-1, 3),        # left edge
            hsv[:, -5:].reshape(-1, 3),       # right edge
        ]
        for sample in samples:
            # Filter for reasonably saturated pixels
            mask = (sample[:, 1] > 30) & (sample[:, 2] > 30)
            hues = sample[mask, 0]
            hue_values.extend(hues.tolist())

    if not hue_values:
        return (35, 85)  # default green range

    hue_arr = np.array(hue_values)
    hue_min = max(int(np.percentile(hue_arr, 5)), 0)
    hue_max = min(int(np.percentile(hue_arr, 95)), 180)

    # Only use if it's actually in the green range (roughly 30-90)
    if hue_min > 90 or hue_max < 30:
        print("  Warning: auto-detected hue range doesn't look like green screen, using defaults")
        return (35, 85)

    print(f"  Auto-detected green hue range: {hue_min}-{hue_max}")
    return (hue_min, hue_max)
