"""Core loop detection algorithm."""

import numpy as np
from tqdm import tqdm

from .similarity import compute_pose_similarity, compute_image_similarity


def find_best_loop(
    frames: list[np.ndarray],
    poses: list[dict] | None = None,
    min_gap: int = 10,
    max_frames: int = 60,
    similarity_threshold: float = 0.85,
    use_pose: bool = True,
    crossfade_frames: int = 0,
) -> tuple[int | None, int | None, float]:
    """Find the best loop point in a frame sequence.

    Finds pair (i, j) where the animal pose is most similar,
    with min_gap < (j - i) <= max_frames.

    Returns:
        (start_idx, end_idx, similarity_score) or (None, None, 0.0)
    """
    n = len(frames)
    if n < min_gap * 2:
        print(f"Video too short: {n} frames, need at least {min_gap * 2}")
        return None, None, 0.0

    can_use_pose = (
        use_pose
        and poses is not None
        and sum(1 for p in poses if p["detected"]) / n >= 0.5
    )

    if can_use_pose:
        print("Using pose-based similarity...")
        sim_matrix = _compute_similarity_band_pose(
            frames, poses, n, min_gap, max_frames
        )
    else:
        if use_pose and poses is not None:
            print("Pose detection rate too low, falling back to image similarity...")
        else:
            print("Using image-based similarity...")
        sim_matrix = _compute_similarity_band_image(
            frames, poses, n, min_gap, max_frames
        )

    # Find best candidate: highest similarity, then shortest duration
    best_score = 0.0
    best_i, best_j = None, None

    for i in range(n):
        for j in range(i + min_gap, min(i + max_frames + 1, n)):
            score = sim_matrix[i][j]
            if score > best_score or (
                score == best_score
                and best_i is not None
                and (j - i) < (best_j - best_i)
            ):
                best_score = score
                best_i, best_j = i, j

    if best_score < similarity_threshold:
        print(
            f"Best similarity {best_score:.3f} below threshold {similarity_threshold:.3f}"
        )
        # Auto-retry with lower thresholds
        for lower_thresh in [similarity_threshold - 0.05, similarity_threshold - 0.1, 0.6]:
            if lower_thresh <= best_score:
                print(f"  Accepting with lower threshold {lower_thresh:.2f}")
                break
        else:
            if best_score < 0.6:
                print("No suitable loop point found. Try a video with repeated motion.")
                return None, None, best_score

    print(
        f"Best loop: frames {best_i} -> {best_j} "
        f"({best_j - best_i} frames, similarity={best_score:.3f})"
    )
    return best_i, best_j, best_score


def _compute_similarity_band_pose(
    frames: list[np.ndarray],
    poses: list[dict],
    n: int,
    min_gap: int,
    max_frames: int,
) -> np.ndarray:
    """Compute pose similarity for all candidate (i, j) pairs."""
    sim_matrix = np.zeros((n, n))
    total = sum(
        min(max_frames, n - i - min_gap) for i in range(n) if i + min_gap < n
    )
    pbar = tqdm(total=total, desc="Computing pose similarity")

    for i in range(n):
        if not poses[i]["detected"]:
            pbar.update(min(max_frames, max(0, n - i - min_gap)))
            continue
        for j in range(i + min_gap, min(i + max_frames + 1, n)):
            if poses[j]["detected"]:
                sim_matrix[i][j] = compute_pose_similarity(
                    poses[i], poses[j], method="oks"
                )
            pbar.update(1)

    pbar.close()
    return sim_matrix


def _compute_similarity_band_image(
    frames: list[np.ndarray],
    poses: list[dict] | None,
    n: int,
    min_gap: int,
    max_frames: int,
) -> np.ndarray:
    """Compute image similarity for all candidate (i, j) pairs."""
    sim_matrix = np.zeros((n, n))
    total = sum(
        min(max_frames, n - i - min_gap) for i in range(n) if i + min_gap < n
    )
    pbar = tqdm(total=total, desc="Computing image similarity")

    for i in range(n):
        bbox_a = poses[i]["bbox"] if poses and poses[i]["detected"] else None
        for j in range(i + min_gap, min(i + max_frames + 1, n)):
            bbox_b = (
                poses[j]["bbox"] if poses and poses[j]["detected"] else None
            )
            sim_matrix[i][j] = compute_image_similarity(
                frames[i], frames[j], bbox_a, bbox_b
            )
            pbar.update(1)

    pbar.close()
    return sim_matrix


def apply_crossfade(
    frames: list[np.ndarray],
    start: int,
    end: int,
    blend_frames: int = 3,
) -> list[np.ndarray]:
    """Alpha-blend boundary frames for smoother loop transition."""
    segment = frames[start:end]
    n = len(segment)
    if blend_frames <= 0 or n < blend_frames * 2:
        return segment

    result = [f.copy() for f in segment]
    for k in range(blend_frames):
        alpha = (k + 1) / (blend_frames + 1)
        idx_from_start = k
        idx_from_end = n - blend_frames + k

        blended = (
            segment[idx_from_start].astype(float) * (1 - alpha)
            + segment[idx_from_end].astype(float) * alpha
        ).astype(np.uint8)
        result[idx_from_start] = blended

    return result
