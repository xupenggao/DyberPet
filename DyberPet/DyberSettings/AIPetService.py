# coding:utf-8
import os
import json
import base64
from io import BytesIO

import httpx
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap, QImage, QTransform

STYLE_PROMPTS = {
    "q_cartoon": (
        "Transform this pet photo into a cute Q-version chibi cartoon character suitable for a desktop pet application. "
        "The character should have a large head, big expressive eyes, small body, and vibrant colors. "
        "Keep the pet's distinctive features (fur color, markings, ear shape, tail). "
        "The image MUST have a completely transparent background (PNG with alpha channel). "
        "Character should be centered in the frame. "
    ),
    "pixel_art": (
        "Transform this pet photo into a retro pixel art sprite suitable for a desktop pet application. "
        "Use a limited color palette, clean pixel edges, and 16-32px style proportions. "
        "Keep the pet's distinctive features recognizable. "
        "The image MUST have a completely transparent background (PNG with alpha channel). "
        "Character should be centered in the frame. "
    ),
    "simplified": (
        "Transform this pet photo into a clean, simplified cartoon illustration suitable for a desktop pet application. "
        "Use smooth lines, flat colors with minimal shading, and a friendly appealing look. "
        "Keep the pet's distinctive features (fur color, markings, ear shape, tail). "
        "The image MUST have a completely transparent background (PNG with alpha channel). "
        "Character should be centered in the frame. "
    ),
}

STYLE_NAMES = {
    "q_cartoon": "Q-version Cartoon",
    "pixel_art": "Pixel Art",
    "simplified": "Simplified Cartoon",
}

REQUIRED_ACTIONS = {
    "stand": {
        "description": "standing idle, front-facing, neutral cute pose",
        "num_frames": 2,
    },
    "leftwalk": {
        "description": "walking to the left, side view, legs in mid-stride",
        "num_frames": 3,
    },
    "drag": {
        "description": "being dragged, surprised or startled expression, stretched pose",
        "num_frames": 1,
    },
    "fall": {
        "description": "falling downward, surprised expression, body stretched vertically",
        "num_frames": 1,
    },
}


class AIPetGenerator(QObject):
    progress_updated = Signal(str, str)
    generation_complete = Signal(dict)
    generation_error = Signal(str)

    def __init__(self, api_key, api_base="https://api.openai.com/v1", parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def generate_pet_sprites(self, photos, style, pet_name):
        self._cancelled = False
        results = {}

        style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["q_cartoon"])

        reference_b64 = []
        for path in photos:
            with open(path, "rb") as f:
                reference_b64.append(base64.b64encode(f.read()).decode())

        for action_name, action_info in REQUIRED_ACTIONS.items():
            if self._cancelled:
                self.generation_error.emit("Cancelled by user")
                return

            self.progress_updated.emit(action_name, "generating")

            frames = self._generate_action(
                reference_b64, style_prompt, pet_name, action_name, action_info
            )
            if frames is None:
                return

            results[action_name] = frames
            self.progress_updated.emit(action_name, "done")

        # rightwalk = mirror of leftwalk
        if "leftwalk" in results and not self._cancelled:
            results["rightwalk"] = self._mirror_frames(results["leftwalk"])
            self.progress_updated.emit("rightwalk", "done")

        if not self._cancelled:
            self.generation_complete.emit(results)

    def _generate_action(self, reference_b64, style_prompt, pet_name, action_name, action_info):
        num_frames = action_info["num_frames"]
        frame_note = f"Generate {num_frames} frame(s) arranged side by side in a single horizontal strip." if num_frames > 1 else "Generate a single frame."

        prompt = (
            f"{style_prompt}\n"
            f"Action: {action_info['description']}\n"
            f"{frame_note}\n"
            f"Each frame should be exactly 128x128 pixels. "
            f"The total image width should be {128 * num_frames} pixels and height 128 pixels. "
            f"Output as PNG with transparent background."
        )

        image_bytes = self._call_api(prompt, reference_b64)
        if image_bytes is None:
            return None

        return self._extract_frames(image_bytes, num_frames, 128)

    def _call_api(self, prompt, reference_images):
        try:
            content = [{"type": "text", "text": prompt}]
            for img_b64 in reference_images[:3]:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                })

            payload = {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 4096,
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Use chat completions API to generate with image input
            # The response may include generated image via gpt-4o image output
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            message = data["choices"][0]["message"]

            # Check if response contains generated image (gpt-4o image output)
            if hasattr(message, "get") and message.get("content"):
                for part in message.get("content", []):
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        img_url = part["image_url"]["url"]
                        if img_url.startswith("data:"):
                            b64 = img_url.split(",", 1)[1]
                            return base64.b64decode(b64)
                        else:
                            return self._download_image(img_url)

            # Fallback: try DALL-E endpoint for pure generation
            return self._call_dalle(prompt, reference_images)

        except httpx.HTTPStatusError as e:
            self.generation_error.emit(f"API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            self.generation_error.emit(f"Network error: {str(e)}")
            return None

    def _call_dalle(self, prompt, reference_images):
        try:
            # Use DALL-E 3 for image generation
            dalle_prompt = prompt.replace("This pet photo", "A pet character")

            payload = {
                "model": "dall-e-3",
                "prompt": dalle_prompt,
                "n": 1,
                "size": "1024x1024",
                "quality": "standard",
                "response_format": "b64_json",
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{self.api_base}/images/generations",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            b64 = data["data"][0]["b64_json"]
            return base64.b64decode(b64)

        except Exception as e:
            self.generation_error.emit(f"DALL-E error: {str(e)}")
            return None

    def _download_image(self, url):
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.content
        except Exception as e:
            self.generation_error.emit(f"Download error: {str(e)}")
            return None

    def _extract_frames(self, image_bytes, num_frames, frame_size):
        img = QImage()
        img.loadFromData(image_bytes)
        if img.isNull():
            self.generation_error.emit("Failed to load generated image")
            return None

        frames = []
        total_width = img.width()
        frame_width = total_width // num_frames
        for i in range(num_frames):
            rect = QRect(i * frame_width, 0, frame_width, img.height())
            frame = img.copy(rect)
            # Scale to target frame size
            if frame.width() != frame_size or frame.height() != frame_size:
                frame = frame.scaled(
                    frame_size, frame_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            frames.append(frame)
        return frames

    def _mirror_frames(self, frames):
        mirrored = []
        transform = QTransform().scale(-1, 1)
        for frame in frames:
            pixmap = QPixmap.fromImage(frame)
            mirrored_px = pixmap.transformed(transform)
            mirrored.append(mirrored_px.toImage())
        return mirrored


from PySide6.QtCore import QRect, Qt


class PetFileBuilder:
    @staticmethod
    def build_pet_folder(pet_name, sprites, target_dir):
        pet_dir = os.path.join(target_dir, pet_name)
        action_dir = os.path.join(pet_dir, "action")
        info_dir = os.path.join(pet_dir, "info")
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

        pet_conf = PetFileBuilder._generate_pet_conf()
        with open(os.path.join(pet_dir, "pet_conf.json"), "w", encoding="utf-8") as f:
            json.dump(pet_conf, f, indent=2, ensure_ascii=False)

        act_conf = PetFileBuilder._generate_act_conf(sprites)
        with open(os.path.join(pet_dir, "act_conf.json"), "w", encoding="utf-8") as f:
            json.dump(act_conf, f, indent=2, ensure_ascii=False)

        info = {
            "petName": pet_name,
            "author": "AI Generated",
            "version": "1.0",
        }
        with open(os.path.join(info_dir, "info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2, ensure_ascii=False)

        return pet_dir

    @staticmethod
    def _generate_pet_conf():
        return {
            "width": 128,
            "height": 128,
            "scale": 1.0,
            "refresh": 5,
            "interact_speed": 0.02,
            "default": "default",
            "up": "default",
            "down": "default",
            "left": "left_walk",
            "right": "right_walk",
            "drag": "drag",
            "fall": "fall",
            "on_floor": "default",
            "random_act": [
                {"name": "idle", "act_list": ["default"], "act_prob": 0.8, "act_type": [2, 0]},
                {"name": "walk", "act_list": ["left_walk", "right_walk", "default"], "act_prob": 0.2, "act_type": [3, 1]},
            ],
        }

    @staticmethod
    def _generate_act_conf(sprites):
        conf = {
            "default": {
                "images": "stand",
                "act_num": len(sprites.get("stand", [])),
                "frame_refresh": 0.5,
            },
        }

        if "leftwalk" in sprites:
            conf["left_walk"] = {
                "images": "leftwalk",
                "act_num": len(sprites["leftwalk"]),
                "need_move": True,
                "direction": "left",
                "frame_refresh": 0.2,
            }

        if "rightwalk" in sprites:
            conf["right_walk"] = {
                "images": "rightwalk",
                "act_num": len(sprites["rightwalk"]),
                "need_move": True,
                "direction": "right",
                "frame_refresh": 0.2,
            }

        if "drag" in sprites:
            conf["drag"] = {
                "images": "drag",
                "act_num": len(sprites["drag"]),
            }

        if "fall" in sprites:
            conf["fall"] = {
                "images": "fall",
                "act_num": len(sprites["fall"]),
            }

        return conf

    @staticmethod
    def test_api_connection(api_key, api_base="https://api.openai.com/v1"):
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    f"{api_base.rstrip('/')}/models",
                    headers=headers,
                )
                resp.raise_for_status()
                return True, "Connection successful"
        except httpx.HTTPStatusError as e:
            return False, f"API error: {e.response.status_code}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
