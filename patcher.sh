#!/bin/bash

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Utility: Patches a given boot.bin or boot.img with Magisk
# Expectation: In your current working directory, you have the following files: 
# 1. boot.bin or boot.img - an unencryped raw binary of your android's environment's boot partition
# 2. Magisk-v27.0.apk (or other magisk APK)

# On macOS use: bash patcher-macos.sh
# Runs without sudo on macOS and Linux.

# ==========================================
# Configuration & File Checks
# ==========================================
set -euo pipefail

if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != --prepare ]; }; then
    echo "Usage: bash patcher.sh [--prepare]" >&2
    exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
HOST_OS=$(uname -s)
case "$HOST_OS" in
    Darwin|Linux) ;;
    *) echo "Unsupported host OS: $HOST_OS" >&2; exit 1 ;;
esac
if [ "$(id -u)" = 0 ]; then
    echo "Run without sudo; patching does not require root." >&2
    exit 1
fi
for cmd in adb curl unzip python3; do
    command -v "$cmd" >/dev/null || { echo "Missing $cmd; see MACOS.md." >&2; exit 1; }
done

ORIG_DIR="$PWD"
MAGISK_APK="Magisk-v27.0.apk"
TEXT_LAUNCHER_APK="textlauncher.apk"
FINAL_OUT="boot.patched.img"
SDK_VER=23
CPU_ABI="arm64-v8a"

# Define a permanent, self-contained key vault folder inside the user's home directory
VAULT_DIR=${TONAL_KEY_DIR:-"$HOME/tonal_keys"}
mkdir -p "$VAULT_DIR"
VAULT_DIR=$(cd "$VAULT_DIR" && pwd)
ADB_PUB_KEY="$VAULT_DIR/adbkey.pub"
ADB_PRIV_KEY="$VAULT_DIR/adbkey"

if [ "${1:-}" != --prepare ]; then
    # Auto-detect whether the boot image is named .img or .bin
    if [ -f "boot.img" ]; then
        BOOT_IMG="boot.img"
    elif [ -f "boot.bin" ]; then
        BOOT_IMG="boot.bin"
    else
        echo "[!] Error: Neither boot.img nor boot.bin found in current directory."
        exit 1
    fi

    if [ -e "$FINAL_OUT" ]; then
        echo "Move the existing $FINAL_OUT before patching again." >&2
        exit 1
    fi
fi

if [ "$HOST_OS" = Darwin ]; then
    MAGISKBOOT=${MAGISKBOOT:-"$SCRIPT_DIR/.tools/bin/magiskboot"}
    if [ ! -x "$MAGISKBOOT" ]; then
        echo "Build native magiskboot first: bash setup-macos.sh" >&2
        exit 1
    fi
    # Resolve before switching to the temporary workspace.
    MAGISKBOOT=$(cd "$(dirname "$MAGISKBOOT")" && pwd)/$(basename "$MAGISKBOOT")
else
    case "$(uname -m)" in
        aarch64|arm64) HOST_ABI=arm64-v8a ;;
        x86_64) HOST_ABI=x86_64 ;;
        *) echo "Unsupported Linux host architecture" >&2; exit 1 ;;
    esac
fi

# Download atomically so interrupted requests cannot become cached APKs.
download_apk() {
    local url=$1 destination=$2
    if [ ! -s "$destination" ]; then
        curl --fail --location --silent --show-error "$url" -o "$destination.download" || {
            rm -f "$destination.download"
            return 1
        }
        mv "$destination.download" "$destination"
    fi
    unzip -tq "$destination" >/dev/null
}
download_apk https://github.com/topjohnwu/Magisk/releases/download/v27.0/Magisk-v27.0.apk "$MAGISK_APK"
download_apk https://github.com/ademar111190/TextLauncher/releases/download/1.4.1/app-release.apk "$TEXT_LAUNCHER_APK"

# ==========================================
# Phase 1: Golden Key Vault Generation
# ==========================================
echo "[*] Ensuring permanent ADB golden key exists..."
chmod 0700 "$VAULT_DIR"
if [ ! -f "$ADB_PRIV_KEY" ]; then
    if [ -e "$ADB_PUB_KEY" ]; then
        echo "Public key exists without its private key; restore the pair." >&2
        exit 1
    fi
    (umask 077; adb keygen "$ADB_PRIV_KEY")
elif [ ! -s "$ADB_PUB_KEY" ]; then
    adb pubkey "$ADB_PRIV_KEY" > "$ADB_PUB_KEY"
fi
chmod 0600 "$ADB_PRIV_KEY"
chmod 0644 "$ADB_PUB_KEY"

# Preparation is host-only: no boot image or connected device required.
if [ "${1:-}" = --prepare ]; then
    echo "APKs and dedicated ADB key ready; no device commands issued."
    exit 0
fi

# ==========================================
# Phase 2: Set Up Temporary Workspace
# ==========================================
TEMP_DIR=$(mktemp -d)
echo "[*] Created temporary workspace at $TEMP_DIR"

# Ensure cleanup happens even if the script exits abruptly
trap 'echo "[*] Cleaning up workspace..."; cd "$ORIG_DIR"; rm -rf "$TEMP_DIR"' EXIT

cd "$TEMP_DIR" || exit 1

# ==========================================
# Phase 3: Extract Magisk Tools
# ==========================================
echo "[*] Extracting Magisk tools from $MAGISK_APK..."
unzip -q -o -j "$ORIG_DIR/$MAGISK_APK" "assets/boot_patch.sh" -d .
unzip -q -o -j "$ORIG_DIR/$MAGISK_APK" "assets/util_functions.sh" -d .
unzip -q -o -j "$ORIG_DIR/$MAGISK_APK" "assets/stub.apk" -d .
if [ "$HOST_OS" = Darwin ]; then
    cp "$MAGISKBOOT" magiskboot
else
    unzip -q -o -j "$ORIG_DIR/$MAGISK_APK" "lib/$HOST_ABI/libmagiskboot.so" -d .
    mv libmagiskboot.so magiskboot
fi
unzip -q -o -j "$ORIG_DIR/$MAGISK_APK" "lib/arm64-v8a/libmagiskinit.so" -d .
unzip -q -o -j "$ORIG_DIR/$MAGISK_APK" "lib/arm64-v8a/libmagisk64.so" -d .
unzip -q -o -j "$ORIG_DIR/$MAGISK_APK" "lib/armeabi-v7a/libmagisk32.so" -d .

echo "[*] Renaming and setting permissions for binaries..."
mv -f libmagiskinit.so magiskinit
mv -f libmagisk64.so magisk64
mv -f libmagisk32.so magisk32
chmod +x boot_patch.sh magiskboot magiskinit magisk64 magisk32

cp -f "$ORIG_DIR/$MAGISK_APK" magisk.apk

# Portable replacement for GNU sed -i; the upstream script expects an Android UI FD.
python3 - <<'PYTHON'
from pathlib import Path
p = Path("util_functions.sh")
text = p.read_text().replace('>&${O33}', '>&1').replace('>& $O33', '>&1')
# Magisk's grep_prop uses dos2unix, which macOS does not ship.
p.write_text(text.replace('| dos2unix |', r"| tr -d '\r' |"))
PYTHON

# ==========================================
# Phase 4: Create getprop Stub (necessary for magisk tools used outside of a phone)
# ==========================================
echo "[*] Generating dynamic getprop stub..."
cat << EOF > getprop
#!/bin/bash
case "\$1" in
    ro.build.version.sdk) echo "$SDK_VER" ;;
    ro.product.cpu.abi) echo "$CPU_ABI" ;;
    *) echo "" ;;
esac
EOF
chmod +x getprop

# ==========================================
# Phase 5: Execute Magisk Patch
# ==========================================
echo "[*] Copying boot image to temp workspace..."
cp "$ORIG_DIR/$BOOT_IMG" .
mkdir original_check
(cd original_check && ../magiskboot unpack "../$BOOT_IMG" >/dev/null)

echo "[*] Patching $BOOT_IMG with Magisk..."
export KEEPVERITY=true
export KEEPFORCEENCRYPT=true
export RECOVERYMODE=false
export LEGACYSAR=false
export PATCHVBMETAFLAG=false
export PATH="$PWD:$PATH"

bash boot_patch.sh "$BOOT_IMG"

# ==========================================
# Phase 6: Inject Payload (ADB, Launcher, Bypass)
# ==========================================
if [ ! -f "new-boot.img" ]; then
    echo "[!] Error: new-boot.img was not generated. The Magisk patch failed."
    exit 1
fi

echo "[*] Unpacking patched image to inject payload..."
./magiskboot unpack new-boot.img >/dev/null

echo "[*] Staging ramdisk additions..."
mkdir ramdisk_root && cd ramdisk_root
# Stage only new files. magiskboot preserves existing archive ownership/modes;
# extracting and rebuilding with the Mac user's UID would corrupt them.

echo "[*] Creating Magisk overlay.d structure..."
mkdir -p overlay.d/sbin

echo "[*] Injecting Permanent Golden ADB Public Key into Native Root..."
# Android 6 adbd natively looks at /adb_keys on boot.
cp "$ADB_PUB_KEY" overlay.d/adb_keys
chmod 0640 overlay.d/adb_keys

echo "[*] Staging Launcher Payload into /sbin..."
cp "$ORIG_DIR/$TEXT_LAUNCHER_APK" overlay.d/sbin/textlauncher.apk
chmod 0644 overlay.d/sbin/textlauncher.apk

echo "[*] Generating Native Init Service Script..."
cat << 'EOF' > overlay.d/sbin/bypass_kiosk.sh
#!/system/bin/sh

# 0. EXPORT ENVIRONMENT (CRITICAL FIX)
# Native init scripts have no PATH. We must define the environment so am/pm/settings commands work.
export PATH=/sbin:/system/sbin:/system/bin:/system/xbin
export ANDROID_ROOT=/system
export ANDROID_DATA=/data

# SELINUX OVERRIDE (CRITICAL FIX)
# Force the runtime state if kernel allows it
setenforce 0
# Inject broad Magisk policies live just in case
/sbin/magiskpolicy --live "permissive *"

# 1. Wait for Android Framework (ActivityManager) to wake up (with safety timeout)
ATTEMPTS=0
MAX_ATTEMPTS=600
until dumpsys activity >/dev/null 2>&1; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
        echo "[!] Warning: Framework did not wake up in time. Continuing boot anyway..."
        break
    fi
    sleep 2
done

# 2. Push ADB settings and force-restart adbd just in case
mkdir -p /data/misc/adb
if ! grep -q -F "$(cat /adb_keys)" /data/misc/adb/adb_keys 2>/dev/null; then
    cat /adb_keys >> /data/misc/adb/adb_keys
fi
chmod 0640 /data/misc/adb/adb_keys
chown system:shell /data/misc/adb/adb_keys
settings put secure development_settings_enabled 1
settings put secure adb_enabled 1
# Reapply authenticated network ADB every boot, before restarting the daemon.
# Read-only properties may already exist, so use Magisk's resetprop applet.
setprop ctl.stop adbd
setprop service.adb.tcp.port -1
setprop persist.adb.tcp.port -1
if [ ! -x /sbin/resetprop ] && [ -x /sbin/magisk ]; then
    ln -s /sbin/magisk /sbin/resetprop
fi
/sbin/resetprop ro.adb.secure 1
/sbin/resetprop ro.secure 1
setprop service.adb.root 0
if [ "$(getprop ro.adb.secure)" = 1 ] && [ "$(getprop ro.secure)" = 1 ]; then
    setprop persist.adb.tcp.port 5555
    setprop service.adb.tcp.port 5555
else
    echo "ADB authentication could not be enabled; leaving network ADB disabled."
fi
setprop ctl.start adbd

# 3. Install TextLauncher ONLY if it is missing (using fast, safe pm path check)
if [ -z "$(pm path ademar.textlauncher 2>/dev/null)" ]; then
    pm install -r /sbin/textlauncher.apk
fi

# 4. Force-stop and disable the Tonal kiosk apps
am force-stop com.tonal.tonallauncher
am force-stop com.tonal.apps.machineclient2
pm disable com.tonal.tonallauncher

# 5. Force open standard Android Settings and Developer Options
am start -a android.settings.SETTINGS
am start -a com.android.settings.APPLICATION_DEVELOPMENT_SETTINGS

# 6. Force the notification panel to drop down (using raw binder call)
service call statusbar 1

# 7. Wake up the screen and launch the new home environment
am start -a android.intent.action.MAIN -c android.intent.category.HOME
EOF

chmod 0755 overlay.d/sbin/bypass_kiosk.sh

echo "[*] Injecting overlay.d custom.rc..."
cat << EOF > overlay.d/custom.rc
on early-init
    # SeLinux Permissive via sysfs
    write /sys/fs/selinux/enforce 0

    # Never expose a persisted TCP listener before this boot's auth checks.
    setprop service.adb.tcp.port -1
    setprop persist.adb.tcp.port -1
    setprop ro.debuggable 1
    setprop ro.secure 1
    setprop ro.adb.secure 1
    setprop persist.sys.usb.config adb
    setprop sys.usb.config adb
    setprop service.adb.root 0

# Automatically destroy all Device Administrator policies before Android boots
on post-fs-data
    rm /data/system/device_policies.xml
    rm /data/system/device_owner.xml
    rm /data/system/device_owner_2.xml
    rm /data/system/profile_owner.xml

# Start our script natively via the Android init system
on boot
    start bypass_kiosk

service bypass_kiosk /system/bin/sh /sbin/bypass_kiosk.sh
    class late_start
    user root
    group root
    seclabel u:r:su:s0
    oneshot
EOF

echo "[*] Repacking ramdisk..."
cd ..
./magiskboot cpio ramdisk.cpio \
    "mkdir 0750 overlay.d" \
    "mkdir 0750 overlay.d/sbin" \
    "add 0640 overlay.d/adb_keys ramdisk_root/overlay.d/adb_keys" \
    "add 0644 overlay.d/sbin/textlauncher.apk ramdisk_root/overlay.d/sbin/textlauncher.apk" \
    "add 0755 overlay.d/sbin/bypass_kiosk.sh ramdisk_root/overlay.d/sbin/bypass_kiosk.sh" \
    "add 0644 overlay.d/custom.rc ramdisk_root/overlay.d/custom.rc"

echo "[*] Repacking final boot image..."
python3 "$SCRIPT_DIR/scripts/verify_ramdisk.py" --normalize-xz ramdisk.cpio "$PWD/magiskboot"
./magiskboot repack new-boot.img "$FINAL_OUT" >/dev/null

# ==========================================
# Phase 7: Automated Verification Checks
# ==========================================
echo "[*] Running post-build integrity and safety checks..."

# magiskboot verify checks AVB 1.0 signatures, not structural integrity.
# Re-unpack instead; this does not prove the image will boot on the device.
mkdir verify_perms && cd verify_perms
../magiskboot unpack "../$FINAL_OUT" >/dev/null 2>&1
python3 "$SCRIPT_DIR/scripts/verify_ramdisk.py" ramdisk.cpio "$ADB_PUB_KEY" ../original_check/ramdisk.cpio \
    "../$FINAL_OUT" "../$BOOT_IMG" ../patch-validation.json
cd ..

# ==========================================
# Phase 8: Final Outputs & Helper Generation
# ==========================================
if [ -f "$FINAL_OUT" ]; then
    mv patch-validation.json "$ORIG_DIR/patch-validation.json"
    mv "$FINAL_OUT" "$ORIG_DIR/$FINAL_OUT"

    {
        printf '#!/bin/bash\nset -e\nexport ADB_VENDOR_KEYS=%q\n' "$ADB_PRIV_KEY"
        cat << 'EOF'
echo "[*] Restarting ADB with the Tonal key."
adb kill-server
adb start-server
adb devices -l
EOF
    } > "$ORIG_DIR/start.adb.sh"
    chmod +x "$ORIG_DIR/start.adb.sh"


    echo "=========================================="
    echo "[*] SUCCESS! Image built; unpack and ownership checks passed:"
    echo "[*] Output Image: $ORIG_DIR/$FINAL_OUT"
    echo "[*] ADB Helper Script: $ORIG_DIR/start.adb.sh"
    echo "=========================================="
else
    echo "[!] Error: $FINAL_OUT was not generated."
fi
