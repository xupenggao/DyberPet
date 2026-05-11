# coding:utf-8
import os
import sys
import json
import re
import shutil
import tempfile
from collections import deque

import cv2
import numpy as np

from PySide6.QtCore import QObject, Signal, QRect, Qt
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor

_project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

DEFAULT_FRAME_WIDTH = 128
DEFAULT_FRAME_HEIGHT = 128
MIN_FRAME_DIM = 32

NUM_EXTRACT_FRAMES = 20

GREEN_STRICT_MIN = 120
GREEN_STRICT_DOMINANCE = 45
GREEN_FEATHER_MIN = 95
GREEN_FEATHER_DOMINANCE = 25

REQUIRED_ACTIONS = {
    "stand": {
        "description": "待机",
    },
    "leftwalk": {
        "description": "向左走路动作",
    },
}

OPTIONAL_ACTIONS = {
    "sit": {
        "description": "坐下动作",
    },
    "lie": {
        "description": "趴下动作",
    },
    "sleep": {
        "description": "睡觉动作",
    },
    "patpat": {
        "description": "被摸头动作",
    },
    "drag": {
        "description": "被拖拽动作",
    },
    "prefall": {
        "description": "即将下落的预备动作",
    },
    "fall": {
        "description": "向下掉落动作",
    },
    "onfloor": {
        "description": "落到地面后的动作",
    },
}

ALL_ACTIONS = {**REQUIRED_ACTIONS, **OPTIONAL_ACTIONS}


class SpriteSheetProcessor(QObject):
    progress_updated = Signal(str, str)
    processing_complete = Signal(dict)
    processing_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def process_uploaded_videos(self, videos):
        self._cancelled = False
        results = {}

        for action_name, video_info in videos.items():
            if self._cancelled:
                self.processing_error.emit("用户已取消")
                return

            if isinstance(video_info, dict):
                video_path = video_info["path"]
                anim_type = video_info.get("anim_type", "loop")
            else:
                video_path = video_info
                anim_type = "loop"

            self.progress_updated.emit(action_name, "processing")

            frames = self._process_video(video_path, action_name, anim_type)
            if frames is None:
                return

            results[action_name] = frames
            self.progress_updated.emit(action_name, "done")

        if "leftwalk" in results and not self._cancelled:
            results["rightwalk"] = self._mirror_frames(results["leftwalk"])
            self.progress_updated.emit("rightwalk", "done")

        if not self._cancelled:
            self.processing_complete.emit(results)

    def _process_video(self, video_path, action_name, anim_type="loop"):
        from tools.loop_maker.video_io import extract_frames

        frames, _ = extract_frames(video_path, target_fps=12)
        if not frames:
            self.processing_error.emit(f"无法从视频中提取帧：{video_path}")
            return None

        if anim_type == "loop":
            segment = self._find_loop(frames)
        else:
            segment = self._extract_oneshot(frames)

        keyed_frames = []
        for rgb in segment:
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
            keyed = self._remove_green_screen(qimg)
            keyed_frames.append(keyed)

        bboxes = []
        for f in keyed_frames:
            bbox = self._find_subject_bounds(f)
            if bbox is None:
                self.processing_error.emit("视频帧中未检测到主体")
                return None
            bboxes.append(bbox)

        # 全局坐标：所有帧中主体的最左/最右/最高/最低位置
        g_x1 = min(b.left() for b in bboxes)
        g_y1 = min(b.top() for b in bboxes)
        g_x2 = max(b.left() + b.width() for b in bboxes)
        g_y2 = max(b.top() + b.height() for b in bboxes)
        global_rect = QRect(g_x1, g_y1, g_x2 - g_x1, g_y2 - g_y1)

        frame_w, frame_h = self._calculate_adaptive_frame_size(
            global_rect.width(), global_rect.height())

        rendered = [
            self._render_global_crop(f, global_rect, frame_w, frame_h)
            for f in keyed_frames
        ]
        return rendered

    MIN_OUTPUT_FRAMES = 10

    def _find_loop(self, frames):
        n = len(frames)

        try:
            from tools.loop_maker.loop_finder import find_best_loop
            start, end, score = find_best_loop(
                frames,
                min_gap=max(5, n // 10),
                max_frames=min(60, n),
                similarity_threshold=0.8,
                use_pose=False,
            )
            if start is not None and (end - start) >= self.MIN_OUTPUT_FRAMES:
                return frames[start:end]
        except Exception:
            pass

        target = max(self.MIN_OUTPUT_FRAMES, NUM_EXTRACT_FRAMES)
        if n <= target:
            return list(frames)
        indices = [int(i * (n - 1) / (target - 1)) for i in range(target)]
        return [frames[i] for i in indices]

    def _extract_oneshot(self, frames):
        n = len(frames)
        target = max(self.MIN_OUTPUT_FRAMES, NUM_EXTRACT_FRAMES)
        if n <= target:
            return list(frames)
        indices = [int(i * (n - 1) / (target - 1)) for i in range(target)]
        return [frames[i] for i in indices]

    # ── Green screen removal (BFS flood fill) ──────────────────────────

    def _find_subject_bounds(self, image):
        width, height = image.width(), image.height()
        image = image.convertToFormat(QImage.Format.Format_ARGB32)
        bpl = image.bytesPerLine()
        raw = bytes(image.constBits())
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(height, bpl)
        arr = arr[:, :width * 4].reshape(height, width, 4)
        alpha = arr[:, :, 3]

        mask = (alpha > 128).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        coords = cv2.findNonZero(mask)
        if coords is None:
            return None
        x, y, w, h = cv2.boundingRect(coords)
        return QRect(x, y, w, h)

    def _remove_green_screen(self, image):
        image = image.convertToFormat(QImage.Format.Format_ARGB32)
        width, height = image.width(), image.height()
        visited = set()
        queue = deque(self._green_screen_seed_points(width, height))

        while queue:
            x, y = queue.popleft()
            if x < 0 or y < 0 or x >= width or y >= height or (x, y) in visited:
                continue
            color = image.pixelColor(x, y)
            visited.add((x, y))
            if color.alpha() <= 8:
                continue
            if not self._is_green_screen(color, relaxed=True):
                continue

            color.setAlpha(0)
            image.setPixelColor(x, y, color)
            queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))

        self._remove_dark_borders(image)
        self._feather_green_edges(image)
        return image

    def _green_screen_seed_points(self, width, height):
        seeds = set()
        for x in range(width):
            seeds.add((x, 0))
            seeds.add((x, height - 1))
        for y in range(height):
            seeds.add((0, y))
            seeds.add((width - 1, y))

        step = max(1, min(width, height) // 8)
        for y in range(step, height - 1, step):
            for x in range(step, width - 1, step):
                seeds.add((x, y))
        return seeds

    def _is_green_screen(self, color, relaxed=False):
        green = color.green()
        dominance = green - max(color.red(), color.blue())
        if relaxed:
            return green >= GREEN_FEATHER_MIN and dominance >= GREEN_FEATHER_DOMINANCE
        return green >= GREEN_STRICT_MIN and dominance >= GREEN_STRICT_DOMINANCE

    def _remove_dark_borders(self, image):
        width, height = image.width(), image.height()
        visited = set()
        queue = deque()
        for x in range(width):
            queue.append((x, 0))
            queue.append((x, height - 1))
        for y in range(height):
            queue.append((0, y))
            queue.append((width - 1, y))

        while queue:
            x, y = queue.popleft()
            if x < 0 or y < 0 or x >= width or y >= height or (x, y) in visited:
                continue
            visited.add((x, y))
            color = image.pixelColor(x, y)
            if color.alpha() <= 8:
                continue
            if color.red() > 30 or color.green() > 30 or color.blue() > 30:
                continue
            color.setAlpha(0)
            image.setPixelColor(x, y, color)
            queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))

    def _feather_green_edges(self, image):
        width, height = image.width(), image.height()
        to_clear = []
        to_feather = []

        for y in range(height):
            for x in range(width):
                color = image.pixelColor(x, y)
                if color.alpha() <= 8 or not self._is_green_screen(color, relaxed=True):
                    continue
                if not self._has_transparent_neighbor(image, x, y):
                    continue
                if self._is_green_screen(color, relaxed=False):
                    to_clear.append((x, y))
                else:
                    to_feather.append((x, y))

        for x, y in to_clear:
            color = image.pixelColor(x, y)
            color.setAlpha(0)
            image.setPixelColor(x, y, color)

        for x, y in to_feather:
            color = image.pixelColor(x, y)
            color.setAlpha(min(color.alpha(), 96))
            image.setPixelColor(x, y, color)

    def _has_transparent_neighbor(self, image, x, y):
        width, height = image.width(), image.height()
        for nx in (x - 1, x, x + 1):
            for ny in (y - 1, y, y + 1):
                if nx == x and ny == y:
                    continue
                if nx < 0 or ny < 0 or nx >= width or ny >= height:
                    continue
                if image.pixelColor(nx, ny).alpha() <= 8:
                    return True
        return False

    # ── Rendering ──────────────────────────────────────────────────────

    def _calculate_adaptive_frame_size(self, subject_w, subject_h):
        if subject_w <= 0 or subject_h <= 0:
            return DEFAULT_FRAME_WIDTH, DEFAULT_FRAME_HEIGHT
        aspect = subject_w / subject_h
        if aspect >= 1.0:
            fw = DEFAULT_FRAME_WIDTH
            fh = max(MIN_FRAME_DIM, round(DEFAULT_FRAME_WIDTH / aspect))
        else:
            fh = DEFAULT_FRAME_HEIGHT
            fw = max(MIN_FRAME_DIM, round(DEFAULT_FRAME_HEIGHT * aspect))
        return fw, fh

    def _render_global_crop(self, image, global_rect, frame_w, frame_h):
        crop = image.copy(global_rect)
        scaled = crop.scaled(
            frame_w, frame_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        frame = QImage(frame_w, frame_h, QImage.Format.Format_ARGB32_Premultiplied)
        frame.fill(Qt.GlobalColor.transparent)
        painter = QPainter(frame)
        painter.drawImage(
            (frame_w - scaled.width()) // 2,
            frame_h - scaled.height(),
            scaled,
        )
        painter.end()
        return frame

    def _mirror_frames(self, frames):
        mirrored = []
        for frame in frames:
            mirrored.append(frame.mirrored(True, False))
        return mirrored


class PetFileBuilder:
    SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-一-鿿]{1,32}$")

    @staticmethod
    def validate_pet_name(pet_name):
        name = pet_name.strip()
        if not name:
            return False, "请输入桌宠名称"
        if name in (".", "..") or not PetFileBuilder.SAFE_NAME_RE.match(name):
            return False, "名称只能包含字母、数字、中文、下划线和连字符（最长32字符）"
        return True, name

    @staticmethod
    def build_pet_folder(pet_name, sprites, target_dir, anim_types=None):
        ok, result = PetFileBuilder.validate_pet_name(pet_name)
        if not ok:
            raise ValueError(result)
        pet_name = result

        required = set(REQUIRED_ACTIONS.keys()) | {"rightwalk"}
        missing = sorted(required - set(sprites.keys()))
        if missing:
            raise ValueError("缺少必传动作逐帧图：" + ", ".join(missing))

        os.makedirs(target_dir, exist_ok=True)
        pet_dir = os.path.join(target_dir, pet_name)
        if os.path.exists(pet_dir):
            raise FileExistsError(f"桌宠文件夹已存在：{pet_name}")

        build_dir = tempfile.mkdtemp(prefix=f".{pet_name}.creating_", dir=target_dir)
        try:
            action_dir = os.path.join(build_dir, "action")
            info_dir = os.path.join(build_dir, "info")
            os.makedirs(action_dir, exist_ok=True)
            os.makedirs(info_dir, exist_ok=True)

            for action_name, frames in sprites.items():
                for i, frame in enumerate(frames):
                    if isinstance(frame, QImage):
                        pixmap = QPixmap.fromImage(frame)
                    else:
                        pixmap = frame
                    path = os.path.join(action_dir, f"{action_name}_{i}.png")
                    pixmap.save(path, "PNG")

            max_fw, max_fh = DEFAULT_FRAME_WIDTH, DEFAULT_FRAME_HEIGHT
            for frames in sprites.values():
                if frames:
                    first = frames[0]
                    if isinstance(first, QImage):
                        max_fw = max(max_fw, first.width())
                        max_fh = max(max_fh, first.height())

            pet_conf = PetFileBuilder._generate_pet_conf(sprites, max_fw, max_fh)
            with open(os.path.join(build_dir, "pet_conf.json"), "w", encoding="utf-8") as f:
                json.dump(pet_conf, f, indent=2, ensure_ascii=False)

            act_conf = PetFileBuilder._generate_act_conf(sprites, anim_types)
            with open(os.path.join(build_dir, "act_conf.json"), "w", encoding="utf-8") as f:
                json.dump(act_conf, f, indent=2, ensure_ascii=False)

            info = {
                "petName": pet_name,
                "author": {
                    "name": "用户自定义",
                    "infos": "用户上传绿幕视频生成",
                    "frameColor": "#4f91ff",
                },
                "tages": {
                    "自定义": "#BDD7EE",
                },
                "intro": "由用户上传的绿幕视频创建。",
                "version": "1.0",
            }
            with open(os.path.join(info_dir, "info.json"), "w", encoding="utf-8") as f:
                json.dump(info, f, indent=2, ensure_ascii=False)

            from DyberPet.conf import CheckCharFiles
            stat_code, error_list = CheckCharFiles(build_dir)
            if stat_code != 0:
                detail = "" if error_list is None else ": " + ", ".join(error_list)
                raise ValueError(f"角色文件不完整 ({stat_code}){detail}")

            os.rename(build_dir, pet_dir)
        except Exception:
            if os.path.exists(build_dir):
                shutil.rmtree(build_dir)
            raise

        return pet_dir

    @staticmethod
    def _generate_pet_conf(sprites, frame_w=DEFAULT_FRAME_WIDTH, frame_h=DEFAULT_FRAME_HEIGHT):
        conf = {
            "width": frame_w,
            "height": frame_h,
            "scale": 1.0,
            "refresh": 5,
            "interact_speed": 0.02,
            "default": "default",
            "up": "default",
            "down": "default",
            "left": "left_walk",
            "right": "right_walk",
            "drag": "drag",
            "prefall": "prefall",
            "fall": "fall",
            "on_floor": "onfloor",
            "patpat": "patpat" if "patpat" in sprites else "default",
        }

        random_act = [
            {"name": "idle", "act_list": ["default"], "act_prob": 0.8, "act_type": [2, 0]},
        ]

        if "leftwalk" in sprites:
            random_act.append(
                {"name": "walk", "act_list": ["left_walk", "right_walk", "default"], "act_prob": 0.35, "act_type": [3, 1]}
            )

        if "sit" in sprites:
            random_act.append(
                {"name": "sit", "act_list": ["sit"], "act_prob": 0.25, "act_type": [2, 0]}
            )

        if "lie" in sprites:
            act_list = ["lie"]
            if "sleep" in sprites:
                act_list.append("sleep")
            act_list.append("default")
            random_act.append(
                {"name": "lie", "act_list": act_list, "act_prob": 0.2, "act_type": [1, 0]}
            )

        if "sleep" in sprites and "lie" not in sprites:
            random_act.append(
                {"name": "sleep", "act_list": ["sleep"], "act_prob": 0.15, "act_type": [0, 0]}
            )

        random_act.append(
            {"name": "onfloor", "act_list": ["onfloor"], "act_prob": 0, "act_type": [0, 10000]}
        )

        conf["random_act"] = random_act
        return conf

    @staticmethod
    def _generate_act_conf(sprites, anim_types=None):
        if anim_types is None:
            anim_types = {}

        def _act_num(action):
            return 5 if anim_types.get(action, "loop") == "loop" else 1

        conf = {
            "default": {
                "images": "stand",
                "act_num": _act_num("stand"),
                "frame_refresh": 0.13,
            },
        }

        if "leftwalk" in sprites:
            conf["left_walk"] = {
                "images": "leftwalk",
                "act_num": _act_num("leftwalk"),
                "need_move": True,
                "direction": "left",
                "frame_move": 3,
                "frame_refresh": 0.08,
            }

        if "rightwalk" in sprites:
            conf["right_walk"] = {
                "images": "rightwalk",
                "act_num": _act_num("leftwalk"),
                "need_move": True,
                "direction": "right",
                "frame_move": 3,
                "frame_refresh": 0.08,
            }

        for action_name in ("sit", "lie", "sleep", "patpat"):
            if action_name in sprites:
                conf[action_name] = {
                    "images": action_name,
                    "act_num": _act_num(action_name),
                    "frame_refresh": 0.11,
                }

        for action_name in ("drag", "prefall", "fall", "onfloor"):
            if action_name in sprites:
                conf[action_name] = {
                    "images": action_name,
                    "act_num": _act_num(action_name),
                    "frame_refresh": 0.08,
                }
            else:
                conf[action_name] = {
                    "images": "stand",
                    "act_num": 1,
                    "frame_refresh": 0.08,
                }

        return conf
