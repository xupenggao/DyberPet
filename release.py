"""
One-click release script for DyberPet / LingPet.

Builds the project with Nuitka, zips the output, creates a Gitee Release,
and uploads the zip as an asset.

Usage:
    python release.py v0.7.0 "Bug fixes and new companion feature"
    python release.py v0.7.0 --skip-build  # skip build, just upload existing zip
"""

import os
import sys
import json
import shutil
import zipfile
import argparse
import urllib.request
import urllib.parse


GITEE_API = "https://gitee.com/api/v5"
OWNER = "Simon-25"
REPO = "dyberpet"
DIST_DIR = "dist/LingPet"


def load_token():
    """Load Gitee token from settings file or environment."""
    token = os.environ.get("GITEE_TOKEN", "")
    if token:
        return token

    settings_path = os.path.join("data", "settings.json")
    if os.path.isfile(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        token = data.get("gitee_token", "")

    if not token:
        print("[Error] Gitee token not found. Set GITEE_TOKEN env var or add 'gitee_token' to data/settings.json")
        sys.exit(1)
    return token


def run_build():
    """Run build_nuitka.bat."""
    print("[1/3] Building with Nuitka...")
    ret = os.system("build_nuitka.bat")
    if ret != 0:
        print("[Error] Build failed!")
        sys.exit(1)
    print("[1/3] Build complete.")


def create_zip(version):
    """Zip the dist directory."""
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


def create_release(token, version, notes, zip_path):
    """Create a Gitee Release and upload the zip."""
    print(f"[3/3] Creating Gitee Release {version}...")

    # Create release
    url = f"{GITEE_API}/repos/{OWNER}/{REPO}/releases"
    data = urllib.parse.urlencode({
        "access_token": token,
        "tag_name": version,
        "name": f"LingPet {version}",
        "body": notes or f"Release {version}",
        "target_commitish": "dev",
    }).encode()

    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            release = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[Error] Failed to create release: {e.code}\n{body}")
        sys.exit(1)

    release_id = release["id"]
    print(f"  Release created: id={release_id}")

    # Upload asset
    upload_url = f"{GITEE_API}/repos/{OWNER}/{REPO}/releases/{release_id}/attach_files"
    filename = os.path.basename(zip_path)

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    with open(zip_path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        upload_url + f"?access_token={token}",
        data=body,
        method="POST",
    )
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            asset = json.loads(resp.read())
        print(f"  Asset uploaded: {asset.get('name', filename)}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"[Error] Failed to upload asset: {e.code}\n{err_body}")
        sys.exit(1)

    print(f"[3/3] Release {version} published successfully!")
    print(f"  URL: https://gitee.com/{OWNER}/{REPO}/releases/{version}")


def main():
    parser = argparse.ArgumentParser(description="Build and release LingPet")
    parser.add_argument("version", help="Version tag, e.g. v0.7.0")
    parser.add_argument("notes", nargs="?", default="", help="Release notes")
    parser.add_argument("--skip-build", action="store_true", help="Skip build step")
    args = parser.parse_args()

    token = load_token()

    if not args.skip_build:
        run_build()

    if not os.path.isdir(DIST_DIR):
        print(f"[Error] {DIST_DIR} not found. Run build first.")
        sys.exit(1)

    zip_path = create_zip(args.version)
    create_release(token, args.version, args.notes, zip_path)


if __name__ == "__main__":
    main()
