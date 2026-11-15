#!/bin/bash
set -euo pipefail
RESOURCES=$(cd "$(dirname "$0")" && pwd)
export PATH="$RESOURCES/bin:/usr/bin:/bin:/usr/sbin:/sbin"
unset PYTHONHOME PYTHONPATH DYLD_LIBRARY_PATH DYLD_FRAMEWORK_PATH
export PYTHONDONTWRITEBYTECODE=1
export TONAL_KEY_DIR="$HOME/tonal_keys"
case "${1:-}" in
    check)
        test -x "$RESOURCES/.tools/bin/magiskboot"
        unzip -tq "$RESOURCES/Magisk-v27.0.apk"
        unzip -tq "$RESOURCES/textlauncher.apk"
        # Existing keys are retained; first launch on a new Mac creates its key.
        bash "$RESOURCES/task.sh" prepare
        adb version
        "$RESOURCES/runtime/tonal-runtime" check
        ;;
    prepare)
        cd "$RESOURCES"
        exec bash "$RESOURCES/patcher.sh" --prepare
        ;;
    wireless) shift; exec "$RESOURCES/runtime/tonal-runtime" wireless "$@" ;;
    device) shift; exec "$RESOURCES/runtime/tonal-runtime" device "$@" ;;
    mtk) exec "$RESOURCES/runtime/tonal-runtime" mtk ;;
    patch)
        cd "$2"
        exec bash "$RESOURCES/patcher.sh"
        ;;
    connect)
        export ADB_VENDOR_KEYS="$HOME/tonal_keys/adbkey"
        test -s "$ADB_VENDOR_KEYS"
        adb kill-server
        adb start-server
        adb devices -l
        ;;
    devices) exec adb devices -l ;;
    install) exec adb -s "$2" install -r "$RESOURCES/Magisk-v27.0.apk" ;;
    *) echo 'Unknown action' >&2; exit 1 ;;
esac
