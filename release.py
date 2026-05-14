"""
One-click release script for LingPet.

Usage:
    # Full: build + zip + upload
    python release.py v0.7.0 "更新说明"

    # Skip build, just zip existing dist and upload
    python release.py v0.7.0 "更新说明" --skip-build

    # Upload a pre-built zip directly
    python release.py v0.7.0 "更新说明" --zip path/to/LingPet-v0.7.0.zip
"""

import os
import sys
import json
import shutil
import zipfile
import argparse
import urllib.request
import urllib.error
import urllib.parse


GITHUB_API = "https://api.github.com"
OWNER = "xupenggao"
REPO = "petupdate"
DIST_DIR = "dist/LingPet"


def load_token():
    """Load GitHub token from env or settings file."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return token

    settings_path = os.path.join("data", "settings.json")
    if os.path.isfile(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        token = data.get("github_token", "")

    if not token:
        print("[Error] GitHub token not found. Set GITHUB_TOKEN env var or add 'github_token' to data/settings.json")
        sys.exit(1)
    return token


def _api_request(url, token, method="GET", data=None, content_type=None):
    """Make a GitHub API request with auth header."""
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if content_type:
        req.add_header("Content-Type", content_type)
    return req


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


def get_or_create_release(token, version, notes):
    """Get existing release or create a new one."""
    # Check if release already exists for this tag
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/releases/tags/{version}"
    req = _api_request(url, token)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            release = json.loads(resp.read())
        print(f"  Existing release found: {version} (id={release['id']})")
        return release
    except urllib.error.HTTPError:
        pass

    # Create new release
    print(f"  Creating release {version}...")
    create_url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/releases"
    body = json.dumps({
        "tag_name": version,
        "name": f"LingPet {version}",
        "body": notes or f"Release {version}",
    }).encode()

    req = _api_request(create_url, token, method="POST", data=body, content_type="application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            release = json.loads(resp.read())
        print(f"  Release created: {version} (id={release['id']})")
        return release
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"[Error] Failed to create release: {e.code}\n{err}")
        sys.exit(1)


def delete_existing_asset(token, release_id, filename):
    """Delete existing asset with the same name if present."""
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/releases/{release_id}/assets"
    req = _api_request(url, token)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            assets = json.loads(resp.read())
        for asset in assets:
            if asset.get("name") == filename:
                del_url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/releases/assets/{asset['id']}"
                del_req = _api_request(del_url, token, method="DELETE")
                urllib.request.urlopen(del_req, timeout=10)
                print(f"  Old asset deleted: {filename}")
                break
    except Exception:
        pass


def upload_asset(token, version, zip_path):
    """Upload zip to the GitHub release using gh CLI."""
    filename = os.path.basename(zip_path)
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"  Uploading {filename} ({size_mb:.1f} MB) via gh CLI...")

    ret = os.system(f'gh release upload {version} "{zip_path}" --repo {OWNER}/{REPO} --clobber')
    if ret != 0:
        print("[Error] Upload failed. Make sure 'gh auth login' has been run.")
        sys.exit(1)
    print(f"  Asset uploaded: {filename}")


def main():
    parser = argparse.ArgumentParser(description="Upload LingPet release to GitHub")
    parser.add_argument("version", help="Version tag, e.g. v0.7.0")
    parser.add_argument("notes", nargs="?", default="", help="Release notes")
    parser.add_argument("--skip-build", action="store_true", help="Skip build, zip from dist/")
    parser.add_argument("--zip", help="Upload a pre-built zip file directly")
    args = parser.parse_args()

    token = load_token()

    if args.zip:
        zip_path = args.zip
        if not os.path.isfile(zip_path):
            print(f"[Error] File not found: {zip_path}")
            sys.exit(1)
        name = os.path.basename(zip_path)
        if not name.startswith("LingPet") or not name.endswith(".zip"):
            print(f"[Error] Zip must start with 'LingPet' and end with '.zip', got: {name}")
            sys.exit(1)
        print(f"[1/2] Uploading: {zip_path}")
    else:
        if not args.skip_build:
            run_build()

        if not os.path.isdir(DIST_DIR):
            print(f"[Error] {DIST_DIR} not found. Run build first or use --zip.")
            sys.exit(1)

        zip_path = create_zip(args.version)

    release = get_or_create_release(token, args.version, args.notes)
    upload_asset(token, args.version, zip_path)

    print(f"\nDone! Release: https://github.com/{OWNER}/{REPO}/releases/tag/{args.version}")


if __name__ == "__main__":
    main()
