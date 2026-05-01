# coding:utf-8
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog,
    QStackedWidget, QPushButton, QSizePolicy, QGridLayout,
    QRadioButton, QButtonGroup, QLineEdit, QComboBox,
)
from qfluentwidgets import (
    ScrollArea, PushButton, LineEdit, RadioButton, ComboBox,
    InfoBar, InfoBarPosition, StateToolTip, FluentIcon as FIF,
    CardWidget, ImageLabel, BodyLabel, SubtitleLabel, TitleLabel,
    PrimaryPushButton, ProgressRing, ExpandLayout,
)

import DyberPet.settings as settings
from .AIPetService import PetFileBuilder, STYLE_PROMPTS, STYLE_NAMES
from .AIGenerationThread import AIGenerationThread

from sys import platform

basedir = settings.BASEDIR


class PhotoPreviewCard(CardWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        pixmap = QPixmap(image_path)
        label = QLabel()
        scaled = pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(scaled)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)


class AIPetInterface(ScrollArea):
    pet_created = Signal(str)

    def __init__(self, sizeHintDyber, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("AIPetInterface")
        self.sizeHintDyber = (sizeHintDyber[0] - 100, sizeHintDyber[1])
        self._photos = []
        self._selected_style = "q_cartoon"
        self._generated_sprites = {}
        self._gen_thread = None
        self._state_tooltip = None

        self.scrollWidget = QWidget()
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        self.main_layout = QVBoxLayout(self.scrollWidget)
        self.main_layout.setContentsMargins(30, 20, 30, 20)

        # Title
        self.titleLabel = TitleLabel(self.tr("AI Pet Creator"), self)
        self.main_layout.addWidget(self.titleLabel)

        self.descLabel = BodyLabel(
            self.tr("Upload photos of your pet, and AI will generate a desktop pet character for you.")
        )
        self.main_layout.addWidget(self.descLabel)
        self.main_layout.addSpacing(10)

        # Stacked pages
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)

        self._setup_page1()
        self._setup_page2()
        self._setup_page3()
        self._setup_page4()
        self._setup_page5()

        # Navigation buttons
        nav_layout = QHBoxLayout()
        self.btn_back = PushButton(self.tr("Back"))
        self.btn_back.clicked.connect(self._go_back)
        self.btn_next = PrimaryPushButton(self.tr("Next"))
        self.btn_next.clicked.connect(self._go_next)
        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_back)
        nav_layout.addWidget(self.btn_next)
        self.main_layout.addLayout(nav_layout)

        self.btn_back.hide()
        self._update_nav_buttons()
        self.main_layout.addStretch()

    # ── Page 1: Photo Upload ──────────────────────────────────────────
    def _setup_page1(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(SubtitleLabel(self.tr("Step 1: Upload Pet Photos")))

        name_layout = QHBoxLayout()
        name_layout.addWidget(BodyLabel(self.tr("Pet Name:")))
        self.pet_name_edit = LineEdit()
        self.pet_name_edit.setPlaceholderText(self.tr("Enter a name for your pet"))
        self.pet_name_edit.setClearButtonEnabled(True)
        name_layout.addWidget(self.pet_name_edit)
        layout.addLayout(name_layout)

        btn_layout = QHBoxLayout()
        self.btn_select_photos = PushButton(self.tr("Select Photos"), self, FIF.PHOTO)
        self.btn_select_photos.clicked.connect(self._on_select_photos)
        btn_layout.addWidget(self.btn_select_photos)
        btn_layout.addWidget(BodyLabel(self.tr("(1-5 photos, support jpg/png)")))
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.photo_grid = QGridLayout()
        layout.addLayout(self.photo_grid)

        layout.addStretch()
        self.stack.addWidget(page)

    def _on_select_photos(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, self.tr("Select Pet Photos"), "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not files:
            return
        self._photos = files[:5]
        self._refresh_photo_grid()

    def _refresh_photo_grid(self):
        for i in reversed(range(self.photo_grid.count())):
            w = self.photo_grid.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        for i, path in enumerate(self._photos):
            card = PhotoPreviewCard(path)
            self.photo_grid.addWidget(card, i // 3, i % 3)

    # ── Page 2: Style Selection ───────────────────────────────────────
    def _setup_page2(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(SubtitleLabel(self.tr("Step 2: Choose Art Style")))

        self.style_group = QButtonGroup(self)
        for i, (key, label) in enumerate(STYLE_NAMES.items()):
            rb = RadioButton(self.tr(label))
            rb.setProperty("style_key", key)
            self.style_group.addButton(rb, i)
            layout.addWidget(rb)
            if i == 0:
                rb.setChecked(True)

        self.style_group.buttonClicked.connect(self._on_style_changed)
        layout.addStretch()
        self.stack.addWidget(page)

    def _on_style_changed(self, btn):
        self._selected_style = btn.property("style_key")

    # ── Page 3: API Configuration ─────────────────────────────────────
    def _setup_page3(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(SubtitleLabel(self.tr("Step 3: Configure API")))

        provider_layout = QHBoxLayout()
        provider_layout.addWidget(BodyLabel(self.tr("API Provider:")))
        self.api_provider = ComboBox()
        self.api_provider.addItems(["OpenAI", "Custom"])
        self.api_provider.currentIndexChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.api_provider)
        provider_layout.addStretch()
        layout.addLayout(provider_layout)

        base_layout = QHBoxLayout()
        base_layout.addWidget(BodyLabel(self.tr("API Base URL:")))
        self.api_base_edit = LineEdit()
        self.api_base_edit.setText("https://api.openai.com/v1")
        self.api_base_edit.setClearButtonEnabled(True)
        base_layout.addWidget(self.api_base_edit)
        layout.addLayout(base_layout)

        key_layout = QHBoxLayout()
        key_layout.addWidget(BodyLabel(self.tr("API Key:")))
        self.api_key_edit = LineEdit()
        self.api_key_edit.setPlaceholderText("sk-...")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setClearButtonEnabled(True)
        key_layout.addWidget(self.api_key_edit)
        layout.addLayout(key_layout)

        test_layout = QHBoxLayout()
        self.btn_test = PushButton(self.tr("Test Connection"), self, FIF.LINK)
        self.btn_test.clicked.connect(self._on_test_api)
        test_layout.addWidget(self.btn_test)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        # Load saved config
        if hasattr(settings, 'ai_api_key') and settings.ai_api_key:
            self.api_key_edit.setText(settings.ai_api_key)
        if hasattr(settings, 'ai_api_base') and settings.ai_api_base:
            self.api_base_edit.setText(settings.ai_api_base)

        layout.addStretch()
        self.stack.addWidget(page)

    def _on_provider_changed(self, index):
        if index == 0:
            self.api_base_edit.setText("https://api.openai.com/v1")
        else:
            self.api_base_edit.setText("")
            self.api_base_edit.setFocus()

    def _on_test_api(self):
        api_key = self.api_key_edit.text().strip()
        api_base = self.api_base_edit.text().strip()
        if not api_key:
            InfoBar.error(self.tr("Error"), self.tr("Please enter API key"),
                          parent=self, duration=3000, position=InfoBarPosition.TOP)
            return
        ok, msg = PetFileBuilder.test_api_connection(api_key, api_base)
        if ok:
            InfoBar.success(self.tr("Success"), self.tr("Connection successful"),
                            parent=self, duration=3000, position=InfoBarPosition.TOP)
        else:
            InfoBar.error(self.tr("Error"), msg,
                          parent=self, duration=5000, position=InfoBarPosition.TOP)

    # ── Page 4: Generation Progress ───────────────────────────────────
    def _setup_page4(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(SubtitleLabel(self.tr("Step 4: Generating...")))

        self.gen_status_label = BodyLabel(self.tr("Preparing to generate pet sprites..."))
        layout.addWidget(self.gen_status_label)

        self.progress_ring = ProgressRing()
        self.progress_ring.setFixedSize(60, 60)
        layout.addWidget(self.progress_ring, alignment=Qt.AlignCenter)

        self.action_status_layout = QVBoxLayout()
        layout.addLayout(self.action_status_layout)

        layout.addStretch()
        self.stack.addWidget(page)

    # ── Page 5: Preview & Confirm ─────────────────────────────────────
    def _setup_page5(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(SubtitleLabel(self.tr("Step 5: Preview & Confirm")))

        self.preview_label = BodyLabel(self.tr("Generated sprites preview:"))
        layout.addWidget(self.preview_label)

        self.preview_grid = QGridLayout()
        layout.addLayout(self.preview_grid)

        layout.addStretch()
        self.stack.addWidget(page)

    def _show_preview(self):
        for i in reversed(range(self.preview_grid.count())):
            w = self.preview_grid.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        row = 0
        for action_name, frames in self._generated_sprites.items():
            self.preview_grid.addWidget(BodyLabel(f"{action_name}:"), row, 0)
            col = 1
            for frame in frames:
                if isinstance(frame, QImage):
                    pixmap = QPixmap.fromImage(frame)
                else:
                    pixmap = frame
                label = QLabel()
                scaled = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                label.setPixmap(scaled)
                self.preview_grid.addWidget(label, row, col)
                col += 1
            row += 1

    # ── Navigation ────────────────────────────────────────────────────
    def _current_page(self):
        return self.stack.currentIndex()

    def _go_next(self):
        page = self._current_page()

        if page == 0:
            # Validate page 1
            name = self.pet_name_edit.text().strip()
            if not name:
                InfoBar.warning(self.tr("Warning"), self.tr("Please enter a pet name"),
                                parent=self, duration=3000, position=InfoBarPosition.TOP)
                return
            if not self._photos:
                InfoBar.warning(self.tr("Warning"), self.tr("Please select at least one photo"),
                                parent=self, duration=3000, position=InfoBarPosition.TOP)
                return
            # Check pet name not already exist
            pet_dir = os.path.join(basedir, "res/role", name)
            if os.path.exists(pet_dir):
                InfoBar.warning(self.tr("Warning"), self.tr("Pet name already exists, please choose another"),
                                parent=self, duration=3000, position=InfoBarPosition.TOP)
                return

        elif page == 1:
            pass  # Style always valid

        elif page == 2:
            api_key = self.api_key_edit.text().strip()
            if not api_key:
                InfoBar.warning(self.tr("Warning"), self.tr("Please enter API key"),
                                parent=self, duration=3000, position=InfoBarPosition.TOP)
                return
            # Save API config
            settings.ai_api_key = api_key
            settings.ai_api_base = self.api_base_edit.text().strip()
            if not hasattr(settings, 'ai_api_base'):
                settings.ai_api_base = "https://api.openai.com/v1"
            settings.save_settings()
            # Start generation
            self._start_generation()
            self.stack.setCurrentIndex(3)
            self._update_nav_buttons()
            return

        elif page == 3:
            # Generation in progress, skip
            return

        elif page == 4:
            # Confirm creation
            self._confirm_creation()
            return

        self.stack.setCurrentIndex(self._current_page() + 1)
        self._update_nav_buttons()

    def _go_back(self):
        idx = self._current_page()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_nav_buttons()

    def _update_nav_buttons(self):
        page = self._current_page()
        self.btn_back.setVisible(page > 0)

        if page == 0:
            self.btn_next.setText(self.tr("Next"))
        elif page == 1:
            self.btn_next.setText(self.tr("Next"))
        elif page == 2:
            self.btn_next.setText(self.tr("Generate"))
        elif page == 3:
            self.btn_next.setText(self.tr("Waiting..."))
            self.btn_next.setEnabled(False)
            self.btn_back.setEnabled(False)
        elif page == 4:
            self.btn_next.setText(self.tr("Confirm & Create"))
            self.btn_next.setEnabled(True)
            self.btn_back.setEnabled(True)
            self.btn_back.setText(self.tr("Regenerate"))

    # ── Generation ────────────────────────────────────────────────────
    def _start_generation(self):
        api_key = self.api_key_edit.text().strip()
        api_base = self.api_base_edit.text().strip() or "https://api.openai.com/v1"

        # Clear previous status labels
        for i in reversed(range(self.action_status_layout.count())):
            w = self.action_status_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        # Add status labels for each action
        self._action_labels = {}
        for action_name in ["stand", "leftwalk", "rightwalk", "drag", "fall"]:
            lbl = BodyLabel(f"  {action_name}: pending")
            self.action_status_layout.addWidget(lbl)
            self._action_labels[action_name] = lbl

        self.gen_status_label.setText(self.tr("Generating pet sprites, please wait..."))

        self._gen_thread = AIGenerationThread(
            api_key=api_key,
            api_base=api_base,
            photos=self._photos,
            style=self._selected_style,
            pet_name=self.pet_name_edit.text().strip(),
        )
        self._gen_thread.progress.connect(self._on_gen_progress)
        self._gen_thread.finished.connect(self._on_gen_complete)
        self._gen_thread.error.connect(self._on_gen_error)
        self._gen_thread.start()

    def _on_gen_progress(self, action_name, status):
        if action_name in self._action_labels:
            if status == "generating":
                self._action_labels[action_name].setText(f"  {action_name}: generating...")
            elif status == "done":
                self._action_labels[action_name].setText(f"  {action_name}: done")

    def _on_gen_complete(self, results):
        self._generated_sprites = results
        self.gen_status_label.setText(self.tr("Generation complete!"))
        self._show_preview()
        self.stack.setCurrentIndex(4)
        self._update_nav_buttons()

    def _on_gen_error(self, msg):
        self.gen_status_label.setText(self.tr(f"Generation failed: {msg}"))
        InfoBar.error(self.tr("Error"), msg,
                      parent=self, duration=8000, position=InfoBarPosition.TOP)
        self.btn_next.setEnabled(True)
        self.btn_back.setEnabled(True)
        self.btn_next.setText(self.tr("Retry"))
        self.btn_next.clicked.disconnect()

        def retry():
            self.btn_next.clicked.connect(self._go_next)
            self.stack.setCurrentIndex(2)
            self._update_nav_buttons()

        self.btn_next.clicked.connect(retry)

    # ── Confirm ───────────────────────────────────────────────────────
    def _confirm_creation(self):
        pet_name = self.pet_name_edit.text().strip()
        target_dir = os.path.join(basedir, "res/role")

        try:
            PetFileBuilder.build_pet_folder(pet_name, self._generated_sprites, target_dir)
        except Exception as e:
            InfoBar.error(self.tr("Error"), self.tr(f"Failed to create pet: {str(e)}"),
                          parent=self, duration=5000, position=InfoBarPosition.TOP)
            return

        InfoBar.success(self.tr("Success"), self.tr(f"Pet '{pet_name}' created!"),
                        parent=self, duration=3000, position=InfoBarPosition.TOP)

        self.pet_created.emit(pet_name)

        # Reset wizard
        self.stack.setCurrentIndex(0)
        self.pet_name_edit.clear()
        self._photos = []
        self._generated_sprites = {}
        self._refresh_photo_grid()
        self._update_nav_buttons()
