"""YOLOv8-based animal pose estimation."""

import numpy as np


def is_available() -> bool:
    """Check if ultralytics is installed."""
    try:
        import ultralytics  # noqa: F401
        return True
    except ImportError:
        return False


class PoseEstimator:
    """Detect animal keypoints using YOLOv8-Pose."""

    def __init__(self, model_name: str = "yolov8n-pose.pt", device: str = "cpu"):
        if not is_available():
            raise RuntimeError(
                "ultralytics is not installed. Install with: pip install ultralytics"
            )
        from ultralytics import YOLO
        self.model = YOLO(model_name)
        self.device = device

    def estimate_poses(self, frames: list[np.ndarray]) -> list[dict]:
        """Estimate pose for each frame.

        Returns list of dicts with:
            'keypoints': (K, 3) array [x, y, confidence] or None
            'bbox': [x1, y1, x2, y2] or None
            'detected': bool
        """
        results = []
        for frame in frames:
            preds = self.model.predict(
                frame, device=self.device, verbose=False, conf=0.25
            )
            if not preds or len(preds[0].boxes) == 0:
                results.append({"keypoints": None, "bbox": None, "detected": False})
                continue

            pred = preds[0]

            # Pick the largest bounding box (likely the main subject)
            boxes = pred.boxes
            areas = (boxes.xyxy[:, 2] - boxes.xyxy[:, 0]) * (
                boxes.xyxy[:, 3] - boxes.xyxy[:, 1]
            )
            best_idx = int(areas.argmax())

            kpts = pred.keypoints
            if kpts is None or kpts.data.shape[0] == 0:
                results.append({"keypoints": None, "bbox": None, "detected": False})
                continue

            keypoints = kpts.data[best_idx].cpu().numpy()  # (K, 3)
            bbox = boxes.xyxy[best_idx].cpu().numpy().tolist()

            results.append({
                "keypoints": keypoints,
                "bbox": bbox,
                "detected": True,
            })

        return results

    def detection_rate(self, poses: list[dict]) -> float:
        """Fraction of frames where an animal was detected."""
        if not poses:
            return 0.0
        return sum(1 for p in poses if p["detected"]) / len(poses)


def normalize_keypoints(keypoints: np.ndarray, bbox: list) -> np.ndarray:
    """Normalize keypoints to [0, 1] relative to bounding box.

    Makes pose comparison invariant to position and scale.
    """
    x1, y1, x2, y2 = bbox
    w = max(x2 - x1, 1.0)
    h = max(y2 - y1, 1.0)

    normalized = keypoints.copy()
    normalized[:, 0] = (keypoints[:, 0] - x1) / w
    normalized[:, 1] = (keypoints[:, 1] - y1) / h
    return normalized
