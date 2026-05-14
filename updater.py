"""
Standalone updater for DyberPet / LingPet.

Launched as a separate process by the main app. Waits for the main app to exit,
copies new files over the old installation (skipping excluded directories),
then restarts the main app.

Usage:
    updater.exe --source DIR --target DIR --exe NAME [--exclude DIR]...
"""

import os
import sys
import time
import shutil
import argparse
import subprocess
import psutil


def parse_args():
    p = argparse.ArgumentParser(description='LingPet updater')
    p.add_argument('--source', required=True, help='Directory containing new version files')
    p.add_argument('--target', required=True, help='Current installation directory')
    p.add_argument('--exe', required=True, help='Main executable name (e.g. LingPet.exe)')
    p.add_argument('--exclude', nargs='*', default=['data'], help='Directory names to skip')
    return p.parse_args()


def wait_for_exit(exe_name, timeout=30):
    """Wait until no process with the given exe name is running."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        running = False
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == exe_name.lower():
                    running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if not running:
            return True
        time.sleep(0.5)
    return False


def copy_tree(source, target, excludes=None):
    """Copy files from source to target, skipping excluded directory names."""
    excludes = set(excludes or [])
    # Remove old files that no longer exist in source (skip excludes)
    for root, dirs, files in os.walk(target):
        rel = os.path.relpath(root, target)
        parts = rel.split(os.sep) if rel != '.' else []
        if any(p in excludes for p in parts):
            continue
        for f in files:
            dst = os.path.join(root, f)
            src = os.path.join(source, rel, f) if rel != '.' else os.path.join(source, f)
            if not os.path.exists(src):
                try:
                    os.remove(dst)
                except OSError:
                    pass

    # Copy new files
    for root, dirs, files in os.walk(source):
        rel = os.path.relpath(root, source)
        parts = rel.split(os.sep) if rel != '.' else []
        if any(p in excludes for p in parts):
            continue

        if rel == '.':
            dst_root = target
        else:
            dst_root = os.path.join(target, rel)

        os.makedirs(dst_root, exist_ok=True)

        # Don't copy updater.exe itself while it's running
        for f in files:
            src_path = os.path.join(root, f)
            dst_path = os.path.join(dst_root, f)
            try:
                shutil.copy2(src_path, dst_path)
            except OSError:
                pass


def main():
    args = parse_args()

    if not os.path.isdir(args.source):
        sys.exit(1)
    if not os.path.isdir(args.target):
        sys.exit(1)

    ok = wait_for_exit(args.exe)
    if not ok:
        sys.exit(1)

    copy_tree(args.source, args.target, excludes=args.exclude)

    # Cleanup temp files
    try:
        parent = os.path.dirname(args.source)
        if parent and 'dyberpet_update' in parent:
            shutil.rmtree(parent, ignore_errors=True)
    except Exception:
        pass

    # Restart main app
    exe_path = os.path.join(args.target, args.exe)
    if os.path.isfile(exe_path):
        subprocess.Popen(
            [exe_path],
            cwd=args.target,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )


if __name__ == '__main__':
    main()
