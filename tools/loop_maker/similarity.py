"""Pose and image similarity metrics."""

import numpy as np


def compute_pose_similarity(
    pose_a: dict,
    pose_b: dict,
    method: str = "oks",
) -> float:
    """Compute similarity between two poses. Returns value in [0, 1].

    Args:
        pose_a, pose_b: dicts with 'keypoints' (K,3) and 'bbox'
        method: "oks" or "cosine"
    """
    kpts_a = pose_a["keypoints"]
    kpts_b = pose_b["keypoints"]
    if kpts_a is None or kpts_b is None:
        return 0.0

    if method == "oks":
        return _oks_similarity(kpts_a, kpts_b, pose_a["bbox"], pose_b["bbox"])
    else:
        return _cosine_similarity(kpts_a, kpts_b)


def _oks_similarity(
    kpts_a: np.ndarray,
    kpts_b: np.ndarray,
    bbox_a: list,
    bbox_b: list,
) -> float:
    """Object Keypoint Similarity (COCO standard).

    OKS = mean(exp(-d_i^2 / (2 * s * sigma_i^2))) weighted by confidence.
    """
    # Average scale from both bounding boxes
    w_a = bbox_a[2] - bbox_a[0]
    h_a = bbox_a[3] - bbox_a[1]
    w_b = bbox_b[2] - bbox_b[0]
    h_b = bbox_b[3] - bbox_b[1]
    scale = (w_a * h_a + w_b * h_b) / 2.0
    if scale <= 0:
        return 0.0

    # COCO sigma values (per-keypoint tolerance)
    # Using a uniform sigma as we may not know exact keypoint semantics
    sigma = 0.05

    # Euclidean distances
    dx = kpts_a[:, 0] - kpts_b[:, 0]
    dy = kpts_a[:, 1] - kpts_b[:, 1]
    dist_sq = dx**2 + dy**2

    # Weight by minimum confidence of each keypoint pair
    conf = np.minimum(kpts_a[:, 2], kpts_b[:, 2])
    if conf.sum() < 0.1:
        return 0.0

    # OKS per keypoint
    oks_per_kpt = np.exp(-dist_sq / (2 * scale * sigma**2))

    # Weighted average
    oks = np.sum(oks_per_kpt * conf) / conf.sum()
    return float(np.clip(oks, 0.0, 1.0))


def _cosine_similarity(kpts_a: np.ndarray, kpts_b: np.ndarray) -> float:
    """Cosine similarity on keypoint vectors, weighted by confidence."""
    conf = np.minimum(kpts_a[:, 2], kpts_b[:, 2])
    if conf.sum() < 0.1:
        return 0.0

    vec_a = kpts_a[:, :2].flatten() * np.repeat(conf, 2)
    vec_b = kpts_b[:, :2].flatten() * np.repeat(conf, 2)

    dot = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a < 1e-8 or norm_b < 1e-8:
        return 0.0

    return float(np.clip(dot / (norm_a * norm_b), 0.0, 1.0))


def compute_image_similarity(
    img_a: np.ndarray,
    img_b: np.ndarray,
    bbox_a: list | None = None,
    bbox_b: list | None = None,
) -> float:
    """Compute combined image similarity (SSIM + pHash). Returns [0, 1].

    If bboxes are provided, crop to them before comparing.
    """
    # Crop to bbox if available
    if bbox_a is not None:
        x1, y1, x2, y2 = [int(v) for v in bbox_a]
        img_a = img_a[y1:y2, x1:x2]
    if bbox_b is not None:
        x1, y1, x2, y2 = [int(v) for v in bbox_b]
        img_b = img_b[y1:y2, x1:x2]

    if img_a.size == 0 or img_b.size == 0:
        return 0.0

    ssim_score = _compute_ssim(img_a, img_b)
    phash_score = _compute_phash_similarity(img_a, img_b)

    return 0.6 * ssim_score + 0.4 * phash_score


def _compute_ssim(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """SSIM between two images, resized to match."""
    from skimage.metrics import structural_similarity as ssim

    # Resize to same dimensions if needed
    if img_a.shape != img_b.shape:
        import cv2
        h, w = img_b.shape[:2]
        img_a = cv2.resize(img_a, (w, h), interpolation=cv2.INTER_AREA)

    # Convert to grayscale for SSIM
    if len(img_a.shape) == 3:
        import cv2
        gray_a = cv2.cvtColor(img_a, cv2.COLOR_RGB2GRAY)
        gray_b = cv2.cvtColor(img_b, cv2.COLOR_RGB2GRAY)
    else:
        gray_a, gray_b = img_a, img_b

    score = ssim(gray_a, gray_b)
    # SSIM range is [-1, 1], normalize to [0, 1]
    return float(np.clip((score + 1) / 2, 0.0, 1.0))


def _compute_phash_similarity(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """Perceptual hash similarity."""
    from PIL import Image
    import imagehash

    pil_a = Image.fromarray(img_a)
    pil_b = Image.fromarray(img_b)

    hash_a = imagehash.phash(pil_a)
    hash_b = imagehash.phash(pil_b)

    # Hamming distance normalized to [0, 1] similarity
    max_bits = hash_a.hash.size
    distance = hash_a - hash_b
    return 1.0 - distance / max_bits
