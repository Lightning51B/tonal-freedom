#!/bin/bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)
APP="$ROOT/dist/Tonal Freedom.app"
RESOURCES="$APP/Contents/Resources"
PYTHON="$ROOT/.tools/mtkclient/.venv/bin/python"
"$PYTHON" -m pip install 'pyinstaller==6.22.0'
# onedir freezes Python, imports, Qt frameworks and all native libraries.
"$PYTHON" -m PyInstaller --noconfirm --clean --onedir --name tonal-runtime \
    --distpath "$ROOT/.tools/frozen" --workpath "$ROOT/.tools/freeze-build" \
    --specpath "$ROOT/.tools" --paths "$ROOT/.tools/mtkclient" \
    --add-data "$ROOT/.tools/mtkclient/mtkclient:mtkclient" --collect-submodules mtkclient \
    --collect-all capstone --collect-all keystone --collect-all unicorn \
    --add-binary "$(brew --prefix libusb)/lib/libusb-1.0.0.dylib:." \
    --add-binary "$(brew --prefix keystone)/lib/libkeystone.dylib:keystone" \
    --exclude-module mfusepy "$ROOT/macos/runtime.py"
# Rebuild only generated output; stale files must not leak into the app.
if [ -d "$APP" ]; then rm -rf "$APP"; fi
mkdir -p "$APP/Contents/MacOS" "$RESOURCES/.tools/bin" "$RESOURCES/scripts" "$RESOURCES/bin"
xcrun swiftc -swift-version 5 -O -framework Cocoa "$ROOT/macos/TonalFreedom.swift" -o "$APP/Contents/MacOS/TonalFreedom"
cp "$ROOT/macos/task.sh" "$ROOT/patcher.sh" "$ROOT/patcher-macos.sh" "$ROOT/MACOS.md" "$ROOT/GUIDE.md" "$ROOT/Magisk-v27.0.apk" "$ROOT/textlauncher.apk" "$RESOURCES/"
cp "$ROOT/scripts/verify_ramdisk.py" "$RESOURCES/scripts/"
cp "$ROOT/.tools/bin/magiskboot" "$RESOURCES/.tools/bin/"
cp -R "$ROOT/.tools/frozen/tonal-runtime" "$RESOURCES/runtime"
cp "$(command -v adb)" "$RESOURCES/bin/adb"
cp "$ROOT/macos/python3" "$RESOURCES/bin/python3"
chmod +x "$RESOURCES/bin/"*
mkdir -p "$RESOURCES/Licenses"
cp "$ROOT/LICENSE" "$RESOURCES/Licenses/Tonal-Freedom.txt"
cp "$ROOT/.tools/mtkclient/LICENSE" "$RESOURCES/Licenses/mtkclient.txt"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>TonalFreedom</string>
<key>CFBundleIdentifier</key><string>local.tonalfreedom.mac</string>
<key>CFBundleName</key><string>Tonal Freedom</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>1.2</string>
<key>LSMinimumSystemVersion</key><string>13.0</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
codesign --force --deep --sign - "$APP"
printf 'Built %s\n' "$APP"
