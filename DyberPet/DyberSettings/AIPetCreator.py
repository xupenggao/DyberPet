# coding:utf-8
import os

import cv2

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog,
    QStackedWidget, QGridLayout, QScrollArea,
)
from qfluentwidgets import (
    ScrollArea, PushButton, LineEdit,
    InfoBar, InfoBarPosition, FluentIcon as FIF,
    CardWidget, BodyLabel, SubtitleLabel, TitleLabel,
    PrimaryPushButton, ProgressRing, ComboBox,
)

import DyberPet.settings as settings
from .AIPetService import REQUIRED_ACTIONS, OPTIONAL_ACTIONS, ALL_ACTIONS, PetFileBuilder
from .AIGenerationThread import SpriteProcessingThread
from DyberPet.conf import CheckCharFiles

basedir = settings.BASEDIR

ACTION_ORDER = [
    "stand", "leftwalk", "sit",
    "lie", "sleep", "patpat", "drag", "prefall", "fall", "onfloor",
]

ACTION_LABELS = {
    "stand": "待机",
    "leftwalk": "向左行走",
    "sit": "坐下",
    "lie": "趴下",
    "sleep": "睡觉",
    "patpat": "被摸头",
    "drag": "被拖拽",
    "prefall": "下落预备",
    "fall": "掉落中",
    "onfloor": "落地",
}

ACTION_HINTS = {
    "stand": "5秒绿幕视频（必填）",
    "leftwalk": "5秒绿幕视频（必填）",
}

DEFAULT_ANIM_TYPES = {
    "stand": "loop", "leftwalk": "loop",
    "sit": "oneshot", "lie": "oneshot", "sleep": "oneshot",
    "patpat": "oneshot", "drag": "oneshot", "prefall": "oneshot",
    "fall": "oneshot", "onfloor": "oneshot",
}


class VideoUploadCard(CardWidget):
    def __init__(self, action_name, parent=None):
        super().__init__(parent)
        self.action_name = action_name
        self.video_path = None
        self._is_required = action_name in REQUIRED_ACTIONS
        self.anim_type = DEFAULT_ANIM_TYPES.get(action_name, "loop")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        title_row = QHBoxLayout()
        title_text = ACTION_LABELS.get(action_name, action_name)
        title_row.addWidget(BodyLabel(title_text))
        tag_text = "必填" if self._is_required else "选填"
        tag = BodyLabel(tag_text)
        tag.setStyleSheet(
            "color: white; background: #e05555; border-radius: 3px; "
            "padding: 1px 6px; font-size: 10px;"
            if self._is_required else
            "color: #888; background: #eee; border-radius: 3px; "
            "padding: 1px 6px; font-size: 10px;"
        )
        title_row.addWidget(tag)
        title_row.addStretch()

        info_layout = QVBoxLayout()
        info_layout.addLayout(title_row)
        hint_text = ACTION_HINTS.get(action_name, "5秒绿幕视频（选填）")
        hint = BodyLabel(hint_text)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        info_layout.addWidget(hint)
        layout.addLayout(info_layout, 1)

        self.preview_label = QLabel()
        self.preview_label.setFixedSize(72, 72)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px dashed #ccc; border-radius: 4px;")
        layout.addWidget(self.preview_label)

        self.anim_combo = ComboBox()
        self.anim_combo.addItems(["循环", "一次性"])
        self.anim_combo.setCurrentIndex(0 if self.anim_type == "loop" else 1)
        self.anim_combo.setFixedWidth(72)
        self.anim_combo.currentIndexChanged.connect(self._on_anim_type_changed)
        layout.addWidget(self.anim_combo)

        self.btn_upload = PushButton("上传")
        self.btn_upload.setFixedWidth(80)
        self.btn_upload.clicked.connect(self._on_upload)
        layout.addWidget(self.btn_upload)

        self.btn_clear = PushButton("", self, FIF.CLOSE)
        self.btn_clear.setFixedWidth(32)
        self.btn_clear.hide()
        self.btn_clear.clicked.connect(self._on_clear)
        layout.addWidget(self.btn_clear)

    def _on_upload(self):
        label = ACTION_LABELS.get(self.action_name, self.action_name)
        title = f"上传 {label} 绿幕视频"
        file, _ = QFileDialog.getOpenFileName(
            self, title, "",
            "视频文件 (*.mp4 *.avi *.mov *.wmv *.webm *.mkv)"
        )
        if not file:
            return

        self.video_path = file

        cap = cv2.VideoCapture(file)
        ret, frame = cap.read()
        cap.release()

        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview_label.setPixmap(scaled)
            self.preview_label.setStyleSheet("border: 1px solid #4f91ff; border-radius: 4px;")
            self.btn_clear.show()

    def _on_clear(self):
        self.video_path = None
        self.preview_label.clear()
        self.preview_label.setStyleSheet("border: 1px dashed #ccc; border-radius: 4px;")
        self.btn_clear.hide()

    def _on_anim_type_changed(self, index):
        self.anim_type = "loop" if index == 0 else "oneshot"


class AIPetInterface(ScrollArea):
    pet_created = Signal(str)

    def __init__(self, sizeHintDyber, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("AIPetInterface")
        self.sizeHintDyber = (sizeHintDyber[0] - 100, sizeHintDyber[1])
        self._generated_sprites = {}
        self._proc_thread = None

        self.scrollWidget = QWidget()
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        self.main_layout = QVBoxLayout(self.scrollWidget)
        self.main_layout.setContentsMargins(30, 20, 30, 20)

        title_row = QHBoxLayout()
        self.titleLabel = TitleLabel(self.tr("自定义桌宠形象"), self)
        title_row.addWidget(self.titleLabel)
        title_row.addStretch()

        self.btn_back = PushButton(self.tr("上一步"))
        self.btn_back.clicked.connect(self._go_back)
        self.btn_next = PrimaryPushButton(self.tr("处理"))
        self.btn_next.clicked.connect(self._go_next)
        title_row.addWidget(self.btn_back)
        title_row.addWidget(self.btn_next)
        self.main_layout.addLayout(title_row)

        self.descLabel = BodyLabel(
            self.tr("上传桌宠各动作的5秒绿幕视频，系统自动抽取20帧并去除绿色背景生成逐帧图。"
                    "站立、行走为必传，其他动作可选。"
                    "\"向右行走\"由\"向左行走\"自动镜像，无需上传。")
        )
        self.descLabel.setWordWrap(True)
        self.main_layout.addWidget(self.descLabel)
        self.main_layout.addSpacing(10)

        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)

        self._setup_page1()
        self._setup_page2()

        self.btn_back.hide()
        self._update_nav_buttons()
        self.main_layout.addStretch()

    # ── Page 1: Upload Videos ─────────────────────────────────────────────
    def _setup_page1(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(SubtitleLabel(self.tr("第一步：填写信息与上传视频")))

        name_layout = QHBoxLayout()
        name_layout.addWidget(BodyLabel(self.tr("宠物名称：")))
        self.pet_name_edit = LineEdit()
        self.pet_name_edit.setPlaceholderText(self.tr("请输入桌宠名称"))
        self.pet_name_edit.setClearButtonEnabled(True)
        name_layout.addWidget(self.pet_name_edit)
        layout.addLayout(name_layout)

        layout.addSpacing(6)

        hint = BodyLabel(
            self.tr("上传各动作的5秒绿幕视频（绿色背景），系统自动抽取20帧、去除背景并生成逐帧图。"
                    "\"向右行走\"由\"向左行走\"自动镜像，无需上传。")
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)
        layout.addSpacing(4)

        self.action_cards = {}
        for action_name in ACTION_ORDER:
            card = VideoUploadCard(action_name)
            self.action_cards[action_name] = card
            layout.addWidget(card)

        layout.addStretch()
        self.stack.addWidget(page)

    # ── Page 2: Preview & Confirm ────────────────────────────────────────
    def _setup_page2(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(SubtitleLabel(self.tr("第二步：预览与确认")))

        self.proc_status_label = BodyLabel(self.tr("正在处理视频..."))
        layout.addWidget(self.proc_status_label)

        self.progress_ring = ProgressRing()
        self.progress_ring.setFixedSize(48, 48)
        layout.addWidget(self.progress_ring, alignment=Qt.AlignCenter)

        self.action_status_layout = QVBoxLayout()
        layout.addLayout(self.action_status_layout)

        self.preview_label = BodyLabel(self.tr("提取的逐帧预览："))
        self.preview_label.hide()
        layout.addWidget(self.preview_label)

        self.preview_grid = QGridLayout()
        layout.addLayout(self.preview_grid)

        layout.addStretch()
        self.stack.addWidget(page)

    def _show_preview(self):
        self.preview_label.show()
        self.progress_ring.hide()
        for i in reversed(range(self.preview_grid.count())):
            w = self.preview_grid.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        MAX_COLS = 10
        row = 0
        for action_name, frames in self._generated_sprites.items():
            label_text = ACTION_LABELS.get(action_name, action_name)
            self.preview_grid.addWidget(BodyLabel(f"{label_text}:"), row, 0)
            col = 1
            for frame in frames:
                if isinstance(frame, QImage):
                    pixmap = QPixmap.fromImage(frame)
                else:
                    pixmap = frame
                label = QLabel()
                scaled = pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                label.setPixmap(scaled)
                self.preview_grid.addWidget(label, row, col)
                col += 1
                if col > MAX_COLS:
                    col = 0
                    row += 1
            row += 1

    # ── Navigation ───────────────────────────────────────────────────────
    def _current_page(self):
        return self.stack.currentIndex()

    def _set_page(self, index):
        self.stack.setCurrentIndex(index)
        QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(0))
        self._update_nav_buttons()

    def _go_next(self):
        page = self._current_page()

        if page == 0:
            name = self.pet_name_edit.text().strip()
            ok, result = PetFileBuilder.validate_pet_name(name)
            if not ok:
                InfoBar.warning(self.tr("警告"), self.tr(result),
                                parent=self, duration=3000, position=InfoBarPosition.TOP)
                return
            name = result
            self.pet_name_edit.setText(name)

            pet_dir = os.path.join(basedir, "res/role", name)
            if os.path.exists(pet_dir):
                InfoBar.warning(self.tr("警告"), self.tr("该桌宠名称已存在，请换一个名称"),
                                parent=self, duration=3000, position=InfoBarPosition.TOP)
                return

            videos = {}
            self._anim_types = {}
            for action_name, card in self.action_cards.items():
                if card.video_path:
                    videos[action_name] = {
                        "path": card.video_path,
                        "anim_type": card.anim_type,
                    }
                    self._anim_types[action_name] = card.anim_type

            missing_required = [
                ACTION_LABELS[a] for a in REQUIRED_ACTIONS if a not in videos
            ]
            if missing_required:
                InfoBar.warning(self.tr("警告"),
                                self.tr("请上传必传动作视频：" + "、".join(missing_required)),
                                parent=self, duration=3000, position=InfoBarPosition.TOP)
                return

            self._start_processing(videos)
            self._set_page(1)
            return

        elif page == 1:
            self._confirm_creation()
            return

    def _go_back(self):
        idx = self._current_page()
        if idx > 0:
            self._set_page(idx - 1)

    def _update_nav_buttons(self):
        page = self._current_page()
        self.btn_back.setVisible(page > 0)
        self.btn_next.setEnabled(True)
        self.btn_back.setEnabled(True)

        if page == 0:
            self.btn_next.setText(self.tr("处理"))
        elif page == 1:
            self.btn_next.setText(self.tr("确认创建"))
            self.btn_back.setText(self.tr("上一步"))

    # ── Processing ───────────────────────────────────────────────────────
    def _start_processing(self, videos):
        for i in reversed(range(self.action_status_layout.count())):
            w = self.action_status_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        self._action_labels = {}
        all_actions = list(videos.keys())
        if "leftwalk" in videos:
            all_actions.append("rightwalk")
        for action_name in all_actions:
            label_text = ACTION_LABELS.get(action_name, action_name)
            lbl = BodyLabel(f"  {label_text}：等待中")
            self.action_status_layout.addWidget(lbl)
            self._action_labels[action_name] = lbl

        self.proc_status_label.setText(self.tr("正在处理视频..."))
        self.progress_ring.show()
        self.preview_label.hide()

        self._proc_thread = SpriteProcessingThread(videos)
        self._proc_thread.progress.connect(self._on_proc_progress)
        self._proc_thread.finished.connect(self._on_proc_complete)
        self._proc_thread.error.connect(self._on_proc_error)
        self._proc_thread.start()

    def _on_proc_progress(self, action_name, status):
        if action_name in self._action_labels:
            label_text = ACTION_LABELS.get(action_name, action_name)
            if status == "processing":
                self._action_labels[action_name].setText(f"  {label_text}：处理中...")
            elif status == "done":
                self._action_labels[action_name].setText(f"  {label_text}：完成")

    def _on_proc_complete(self, results):
        self._generated_sprites = results
        self.proc_status_label.setText(self.tr("处理完成！"))
        self._show_preview()
        self.btn_next.setEnabled(True)

    def _on_proc_error(self, msg):
        self.proc_status_label.setText(self.tr(f"处理失败：{msg}"))
        self.progress_ring.hide()
        InfoBar.error(self.tr("错误"), msg,
                      parent=self, duration=8000, position=InfoBarPosition.TOP)
        self.btn_next.setEnabled(False)

    # ── Confirm ──────────────────────────────────────────────────────────
    def _confirm_creation(self):
        pet_name = self.pet_name_edit.text().strip()
        target_dir = os.path.join(basedir, "res/role")

        if not self._generated_sprites:
            InfoBar.warning(self.tr("警告"), self.tr("没有可创建的逐帧图数据"),
                            parent=self, duration=3000, position=InfoBarPosition.TOP)
            return

        try:
            pet_dir = PetFileBuilder.build_pet_folder(
                pet_name, self._generated_sprites, target_dir,
                anim_types=self._anim_types)
            stat_code, error_list = CheckCharFiles(pet_dir)
            if stat_code != 0:
                detail = "" if error_list is None else ": " + ", ".join(error_list)
                raise ValueError(f"生成的角色文件不完整 ({stat_code}){detail}")
        except Exception as e:
            InfoBar.error(self.tr("错误"), self.tr(f"创建桌宠失败：{str(e)}"),
                          parent=self, duration=5000, position=InfoBarPosition.TOP)
            return

        InfoBar.success(self.tr("成功"), self.tr(f"桌宠「{pet_name}」创建成功！"),
                        parent=self, duration=3000, position=InfoBarPosition.TOP)

        self.pet_created.emit(pet_name)

        self.pet_name_edit.clear()
        self._generated_sprites = {}
        for card in self.action_cards.values():
            card._on_clear()
        self._set_page(0)
