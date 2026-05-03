# coding:utf-8
from PySide6.QtCore import QThread, Signal
from .AIPetService import SpriteSheetProcessor


class SpriteProcessingThread(QThread):
    progress = Signal(str, str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, videos, parent=None):
        super().__init__(parent)
        self.videos = videos
        self._processor = None

    def run(self):
        self._processor = SpriteSheetProcessor()
        self._processor.progress_updated.connect(self.progress.emit)
        self._processor.processing_complete.connect(self.finished.emit)
        self._processor.processing_error.connect(self.error.emit)
        self._processor.process_uploaded_videos(self.videos)

    def cancel(self):
        if self._processor:
            self._processor.cancel()
