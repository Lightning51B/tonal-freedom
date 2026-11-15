#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
echo 'Tonal tools — choose an action:'
echo '1. Prepare this Mac (internet required for initial setup)'
echo '2. Open mtkclient for backup / manual flashing'
echo '3. Patch boot.bin or boot.img in this folder'
echo '4. Start ADB with the Tonal key (restarts the ADB server)'
read -r -p 'Selection: ' choice
case "$choice" in
    1) bash prepare-macos.sh ;;
    2)
        MTK="$PWD/.tools/mtkclient"
        [ -x "$MTK/.venv/bin/python" ] || { echo 'Run preparation first.'; exit 1; }
        export DYLD_LIBRARY_PATH="$(brew --prefix keystone)/lib:$(brew --prefix libusb)/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
        cd "$MTK"
        .venv/bin/python mtk_gui.py
        ;;
    3) bash patcher.sh ;;
    4) [ -f start.adb.sh ] || { echo 'Patch your boot image first.'; exit 1; }
       bash start.adb.sh ;;
    *) echo 'No action selected.' ;;
esac
read -r -p 'Press Return to close.' _
