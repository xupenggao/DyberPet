# coding:utf-8
import os
import json
import urllib.request
from sys import platform

from qfluentwidgets import (SettingCardGroup, SwitchSettingCard, HyperlinkCard,InfoBar,
                            ComboBoxSettingCard, ScrollArea, ExpandLayout, InfoBarPosition,
                            setThemeColor, PushButton, setFont, MessageBox)

from qfluentwidgets import FluentIcon as FIF
from PySide6.QtCore import Qt, Signal, QUrl, QStandardPaths, QLocale, QThread
from PySide6.QtGui import QDesktopServices, QIcon, QFont, QPixmap
from PySide6.QtWidgets import QWidget, QLabel, QApplication, QSizePolicy, QDialog, QVBoxLayout, QProgressDialog
#from qframelesswindow import FramelessWindow

from .custom_utils import Dyber_RangeSettingCard, Dyber_ComboBoxSettingCard, CustomColorSettingCard
import DyberPet.settings as settings
from DyberPet.updater import check_update, download_update, prepare_update, launch_updater

basedir = settings.BASEDIR
module_path = os.path.join(basedir, 'DyberPet/DyberSettings/')
'''
if platform == 'win32':
    basedir = ''
    module_path = 'DyberPet/DyberSettings/'
else:
    #from pathlib import Path
    basedir = os.path.dirname(__file__) #Path(os.path.dirname(__file__))
    #basedir = basedir.parent
    basedir = basedir.replace('\\','/')
    basedir = '/'.join(basedir.split('/')[:-2])

    module_path = os.path.join(basedir, 'DyberPet/DyberSettings/')
'''


class SettingInterface(ScrollArea):
    """ Setting interface """

    ontop_changed = Signal(name='ontop_changed')
    scale_changed = Signal(name='scale_changed')
    lang_changed = Signal(name='lang_changed')
    walk_on_window_changed = Signal(name='walk_on_window_changed')

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("SettingInterface")
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # setting label
        self.settingLabel = QLabel(self.tr("基本设置"), self)

        self.contactAuthorBtn = PushButton(self.tr("联系作者"), self, FIF.PEOPLE)
        self.contactAuthorBtn.setSizePolicy(QSizePolicy.Maximum, self.contactAuthorBtn.sizePolicy().verticalPolicy())
        self.contactAuthorBtn.clicked.connect(self.__onContactAuthor)

        # Mode =========================================================================================
        self.ModeGroup = SettingCardGroup(self.tr('模式'), self.scrollWidget)
        # Always on top
        self.AlwaysOnTopCard = SwitchSettingCard(
            FIF.PIN,
            self.tr("窗口置顶"),
            self.tr("开启后桌宠将始终显示在其他应用窗口之上"),
            parent=self.ModeGroup #DisplayModeGroup
        )
        if settings.on_top_hint:
            self.AlwaysOnTopCard.setChecked(True)
        else:
            self.AlwaysOnTopCard.setChecked(False)
        self.AlwaysOnTopCard.switchButton.checkedChanged.connect(self._AlwaysOnTopChanged)

        # Allow drop
        self.AllowDropCard = SwitchSettingCard(
            QIcon(os.path.join(basedir, 'res/icons/system/falldown.svg')),
            self.tr("允许掉落"),
            self.tr("鼠标释放后，桌宠掉落到地面（开）或停留在原位（关）"),
            parent=self.ModeGroup #DisplayModeGroup
        )
        if settings.set_fall:
            self.AllowDropCard.setChecked(True)
        else:
            self.AllowDropCard.setChecked(False)
        self.AllowDropCard.switchButton.checkedChanged.connect(self._AllowDropChanged)

        # Walk on active foreground window
        self.WalkOnWindowCard = SwitchSettingCard(
            QIcon(os.path.join(basedir, 'res/icons/system/gravity.svg')),
            self.tr("前台窗口巡游"),
            self.tr("桌宠偶尔会走到当前前台窗口上方活动，然后返回原位"),
            parent=self.ModeGroup
        )
        if settings.walk_on_active_window:
            self.WalkOnWindowCard.setChecked(True)
        else:
            self.WalkOnWindowCard.setChecked(False)
        self.WalkOnWindowCard.switchButton.checkedChanged.connect(self._WalkOnWindowChanged)
        if platform not in ['win32', 'darwin']:
            self.WalkOnWindowCard.switchButton.indicator.setEnabled(False)

        # Walk only (no idle actions during window excursion)
        self.WalkOnlyCard = SwitchSettingCard(
            QIcon(os.path.join(basedir, 'res/icons/system/gravity.svg')),
            self.tr("仅步行"),
            self.tr("开启后桌宠在前台窗口上方时只进行步行动作，不穿插随机动作"),
            parent=self.ModeGroup
        )
        if settings.walk_only:
            self.WalkOnlyCard.setChecked(True)
        else:
            self.WalkOnlyCard.setChecked(False)
        self.WalkOnlyCard.switchButton.checkedChanged.connect(self._WalkOnlyChanged)
        if not settings.walk_on_active_window:
            self.WalkOnlyCard.switchButton.indicator.setEnabled(False)

        # Auto-Lock
        self.AutoLockCard = SwitchSettingCard(
            QIcon(os.path.join(basedir, 'res/icons/system/lock.svg')),
            self.tr("自动锁定"),
            self.tr("锁屏时暂停饱食度和好感度变化（仅支持 Windows）"),
            parent=self.ModeGroup #DisplayModeGroup
        )
        if settings.auto_lock:
            self.AutoLockCard.setChecked(True)
        else:
            self.AutoLockCard.setChecked(False)
        self.AutoLockCard.switchButton.checkedChanged.connect(self._AutoLockChanged)
        if platform != 'win32':
            self.AutoLockCard.switchButton.indicator.setEnabled(False)


        # Interaction parameters =======================================================================
        self.InteractionGroup = SettingCardGroup(self.tr('交互'), self.scrollWidget)
        self.GravityCard = Dyber_RangeSettingCard(
            1, 200, 0.01,
            QIcon(os.path.join(basedir, 'res/icons/system/gravity.svg')),
            self.tr("重力"),
            self.tr("桌宠掉落的加速度"),
            parent=self.InteractionGroup
        )

        self.GravityCard.setValue(int(settings.gravity*100))
        self.GravityCard.slider.valueChanged.connect(self._GravityChanged)

        self.DragCard = Dyber_RangeSettingCard(
            0, 200, 0.01,
            QIcon(os.path.join(basedir, 'res/icons/system/mousedrag.svg')),
            self.tr("拖拽速度"),
            self.tr("鼠标拖拽桌宠的速度系数"),
            parent=self.InteractionGroup
        )
        self.DragCard.setValue(int(settings.fixdragspeedx*100))
        self.DragCard.slider.valueChanged.connect(self._DragChanged)


        # Notification parameters ======================================================================
        self.VolumnGroup = SettingCardGroup(self.tr('通知'), self.scrollWidget)
        self.VolumnCard = Dyber_RangeSettingCard(
            0, 10, 0.1,
            QIcon(os.path.join(basedir, 'res/icons/system/speaker.svg')),
            self.tr("音量"),
            self.tr("通知和桌宠的音量大小"),
            parent=self.VolumnGroup
        )
        self.VolumnCard.setValue(int(settings.volume*10))
        self.VolumnCard.slider.valueChanged.connect(self._VolumnChanged)

        self.AllowToasterCard = SwitchSettingCard(
            QIcon(os.path.join(basedir, 'res/icons/system/popup.svg')),
            self.tr("弹窗通知"),
            self.tr("开启后通知将以弹窗形式显示在屏幕右下角"),
            parent=self.VolumnGroup
        )
        if settings.toaster_on:
            self.AllowToasterCard.setChecked(True)
        else:
            self.AllowToasterCard.setChecked(False)
        self.AllowToasterCard.switchButton.checkedChanged.connect(self._AllowToasterChanged)

        self.AllowBubbleCard = SwitchSettingCard(
            QIcon(os.path.join(basedir, 'res/icons/system/bubble.svg')),
            self.tr("对话气泡"),
            self.tr("开启后桌宠头顶会弹出各种类型的气泡对话"),
            parent=self.VolumnGroup
        )
        if settings.bubble_on:
            self.AllowBubbleCard.setChecked(True)
        else:
            self.AllowBubbleCard.setChecked(False)
        self.AllowBubbleCard.switchButton.checkedChanged.connect(self._AllowBubbleChanged)

        # Offline companion parameters ==============================================================
        self.CompanionGroup = SettingCardGroup(self.tr('Offline Companion'), self.scrollWidget)

        self.CompanionEnabledCard = SwitchSettingCard(
            QIcon(os.path.join(basedir, 'res/icons/system/bubble.svg')),
            self.tr("离线陪伴互动"),
            self.tr("使用本地规则驱动的陪伴气泡，无需联网 AI"),
            parent=self.CompanionGroup
        )
        self.CompanionEnabledCard.setChecked(settings.companion_enabled)
        self.CompanionEnabledCard.switchButton.checkedChanged.connect(self._CompanionEnabledChanged)

        self.CompanionProactiveCard = SwitchSettingCard(
            QIcon(os.path.join(basedir, 'res/icons/system/popup.svg')),
            self.tr("主动陪伴气泡"),
            self.tr("允许桌宠偶尔主动冒出一条温柔的陪伴气泡"),
            parent=self.CompanionGroup
        )
        self.CompanionProactiveCard.setChecked(settings.companion_proactive)
        self.CompanionProactiveCard.switchButton.checkedChanged.connect(self._CompanionProactiveChanged)

        self.CompanionContextualCard = SwitchSettingCard(
            QIcon(os.path.join(basedir, 'res/icons/system/character.svg')),
            self.tr("工作场景陪伴"),
            self.tr("在 IDE、设计或办公软件中工作时显示低频陪伴气泡"),
            parent=self.CompanionGroup
        )
        self.CompanionContextualCard.setChecked(settings.companion_contextual)
        self.CompanionContextualCard.switchButton.checkedChanged.connect(self._CompanionContextualChanged)

        self.CompanionNightCard = SwitchSettingCard(
            QIcon(os.path.join(basedir, 'res/icons/moon.svg')),
            self.tr("深夜陪伴提醒"),
            self.tr("深夜时段允许更柔和、更低频的陪伴气泡"),
            parent=self.CompanionGroup
        )
        self.CompanionNightCard.setChecked(settings.companion_night)
        self.CompanionNightCard.switchButton.checkedChanged.connect(self._CompanionNightChanged)

        freq_labels = [self.tr('低'), self.tr('中'), self.tr('高')]
        self.companionFrequencyCard = Dyber_ComboBoxSettingCard(
            freq_labels,
            ['low', 'medium', 'high'],
            QIcon(os.path.join(basedir, 'res/icons/system/more.svg')),
            self.tr('互动频率'),
            self.tr('选择离线陪伴气泡的互动频率'),
            parent=self.CompanionGroup
        )
        self.companionFrequencyCard.comboBox.setCurrentIndex(['low', 'medium', 'high'].index(settings.companion_frequency))
        self.companionFrequencyCard.comboBox.currentIndexChanged.connect(self._CompanionFrequencyChanged)

        # Personalization ==============================================================================
        self.PersonalGroup = SettingCardGroup(self.tr('个性化'), self.scrollWidget)
        self.ScaleCard = Dyber_RangeSettingCard(
            1, 50, 0.1,
            QIcon(os.path.join(basedir, 'res/icons/system/resize.svg')),
            self.tr("桌宠大小"),
            self.tr("调整桌宠的显示大小"),
            parent=self.PersonalGroup
        )
        self.ScaleCard.setValue(int(settings.tunable_scale*10))
        self.ScaleCard.slider.valueChanged.connect(self._ScaleChanged)

        pet_list = settings.pets
        self.DefaultPetCard = Dyber_ComboBoxSettingCard(
            pet_list,
            pet_list,
            QIcon(os.path.join(basedir, 'res/icons/system/homestar.svg')),
            self.tr('默认桌宠'),
            self.tr('每次启动应用时显示的桌宠角色'),
            parent=self.PersonalGroup
        )
        self.DefaultPetCard.comboBox.currentTextChanged.connect(self._DefaultPetChanged)

        lang_choices = list(settings.lang_dict.keys())
        lang_now = lang_choices[list(settings.lang_dict.values()).index(settings.language_code)]
        lang_choices.remove(lang_now)
        lang_choices = [lang_now] + lang_choices
        self.languageCard = Dyber_ComboBoxSettingCard(
            lang_choices,
            lang_choices,
            FIF.LANGUAGE,
            self.tr('Language/语言'),
            self.tr('设置界面显示语言'),
            parent=self.PersonalGroup
        )
        self.languageCard.comboBox.currentTextChanged.connect(self._LanguageChanged)

        self.themeColorCard = CustomColorSettingCard(
            FIF.PALETTE,
            self.tr('主题色'),
            self.tr('更改应用的主题配色'),
            self.PersonalGroup
        )
        self.themeColorCard.colorChanged.connect(self.colorChanged)

        # Update section ================================================================
        self.UpdateGroup = SettingCardGroup(self.tr('更新'), self.scrollWidget)
        self.checkUpdateBtn = PushButton(self.tr('检查更新'), self, FIF.SYNC)
        self.checkUpdateBtn.setFixedHeight(36)
        self.checkUpdateBtn.clicked.connect(self._onCheckUpdate)

        self.versionLabel = QLabel(
            self.tr('当前版本：') + settings.VERSION,
            self.scrollWidget
        )
        self.versionLabel.setStyleSheet('color: #666; padding-left: 12px;')


        self.__initWidget()

    def __initWidget(self):
        #self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 75, 0, 20)
        self.setWidget(self.scrollWidget)
        #self.scrollWidget.resize(1000, 800)
        self.setWidgetResizable(True)

        # initialize style sheet
        self.__setQss()

        # initialize layout
        self.__initLayout()
        #self.__connectSignalToSlot()

    def __initLayout(self):
        self.settingLabel.move(50, 20)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.contactAuthorBtn.move(self.width() - self.contactAuthorBtn.width() - 60, 20)

        # add cards to group
        self.ModeGroup.addSettingCard(self.AlwaysOnTopCard)
        self.ModeGroup.addSettingCard(self.AllowDropCard)
        self.ModeGroup.addSettingCard(self.WalkOnWindowCard)
        self.ModeGroup.addSettingCard(self.WalkOnlyCard)
        self.ModeGroup.addSettingCard(self.AutoLockCard)

        self.InteractionGroup.addSettingCard(self.GravityCard)
        self.InteractionGroup.addSettingCard(self.DragCard)

        self.VolumnGroup.addSettingCard(self.VolumnCard)
        self.VolumnGroup.addSettingCard(self.AllowToasterCard)
        self.VolumnGroup.addSettingCard(self.AllowBubbleCard)

        self.CompanionGroup.addSettingCard(self.CompanionEnabledCard)
        self.CompanionGroup.addSettingCard(self.CompanionProactiveCard)
        self.CompanionGroup.addSettingCard(self.CompanionContextualCard)
        self.CompanionGroup.addSettingCard(self.CompanionNightCard)
        self.CompanionGroup.addSettingCard(self.companionFrequencyCard)

        self.PersonalGroup.addSettingCard(self.ScaleCard)
        self.PersonalGroup.addSettingCard(self.DefaultPetCard)
        self.PersonalGroup.addSettingCard(self.languageCard)
        self.PersonalGroup.addSettingCard(self.themeColorCard)

        self.UpdateGroup.addSettingCard(self.checkUpdateBtn)
        self.UpdateGroup.addSettingCard(self.versionLabel)

        # add setting card group to layout
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(60, 10, 60, 0)

        self.expandLayout.addWidget(self.ModeGroup)
        self.expandLayout.addWidget(self.InteractionGroup)
        self.expandLayout.addWidget(self.VolumnGroup)
        self.expandLayout.addWidget(self.CompanionGroup)
        self.expandLayout.addWidget(self.PersonalGroup)
        self.expandLayout.addWidget(self.UpdateGroup)

    def __setQss(self):
        """ set style sheet """
        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')

        theme = 'light' #if isDarkTheme() else 'light'
        with open(os.path.join(basedir, 'res/icons/system/qss/', theme, 'setting_interface.qss'), encoding='utf-8') as f:
            self.setStyleSheet(f.read())

    def _AlwaysOnTopChanged(self, isChecked):
        if isChecked:
            settings.on_top_hint = True
            settings.save_settings()
            self.ontop_changed.emit()
        else:
            settings.on_top_hint = False
            settings.save_settings()
            self.ontop_changed.emit()

    def _AllowDropChanged(self, isChecked):
        if isChecked:
            settings.set_fall = True
        else:
            settings.set_fall = False
        settings.save_settings()

    def _WalkOnWindowChanged(self, isChecked):
        if isChecked:
            settings.walk_on_active_window = True
            if not settings.on_top_hint:
                settings.on_top_hint = True
                self.AlwaysOnTopCard.setChecked(True)
            self.WalkOnlyCard.switchButton.indicator.setEnabled(True)
        else:
            settings.walk_on_active_window = False
            self.WalkOnlyCard.switchButton.indicator.setEnabled(False)
        settings.save_settings()
        self.walk_on_window_changed.emit()

    def _WalkOnlyChanged(self, isChecked):
        if isChecked:
            settings.walk_only = True
        else:
            settings.walk_only = False
        settings.save_settings()

    def _AutoLockChanged(self, isChecked):
        if isChecked:
            settings.auto_lock = True
        else:
            settings.auto_lock = False
        settings.save_settings()

    def _GravityChanged(self, value):
        settings.gravity = value*0.01
        settings.save_settings()

    def _DragChanged(self, value):
        settings.fixdragspeedx, settings.fixdragspeedy = value*0.01, value*0.01
        settings.save_settings()

    def _VolumnChanged(self, value):
        settings.volume = round(value*0.1, 3)
        settings.save_settings()

    def _ScaleChanged(self, value):
        settings.tunable_scale = value*0.1
        settings.scale_dict[settings.petname] = settings.tunable_scale
        settings.save_settings()
        self.scale_changed.emit()

    def _update_scale(self):
        self.ScaleCard.setValue(int(settings.tunable_scale*10))

    def _DefaultPetChanged(self, value):
        settings.default_pet = value
        settings.save_settings()

    def refresh_default_pet(self):
        combo = self.DefaultPetCard.comboBox
        combo.blockSignals(True)
        combo.clear()
        pet_list = settings.pets
        for pet in pet_list:
            combo.addItem(pet, userData=pet)
        if settings.default_pet in pet_list:
            combo.setCurrentText(settings.default_pet)
        elif pet_list:
            combo.setCurrentText(pet_list[0])
        combo.blockSignals(False)

    def _LanguageChanged(self, value):
        settings.language_code = settings.lang_dict[value]
        settings.save_settings()
        settings.change_translator(settings.lang_dict[value])
        #self.retranslateUi()
        self.__showRestartTooltip()
        self.lang_changed.emit()
    
    def __showRestartTooltip(self):
        """ show restart tooltip """
        InfoBar.warning(
            '',
            self.tr('Configuration takes effect after restart\n此设置在重启后生效'),
            duration=3000,
            position=InfoBarPosition.BOTTOM,
            parent=self.window()
        )

    def colorChanged(self, color_str):
        setThemeColor(color_str)
        settings.themeColor = color_str
        settings.save_settings()

    def _checkUpdate(self):
        local_version = settings.VERSION
        success, github_version = get_latest_version()
        if success:
            update_needed = compare_versions(local_version, github_version)
            if update_needed:
                return True, local_version + "  " + self.tr("有新版本可用")
            else:
                return False, local_version + "  " + self.tr("已是最新版本")
        else:
            return False, self.tr("检查更新失败，请检查网络连接")

    def _onCheckUpdate(self):
        self.checkUpdateBtn.setEnabled(False)
        self.checkUpdateBtn.setText(self.tr('检查中...'))

        self._update_thread = _CheckUpdateThread()
        self._update_thread.finished.connect(self._onUpdateChecked)
        self._update_thread.start()

    def _onUpdateChecked(self):
        from DyberPet.updater import _NO_RELEASE, _NET_ERROR

        has_update, version, url, notes, size = self._update_thread.result
        self.checkUpdateBtn.setEnabled(True)
        self.checkUpdateBtn.setText(self.tr('检查更新'))

        if not has_update:
            if version == _NO_RELEASE:
                InfoBar.info(
                    '', self.tr('暂未发布新版本'),
                    duration=3000, position=InfoBarPosition.BOTTOM, parent=self.window()
                )
            elif version and version not in (_NO_RELEASE, _NET_ERROR):
                InfoBar.success(
                    '', self.tr('已是最新版本 ') + version,
                    duration=3000, position=InfoBarPosition.BOTTOM, parent=self.window()
                )
            else:
                InfoBar.warning(
                    '', self.tr('检查更新失败，请检查网络连接'),
                    duration=4000, position=InfoBarPosition.BOTTOM, parent=self.window()
                )
            return

        if not url:
            InfoBar.info(
                '', self.tr('发现新版本 ') + version + self.tr('，但安装包尚未上传，请稍后再试'),
                duration=5000, position=InfoBarPosition.BOTTOM, parent=self.window()
            )
            return

        msg = MessageBox(
            self.tr('发现新版本 ') + version,
            (notes or self.tr('无更新说明')) + '\n\n' + self.tr('是否立即下载并更新？'),
            self.window()
        )
        msg.yesButton.setText(self.tr('立即更新'))
        msg.cancelButton.setText(self.tr('稍后再说'))
        if msg.exec():
            self._start_download(url)

    def _start_download(self, url):
        self._progress = QProgressDialog(self.tr('正在下载更新...'), None, 0, 100, self.window())
        self._progress.setWindowTitle(self.tr('下载更新'))
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.setValue(0)

        self._download_thread = _DownloadThread(url)
        self._download_thread.progress.connect(self._onDownloadProgress)
        self._download_thread.finished.connect(self._onDownloadFinished)
        self._download_thread.start()

    def _onDownloadProgress(self, downloaded, total):
        if total > 0:
            self._progress.setValue(int(downloaded / total * 100))

    def _onDownloadFinished(self):
        zip_path = self._download_thread.result
        if hasattr(self, '_progress'):
            self._progress.close()

        if not zip_path:
            InfoBar.error(
                '', self.tr('下载失败，请重试'),
                duration=3000, position=InfoBarPosition.BOTTOM, parent=self.window()
            )
            return

        source_dir = prepare_update(zip_path)
        if not source_dir:
            InfoBar.error(
                '', self.tr('解压更新包失败'),
                duration=3000, position=InfoBarPosition.BOTTOM, parent=self.window()
            )
            return

        ok = launch_updater(source_dir)
        if ok:
            QApplication.quit()
        else:
            InfoBar.error(
                '', self.tr('启动更新程序失败，请手动下载更新'),
                duration=3000, position=InfoBarPosition.BOTTOM, parent=self.window()
            )
        
    def _AllowToasterChanged(self, isChecked):
        if isChecked:
            settings.toaster_on = True
        else:
            settings.toaster_on = False
        settings.save_settings()

    def _AllowBubbleChanged(self, isChecked):
        if isChecked:
            settings.bubble_on = True
        else:
            settings.bubble_on = False
        settings.save_settings()

    def _CompanionEnabledChanged(self, isChecked):
        settings.companion_enabled = isChecked
        settings.save_settings()

    def _CompanionProactiveChanged(self, isChecked):
        settings.companion_proactive = isChecked
        settings.save_settings()

    def _CompanionContextualChanged(self, isChecked):
        settings.companion_contextual = isChecked
        settings.save_settings()

    def _CompanionNightChanged(self, isChecked):
        settings.companion_night = isChecked
        settings.save_settings()

    def _CompanionFrequencyChanged(self, index):
        values = ['low', 'medium', 'high']
        if 0 <= index < len(values):
            settings.companion_frequency = values[index]
            settings.save_settings()

    def __onContactAuthor(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("联系作者"))
        dialog.setFixedSize(350, 400)

        layout = QVBoxLayout(dialog)

        titleLabel = QLabel(self.tr("微信二维码"))
        titleLabel.setAlignment(Qt.AlignCenter)
        setFont(titleLabel, 16, QFont.DemiBold)
        layout.addWidget(titleLabel)

        qrPath = os.path.join(basedir, 'res/img/IMG_9227.jpg')
        pixmap = QPixmap(qrPath)
        if not pixmap.isNull():
            scaledPixmap = pixmap.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            imgLabel = QLabel()
            imgLabel.setPixmap(scaledPixmap)
            imgLabel.setAlignment(Qt.AlignCenter)
            layout.addWidget(imgLabel, 0, Qt.AlignCenter)

            hintLabel = QLabel(self.tr("扫码添加微信"))
            hintLabel.setAlignment(Qt.AlignCenter)
            layout.addWidget(hintLabel)
        else:
            errorLabel = QLabel(self.tr("二维码图片未找到"))
            errorLabel.setAlignment(Qt.AlignCenter)
            layout.addWidget(errorLabel)

        dialog.exec()





def get_latest_version():
    url = settings.RELEASE_API
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read())
            return True, data['tag_name']
    except Exception as e:
        return False, None

def compare_versions(local_version, github_version):
    # Remove 'v' prefix from version strings
    local_version = local_version.lstrip('v')
    github_version = github_version.lstrip('v')

    # Split version strings into their components
    local_parts = local_version.split('.')
    github_parts = github_version.split('.')

    # Convert version components to integers
    local_numbers = [int(part) for part in local_parts]
    github_numbers = [int(part) for part in github_parts]

    # Compare each component
    for local, github in zip(local_numbers, github_numbers):
        if local < github:
            return True  # User should update
        elif local > github:
            return False  # Local version is ahead

    # If all components are equal, check for additional components
    if len(local_numbers) < len(github_numbers):
        return True  # User should update
    else:
        return False  # Local version is up to date or ahead


class _CheckUpdateThread(QThread):
    """Background thread to check for updates via Gitee API."""

    def run(self):
        self.result = check_update()


class _DownloadThread(QThread):
    """Background thread to download the update zip."""

    progress = Signal(int, int)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.result = None

    def run(self):
        def _progress_cb(downloaded, total):
            self.progress.emit(downloaded, total)

        self.result = download_update(self.url, progress_cb=_progress_cb)
