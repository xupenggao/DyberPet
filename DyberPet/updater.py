import os
import sys
import json
import shutil
import tempfile
import zipfile
import urllib.request
import urllib.error
import subprocess

from DyberPet.settings import VERSION, RELEASE_API, BASEDIR


_NO_RELEASE = '__NO_RELEASE__'
_NET_ERROR = '__NET_ERROR__'


def _make_request(url, token=None):
    """Create a Request with optional GitHub token auth header."""
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/vnd.github+json')
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
        req.add_header('X-GitHub-Api-Version', '2022-11-28')
    return req


def check_update():
    """Query GitHub API for the latest release.

    Returns (has_update, version, download_url, notes, file_size).
    On failure returns (False, error_tag, None, None, None).
    """
    from DyberPet import settings as s

    token = getattr(s, 'github_token', '')
    req = _make_request(RELEASE_API, token)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, _NO_RELEASE, None, None, None
        return False, _NET_ERROR, None, None, None
    except Exception:
        return False, _NET_ERROR, None, None, None

    tag = data.get('tag_name', '')
    notes = data.get('body', '')

    download_url = None
    file_size = 0
    for asset in data.get('assets', []):
        name = asset.get('name', '')
        if name.startswith('LingPet') and name.endswith('.zip'):
            download_url = asset.get('browser_download_url', '')
            file_size = asset.get('size', 0)
            break

    has_update = _compare(VERSION, tag)
    if not download_url:
        return has_update, tag, None, notes, 0

    return has_update, tag, download_url, notes, file_size


def _compare(local, remote):
    lv = local.lstrip('v').split('.')
    rv = remote.lstrip('v').split('.')
    for a, b in zip(lv, rv):
        if int(a) < int(b):
            return True
        if int(a) > int(b):
            return False
    return len(lv) < len(rv)


def download_update(url, progress_cb=None):
    """Download update zip to a temp file.

    Args:
        url: Download URL (GitHub asset URL, supports redirect).
        progress_cb: Callable(downloaded_bytes, total_bytes).

    Returns path to the downloaded zip, or None on failure.
    """
    from DyberPet import settings as s

    token = getattr(s, 'github_token', '')
    req = _make_request(url, token)

    tmp_dir = tempfile.mkdtemp(prefix='dyberpet_update_')
    tmp_path = os.path.join(tmp_dir, 'update.zip')

    try:
        resp = urllib.request.urlopen(req, timeout=120)

        total = int(resp.headers.get('Content-Length', 0))
        downloaded = 0
        chunk = 65536

        with open(tmp_path, 'wb') as f:
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                f.write(buf)
                downloaded += len(buf)
                if progress_cb:
                    progress_cb(downloaded, total)

        return tmp_path
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return None


def prepare_update(zip_path):
    """Extract the update zip and return the path to the extracted directory."""
    extract_dir = zip_path.replace('.zip', '_extracted')
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        entries = os.listdir(extract_dir)
        if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
            return os.path.join(extract_dir, entries[0])
        return extract_dir
    except Exception:
        return None


def launch_updater(source_dir):
    """Launch the standalone updater.exe and exit the app."""
    target_dir = _get_app_dir()
    exe_name = _get_exe_name()
    updater_exe = os.path.join(target_dir, 'updater.exe')

    if not os.path.isfile(updater_exe):
        return False

    cmd = [
        updater_exe,
        '--source', source_dir,
        '--target', target_dir,
        '--exe', exe_name,
        '--exclude', 'data',
    ]
    subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    return True


def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_exe_name():
    if getattr(sys, 'frozen', False):
        return os.path.basename(sys.executable)
    return 'LingPet.exe'
