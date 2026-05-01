# coding:utf-8
from PySide6.QtCore import QThread, Signal
from .AIPetService import AIPetGenerator


class AIGenerationThread(QThread):
    progress = Signal(str, str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api_key, api_base, photos, style, pet_name, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.api_base = api_base
        self.photos = photos
        self.style = style
        self.pet_name = pet_name
        self._generator = None

    def run(self):
        self._generator = AIPetGenerator(self.api_key, self.api_base)
        self._generator.progress_updated.connect(self.progress.emit)
        self._generator.generation_complete.connect(self.finished.emit)
        self._generator.generation_error.connect(self.error.emit)
        self._generator.generate_pet_sprites(
            self.photos, self.style, self.pet_name
        )

    def cancel(self):
        if self._generator:
            self._generator.cancel()
