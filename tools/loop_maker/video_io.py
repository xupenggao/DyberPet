"""Video frame extraction and subsampling."""

import cv2
import numpy as np


def get_video_info(video_path: str) -> dict:
    """Return video metadata: fps, total_frames, width, height, duration."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0
    cap.release()

    return {
        "fps": fps,
        "total_frames": total_frames,
        "width": width,
        "height": height,
        "duration": duration,
    }


def extract_frames(
    video_path: str,
    target_fps: float | None = None,
    crop: tuple[int, int, int, int] | None = None,
) -> tuple[list[np.ndarray], float]:
    """Extract frames from video, optionally subsampling to target_fps.

    Args:
        video_path: Path to video file.
        target_fps: If set, subsample to this FPS. None = keep original.
        crop: (x, y, w, h) crop region. None = no crop.

    Returns:
        (frames, original_fps) where frames are RGB numpy arrays.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    original_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Determine which frames to keep
    if target_fps and target_fps < original_fps:
        step = original_fps / target_fps
        keep_indices = set()
        idx = 0.0
        while idx < total_frames:
            keep_indices.add(int(idx))
            idx += step
    else:
        keep_indices = None  # keep all

    frames = []
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if keep_indices is None or frame_idx in keep_indices:
            # BGR -> RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if crop:
                x, y, w, h = crop
                frame = frame[y : y + h, x : x + w]
            frames.append(frame)

        frame_idx += 1

    cap.release()
    return frames, original_fps


def extract_frames_streaming(
    video_path: str,
    target_fps: float | None = None,
    crop: tuple[int, int, int, int] | None = None,
):
    """Yield frames one at a time for memory-efficient processing.

    Yields (frame_index, frame_rgb) tuples.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    original_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if target_fps and target_fps < original_fps:
        step = original_fps / target_fps
        keep_indices = set()
        idx = 0.0
        while idx < total_frames:
            keep_indices.add(int(idx))
            idx += step
    else:
        keep_indices = None

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if keep_indices is None or frame_idx in keep_indices:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if crop:
                x, y, w, h = crop
                frame = frame[y : y + h, x : x + w]
            yield frame_idx, frame

        frame_idx += 1

    cap.release()
