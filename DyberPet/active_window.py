import os
import subprocess
from dataclasses import dataclass
from sys import platform
from typing import Optional


@dataclass(frozen=True)
class WindowSurface:
    left: int
    top: int
    right: int
    bottom: int
    owner: str = ""
    handle: str = ""

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center_x(self) -> int:
        return self.left + self.width // 2

    @property
    def center_y(self) -> int:
        return self.top + self.height // 2

    def usable(self) -> bool:
        return self.width >= 80 and self.height >= 60


class ActiveWindowTracker:
    def __init__(self, current_pid: Optional[int] = None):
        self.current_pid = current_pid or os.getpid()

    def get_surface(self) -> Optional[WindowSurface]:
        if platform == "win32":
            return self._get_windows_surface()
        if platform == "darwin":
            return self._get_macos_surface()
        return None

    def _get_windows_surface(self) -> Optional[WindowSurface]:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == self.current_pid:
                return None

            if hasattr(user32, "IsIconic") and user32.IsIconic(hwnd):
                return None

            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            if class_name.value in {"Progman", "WorkerW", "Shell_TrayWnd"}:
                return None

            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return None

            surface = WindowSurface(
                int(rect.left),
                int(rect.top),
                int(rect.right),
                int(rect.bottom),
                owner=class_name.value,
                handle=str(hwnd),
            )
            return surface if surface.usable() else None
        except Exception:
            return None

    def _get_macos_surface(self) -> Optional[WindowSurface]:
        script = r'''
        tell application "System Events"
            set frontApps to application processes whose frontmost is true
            if (count of frontApps) is 0 then return ""
            set frontApp to item 1 of frontApps
            set appName to name of frontApp
            if appName contains "DyberPet" or appName contains "Python" then return ""
            if (count of windows of frontApp) is 0 then return ""
            set frontWindow to front window of frontApp
            set windowTitle to name of frontWindow
            set {xPos, yPos} to position of frontWindow
            set {wSize, hSize} to size of frontWindow
            return appName & tab & windowTitle & tab & xPos & tab & yPos & tab & wSize & tab & hSize
        end tell
        '''
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            output = result.stdout.strip()
            if not output:
                return None

            parts = output.split("\t")
            if len(parts) != 6:
                return None

            owner, title, left, top, width, height = parts
            left = int(float(left))
            top = int(float(top))
            width = int(float(width))
            height = int(float(height))

            surface = WindowSurface(
                left,
                top,
                left + width,
                top + height,
                owner=owner,
                handle=f"{owner}:{title}",
            )
            return surface if surface.usable() else None
        except Exception:
            return None
