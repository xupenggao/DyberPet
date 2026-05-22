# coding:utf-8
import json
import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QSizePolicy
from qfluentwidgets import (
    SettingCardGroup, ScrollArea, ExpandLayout, PushButton, Slider,
    InfoBar, InfoBarPosition, PrimaryPushButton,
)

from .custom_utils import Dyber_ComboBoxSettingCard
import DyberPet.settings as settings

basedir = settings.BASEDIR

_HIDDEN_ACTIONS = {"default", "up", "down", "left", "right"}

_ACTION_LABELS = {
    "default":     "Idle",
    "up":          "Idle (Up)",
    "down":        "Idle (Down)",
    "left":        "Idle (Left)",
    "right":       "Idle (Right)",
    "stand":       "Idle",
    "left_walk":   "Walk Left",
    "right_walk":  "Walk Right",
    "leftwalk":    "Walk Left",
    "rightwalk":   "Walk Right",
    "fall_asleep": "Fall Asleep",
    "sleep":       "Sleep",
    "drag":        "Dragged",
    "fall":        "Fall",
    "onfloor":     "On Floor",
    "angry":       "Angry",
    "heart":       "Heart",
    "sit":         "Sit",
    "lie":         "Lie Down",
    "patpat":      "Pat",
    "prefall":     "Pre-fall",
}

_ACTION_LABELS_ZH = {
    "default":     "待机",
    "up":          "待机（上）",
    "down":        "待机（下）",
    "left":        "待机（左）",
    "right":       "待机（右）",
    "stand":       "待机",
    "left_walk":   "向左走",
    "right_walk":  "向右走",
    "leftwalk":    "向左走",
    "rightwalk":   "向右走",
    "fall_asleep": "入睡",
    "sleep":       "睡觉",
    "drag":        "被拖拽",
    "fall":        "下落",
    "onfloor":     "落地",
    "angry":       "生气",
    "heart":       "爱心",
    "sit":         "坐下",
    "lie":         "躺下",
    "patpat":      "抚摸",
    "prefall":     "预落下",
}


class ActSpeedCard(QWidget):
    """Single action speed setting row"""

    def __init__(self, act_name, display_name, has_move,
                 base_refresh, base_move, parent=None):
        super().__init__(parent)
        self.act_name = act_name
        self.has_move = has_move
        self.base_refresh = base_refresh
        self.base_move = base_move
        self.setFixedHeight(50)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(8)

        self.nameLabel = QLabel(display_name, self)
        self.nameLabel.setFixedWidth(80)
        layout.addWidget(self.nameLabel)

        self.speedLabel = QLabel(self.tr("Speed"), self)
        self.speedLabel.setFixedWidth(30)
        layout.addWidget(self.speedLabel)

        self.speed_slider = Slider(Qt.Horizontal, self)
        self.speed_slider.setRange(25, 400)
        self.speed_slider.setValue(100)
        layout.addWidget(self.speed_slider, 1)

        self.speed_value = QLabel("1.00x", self)
        self.speed_value.setFixedWidth(40)
        layout.addWidget(self.speed_value)
        self.speed_slider.valueChanged.connect(
            lambda value: self.speed_value.setText(f"{value / 100:.2f}x")
        )

        if has_move:
            self.moveLabel = QLabel(self.tr("Move"), self)
            self.moveLabel.setFixedWidth(30)
            layout.addWidget(self.moveLabel)

            self.move_slider = Slider(Qt.Horizontal, self)
            self.move_slider.setRange(25, 400)
            self.move_slider.setValue(100)
            layout.addWidget(self.move_slider, 1)

            self.move_value = QLabel("1.00x", self)
            self.move_value.setFixedWidth(40)
            layout.addWidget(self.move_value)
            self.move_slider.valueChanged.connect(
                lambda value: self.move_value.setText(f"{value / 100:.2f}x")
            )

        self.resetBtn = PushButton(self.tr("Reset"), self)
        self.resetBtn.setFixedSize(60, 33)
        self.resetBtn.setToolTip(self.tr("Restore default speed"))
        self.resetBtn.clicked.connect(self._reset)
        layout.addWidget(self.resetBtn)

    def sizeHint(self):
        return QSize(0, 50)

    def _reset(self):
        self.speed_slider.setValue(100)
        if self.has_move:
            self.move_slider.setValue(100)

    def get_values(self):
        speed = self.speed_slider.value() / 100
        if self.has_move:
            return {"speed": speed, "move": self.move_slider.value() / 100}
        return {"speed": speed}

    def set_values(self, data):
        if "speed" in data:
            self.speed_slider.setValue(int(data["speed"] * 100))
        if self.has_move and "move" in data:
            self.move_slider.setValue(int(data["move"] * 100))

    def refresh_language(self):
        if settings.language_code.startswith("zh"):
            self.nameLabel.setText(_ACTION_LABELS_ZH.get(self.act_name, self.act_name))
            self.speedLabel.setText("速度")
            if self.has_move:
                self.moveLabel.setText("移动")
            self.resetBtn.setText("重置")
            self.resetBtn.setToolTip("恢复默认速度")
        else:
            self.nameLabel.setText(_ACTION_LABELS.get(self.act_name, self.act_name))
            self.speedLabel.setText("Speed")
            if self.has_move:
                self.moveLabel.setText("Move")
            self.resetBtn.setText("Reset")
            self.resetBtn.setToolTip("Restore default speed")


class ActSpeedInterface(ScrollArea):
    """Action speed settings page"""

    def __init__(self, sizeHintDyber=(800, 800), parent=None):
        super().__init__(parent=parent)
        self.setObjectName("ActSpeedInterface")
        self.sizeHintDyber = sizeHintDyber

        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)
        self.titleLabel = QLabel(self.tr("Action Speed"), self)
        self.act_cards = {}

        pet_list = settings.pets
        self.petSelector = Dyber_ComboBoxSettingCard(
            pet_list,
            pet_list,
            QIcon(os.path.join(basedir, "res/icons/system/homestar.svg")),
            self.tr("Choose character"),
            self.tr("Choose the character whose action speed you want to adjust"),
            parent=self.scrollWidget,
        )
        self.petSelector.comboBox.currentTextChanged.connect(self._on_pet_changed)
        self.petSelector.comboBox.setMinimumWidth(120)
        _forward_target = self.petSelector.comboBox
        _original_release = self.petSelector.mouseReleaseEvent
        self.petSelector.mouseReleaseEvent = lambda e: (
            _original_release(e),
            _forward_target._toggleComboMenu(),
        )

        self.saveBtn = PrimaryPushButton(self.tr("Save"), self.scrollWidget)
        self.saveBtn.setFixedWidth(100)
        self.saveBtn.clicked.connect(self._on_save)

        self.speedGroup = SettingCardGroup(
            self.tr("Action Speed Settings"), self.scrollWidget
        )

        self.__initWidget()

        if pet_list:
            self._load_pet(pet_list[0])

    def __initWidget(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 75, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.__setQss()
        self.__initLayout()

    def __initLayout(self):
        self.titleLabel.move(50, 20)
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(60, 10, 60, 0)
        self.expandLayout.addWidget(self.petSelector)
        self.expandLayout.addWidget(self.saveBtn)
        self.expandLayout.addWidget(self.speedGroup)

    def __setQss(self):
        self.scrollWidget.setObjectName("scrollWidget")
        self.titleLabel.setObjectName("settingLabel")

        theme = "light"
        with open(
            os.path.join(basedir, "res/icons/system/qss", theme, "setting_interface.qss"),
            encoding="utf-8",
        ) as f:
            self.setStyleSheet(f.read())

    def _on_pet_changed(self, pet_name):
        self._load_pet(pet_name)

    def _get_action_label(self, act_name):
        if settings.language_code.startswith("zh"):
            return _ACTION_LABELS_ZH.get(act_name, act_name)
        return _ACTION_LABELS.get(act_name, act_name)

    def _load_pet(self, pet_name):
        self.act_cards.clear()

        group_width = self.speedGroup.width()
        self.speedGroup.hide()
        self.speedGroup = SettingCardGroup(
            self.tr("Action Speed Settings"), self.scrollWidget
        )
        if group_width > 0:
            self.speedGroup.resize(group_width, self.speedGroup.height())
        self.speedGroup.show()
        self.expandLayout.addWidget(self.speedGroup)

        act_path = os.path.join(basedir, f"res/role/{pet_name}/act_conf.json")
        if not os.path.isfile(act_path):
            return

        with open(act_path, "r", encoding="utf-8") as f:
            act_conf = json.load(f)

        # Load saved multipliers and original base values
        saved = settings.act_speed.get(pet_name, {})

        for act_name, conf in act_conf.items():
            if act_name in _HIDDEN_ACTIONS:
                continue

            has_move = conf.get("need_move", False)
            display_name = self._get_action_label(act_name)

            # Determine base values:
            # If we have saved base values use them (preserves originals),
            # otherwise use current file values as base.
            act_saved = saved.get(act_name, {})
            base_refresh = act_saved.get("base_refresh", conf.get("frame_refresh", 0.08))
            base_move = act_saved.get("base_move", conf.get("frame_move", 3.0))

            card = ActSpeedCard(
                act_name, display_name, has_move,
                base_refresh, base_move, self.speedGroup,
            )
            card.show()

            # Restore saved multiplier if exists
            if act_saved:
                card.set_values(act_saved)

            self.speedGroup.addSettingCard(card)
            self.act_cards[act_name] = card

    def refresh_language(self):
        if settings.language_code.startswith("zh"):
            self.titleLabel.setText("动作速度")
            self.petSelector.setTitle("选择角色")
            self.petSelector.setContent("选择要调整动作速度的角色")
            self.saveBtn.setText("保存")
            self.speedGroup.titleLabel.setText("动作速度设置")
        else:
            self.titleLabel.setText("Action Speed")
            self.petSelector.setTitle("Choose character")
            self.petSelector.setContent("Choose the character whose action speed you want to adjust")
            self.saveBtn.setText("Save")
            self.speedGroup.titleLabel.setText("Action Speed Settings")

        for card in self.act_cards.values():
            card.refresh_language()

    def _on_save(self):
        pet_name = self.petSelector.comboBox.currentText()
        if not pet_name:
            return

        act_path = os.path.join(basedir, f"res/role/{pet_name}/act_conf.json")
        if not os.path.isfile(act_path):
            return

        with open(act_path, "r", encoding="utf-8") as f:
            act_conf = json.load(f)

        pet_speeds = {}
        for act_name, card in self.act_cards.items():
            values = card.get_values()
            speed = values["speed"]
            move = values.get("move", 1.0)

            entry = {"speed": speed, "base_refresh": card.base_refresh}
            if card.has_move:
                entry["move"] = move
                entry["base_move"] = card.base_move
            pet_speeds[act_name] = entry

            if act_name in act_conf:
                act_conf[act_name]["frame_refresh"] = card.base_refresh / speed
                if card.has_move:
                    act_conf[act_name]["frame_move"] = card.base_move * move

        with open(act_path, "w", encoding="utf-8") as f:
            json.dump(act_conf, f, indent=4, ensure_ascii=False)

        if pet_speeds:
            settings.act_speed[pet_name] = pet_speeds
        else:
            settings.act_speed.pop(pet_name, None)
        settings.save_settings()

        InfoBar.warning(
            "",
            self.tr("Settings saved. Restart the app to apply them."),
            duration=3000,
            position=InfoBarPosition.BOTTOM,
            parent=self.window(),
        )
