"""Build a local STORM.app using Apple's native tools (run on the Mac)."""
import argparse
import os
from pathlib import Path
import platform
import plistlib
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit


def build_app(project_root, app_path):
    project_root = project_root.resolve()
    app_path = app_path.expanduser().absolute()
    if app_path.exists():
        raise FileExistsError(f"{app_path} 已存在，請先在 Finder 移走舊版本後重試。")
    app_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".storm-build-", dir=app_path.parent) as folder:
        staged = Path(folder) / "STORM.app"
        resources = staged / "Contents/Resources"
        executable = staged / "Contents/MacOS/STORM"
        resources.mkdir(parents=True)
        executable.parent.mkdir(parents=True)
        subprocess.run([
            "/usr/bin/xcrun", "swiftc", "-O", "-parse-as-library", "-swift-version", "5",
            "-target", f"{platform.machine()}-apple-macosx12.0", "-framework", "AppKit",
            str(project_root / "tools/macos/STORM.swift"), "-o", str(executable),
        ], check=True)
        iconset = Path(folder) / "STORM.iconset"
        subprocess.run([str(executable), "--write-iconset", str(iconset)], check=True)
        subprocess.run(["/usr/bin/iconutil", "-c", "icns", str(iconset),
                        "-o", str(resources / "STORM.icns")], check=True)
        (resources / "project-root.txt").write_text(str(project_root), encoding="utf-8")
        info = {
            "CFBundleName": "STORM", "CFBundleDisplayName": "STORM",
            "CFBundleIdentifier": "io.github.maxthehaters.storm.local",
            "CFBundleExecutable": "STORM", "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "1.0", "CFBundleVersion": "1",
            "CFBundleIconFile": "STORM.icns", "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
        }
        with (staged / "Contents/Info.plist").open("wb") as file:
            plistlib.dump(info, file)
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(staged)], check=True)
        staged.rename(app_path)
    return app_path


def add_to_dock(app_path):
    result = subprocess.run(["/usr/bin/defaults", "export", "com.apple.dock", "-"],
                            capture_output=True, check=True)
    preferences = plistlib.loads(result.stdout)
    existing = preferences.get("persistent-apps", [])
    for tile in existing:
        value = tile.get("tile-data", {}).get("file-data", {}).get("_CFURLString", "")
        if Path(unquote(urlsplit(value).path)).resolve() == app_path.resolve():
            return False
    backup = Path.home() / "Library/Application Support/STORM/dock-apps-before.plist"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        backup.write_bytes(plistlib.dumps(existing))
    tile = {"tile-type": "file-tile", "tile-data": {
        "file-data": {"_CFURLString": app_path.as_uri() + "/", "_CFURLStringType": 15},
        "file-label": "STORM", "file-type": 41,
    }}
    xml = plistlib.dumps(tile).decode("utf-8")
    xml = xml[xml.index("<dict>"):xml.rindex("</dict>") + len("</dict>")]
    subprocess.run(["/usr/bin/defaults", "write", "com.apple.dock", "persistent-apps", "-array-add", xml], check=True)
    subprocess.run(["/usr/bin/killall", "Dock"], check=False, capture_output=True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--app-path", type=Path, default=Path.home() / "Applications/STORM.app")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--add-to-dock", action="store_true")
    args = parser.parse_args()
    if sys.platform != "darwin" or sys.version_info < (3, 10):
        parser.error("請在 Mac 上使用 Python 3.10 以上版本執行。")
    root = args.project_root.resolve()
    if not (root / "frontend/demo_light/storm.py").is_file():
        parser.error("指定的位置不是 STORM 專案。")
    if args.app_path.expanduser().exists():
        parser.error("STORM.app 已存在，請先在 Finder 移走舊版本後重試。")
    python = root / ".venv/bin/python"
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True)
    if not args.skip_install:
        subprocess.run([str(python), "-m", "pip", "install", "-c",
                        str(root / "tools/macos/constraints.txt"), "-e", str(root), "-r",
                        str(root / "frontend/demo_light/requirements.txt"), "pyarrow<21"], check=True)
    app = build_app(root, args.app_path)
    if args.add_to_dock:
        add_to_dock(app)
    print(f"Installed: {app}")


if __name__ == "__main__":
    main()
