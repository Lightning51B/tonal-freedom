#!/bin/bash
# Host preparation only. Never reads or writes a connected device.
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.cargo/bin:$PATH"
[ "$(uname -s)" = Darwin ] && [ "$(id -u)" != 0 ] || {
    echo 'Run on macOS without sudo.' >&2; exit 1;
}
command -v brew >/dev/null || { echo 'Install Homebrew first; see MACOS.md.' >&2; exit 1; }
# Avoid upstream make failures when the selected Xcode path contains spaces.
# This affects this process only; it does not change xcode-select globally.
if [ -d /Library/Developer/CommandLineTools ]; then
    export DEVELOPER_DIR=/Library/Developer/CommandLineTools
fi
xcrun --find clang++ >/dev/null
for formula in python@3.13 libusb openssl keystone; do
    brew list --versions "$formula" >/dev/null || brew install "$formula"
done
command -v adb >/dev/null || brew install --cask android-platform-tools
if [ ! -x .tools/bin/magiskboot ]; then
    bash setup-macos.sh
fi
bash patcher.sh --prepare
MTK="$SCRIPT_DIR/.tools/mtkclient"
REVISION=118a000a83ea31c4f427fe5225abfe964546e05e
if [ ! -d "$MTK" ]; then
    git clone --recursive https://github.com/bkerler/mtkclient.git "$MTK"
    git -C "$MTK" checkout --detach "$REVISION"
fi
[ "$(git -C "$MTK" rev-parse HEAD)" = "$REVISION" ] || {
    echo "Unexpected mtkclient revision in $MTK; move it aside and rerun." >&2; exit 1;
}
git -C "$MTK" submodule update --init --recursive
PYTHON="$(brew --prefix python@3.13)/bin/python3.13"
[ -x "$MTK/.venv/bin/python" ] || "$PYTHON" -m venv "$MTK/.venv"
# Upstream also lists OpenStack's unrelated "keystone", which collides with
# the assembler's Python namespace. mtkclient needs keystone-engine instead.
"$PYTHON" - "$MTK" <<'PYTHON'
import sys
from pathlib import Path
root = Path(sys.argv[1])
lines = (root / 'requirements.txt').read_text().splitlines()
(root.parent / 'mtk-requirements.txt').write_text(
    '\n'.join(line for line in lines if line.strip() not in {'keystone', 'mfusepy'}) + '\n')
PYTHON
# Filesystem mounting is not used; omitting mfusepy avoids loading old Intel
# macFUSE libraries on Apple Silicon. Upstream handles its absence explicitly.
"$MTK/.venv/bin/python" -m pip uninstall -y mfusepy >/dev/null 2>&1 || true
"$MTK/.venv/bin/python" -m pip install --no-binary capstone -r "$SCRIPT_DIR/.tools/mtk-requirements.txt"
# Use Homebrew's native assembler library; PyPI's wheel may omit it.
export DYLD_LIBRARY_PATH="$(brew --prefix keystone)/lib:$(brew --prefix libusb)/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
cd "$MTK"
"$MTK/.venv/bin/python" - <<'PY'
import usb.backend.libusb1
from PySide6.QtWidgets import QApplication
import mtk_gui
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
assert Ks(KS_ARCH_ARM, KS_MODE_ARM).asm("nop")[1] == 1
assert usb.backend.libusb1.get_backend() is not None, 'libusb backend unavailable'
app = QApplication(['tonal-preflight', '-platform', 'offscreen'])
print('mtkclient imports, Qt initialization and libusb backend passed.')
PY
cd "$SCRIPT_DIR"
mkdir -p backups
printf '\nMac preparation complete. Open Tonal Tools.command when ready.\n'
printf 'Keep original partition backups separately and back up ~/tonal_keys securely.\n'
