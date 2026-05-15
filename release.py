"""
One-click release script for LingPet.

Usage:
    # Full: build + zip + upload
    python release.py v0.7.0 "更新说明"

    # Skip build, just zip existing dist and upload
    python release.py v0.7.0 "更新说明" --skip-build

    # Upload a pre-built zip directly
    python release.py v0.7.0 "更新说明" --zip path/to/LingPet-v0.7.0.zip

Prerequisite: run 'gh auth login' once to authenticate.
"""

import os
import sys
import json
import zipfile
import argparse
import subprocess


OWNER = "xupenggao"
REPO = "petupdate"
DIST_DIR = "dist/LingPet"


def _gh(*args):
    """Run a gh CLI command and return stdout."""
    cmd = ["gh"] + list(args) + ["--repo", f"{OWNER}/{REPO}", "--json"]
    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(f"[Error] gh command failed: {result.stderr.strip()}")
        sys.exit(1)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def run_build():
    print("[1/3] Building with Nuitka...")
    ret = os.system("build_nuitka.bat")
    if ret != 0:
        print("[Error] Build failed!")
        sys.exit(1)
    print("[1/3] Build complete.")


def create_zip(version):
    zip_name = f"LingPet-{version}.zip"
    zip_path = os.path.join("dist", zip_name)

    if os.path.isfile(zip_path):
        os.remove(zip_path)

    print(f"[2/3] Creating {zip_name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(DIST_DIR):
            for f in files:
                file_path = os.path.join(root, f)
                arcname = os.path.relpath(file_path, "dist")
                zf.write(file_path, arcname)

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[2/3] Zip created: {zip_name} ({size_mb:.1f} MB)")
    return zip_path


def create_release(version, notes):
    """Create a GitHub release using gh CLI."""
    print(f"  Creating release {version}...")
    cmd = [
        "gh", "release", "create", version,
        "--repo", f"{OWNER}/{REPO}",
        "--title", f"LingPet {version}",
        "--notes", notes or f"Release {version}",
    ]
    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        if "already exists" in result.stderr:
            print(f"  Release {version} already exists, uploading to it.")
        else:
            print(f"[Error] {result.stderr.strip()}")
            sys.exit(1)
    else:
        print(f"  Release created: {version}")


def upload_asset(version, zip_path):
    """Upload zip to the release using gh CLI."""
    filename = os.path.basename(zip_path)
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"  Uploading {filename} ({size_mb:.1f} MB)...")

    cmd = [
        "gh", "release", "upload", version,
        zip_path,
        "--repo", f"{OWNER}/{REPO}",
        "--clobber",
    ]
    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(f"[Error] Upload failed: {result.stderr.strip()}")
        sys.exit(1)
    print(f"  Asset uploaded: {filename}")


def main():
    parser = argparse.ArgumentParser(description="Upload LingPet release to GitHub")
    parser.add_argument("version", help="Version tag, e.g. v0.7.0")
    parser.add_argument("notes", nargs="?", default="", help="Release notes")
    parser.add_argument("--skip-build", action="store_true", help="Skip build, zip from dist/")
    parser.add_argument("--zip", help="Upload a pre-built zip file directly")
    args = parser.parse_args()

    # Check gh auth
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print("[Error] gh not authenticated. Run 'gh auth login' first.")
        sys.exit(1)

    # Verify VERSION in settings.py matches the release version
    settings_path = os.path.join("DyberPet", "settings.py")
    if os.path.isfile(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("VERSION"):
                    current_version = line.split("=")[1].strip().strip('"').strip("'")
                    if current_version != args.version.lstrip("v") and current_version != args.version:
                        print(f"[Warning] settings.py VERSION is '{current_version}' but releasing '{args.version}'")
                        print(f"  Update VERSION in DyberPet/settings.py before releasing!")
                        confirm = input("  Continue anyway? (y/N): ").strip().lower()
                        if confirm != "y":
                            sys.exit(1)
                    break
    if result.returncode != 0:
        print("[Error] gh not authenticated. Run 'gh auth login' first.")
        sys.exit(1)

    if args.zip:
        zip_path = args.zip
        if not os.path.isfile(zip_path):
            print(f"[Error] File not found: {zip_path}")
            sys.exit(1)
        name = os.path.basename(zip_path)
        if not name.startswith("LingPet") or not name.endswith(".zip"):
            print(f"[Error] Zip must start with 'LingPet' and end with '.zip', got: {name}")
            sys.exit(1)
    else:
        if not args.skip_build:
            run_build()

        if not os.path.isdir(DIST_DIR):
            print(f"[Error] {DIST_DIR} not found. Run build first or use --zip.")
            sys.exit(1)

        zip_path = create_zip(args.version)

    create_release(args.version, args.notes)
    upload_asset(args.version, zip_path)

    print(f"\nDone! Release: https://github.com/{OWNER}/{REPO}/releases/tag/{args.version}")


if __name__ == "__main__":
    main()
