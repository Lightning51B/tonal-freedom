# Running natively from a Mac

Backup, patching, flashing, and ADB all run directly on macOS. Apple Silicon
and Intel Macs use a native Mach-O `magiskboot` executable built from the
[official Magisk v31.1 sources](https://github.com/topjohnwu/Magisk/tree/v31.1).
No Docker, Linux VM, or emulation is required. The Android payload and patch
script remain **Magisk v27.0**, as in the original project; v31.1 supplies only
the host boot-image utility. This project still targets Tonal 1, not Tonal 2.

The patcher converts every XZ ramdisk payload to LZMA2-only with CRC32 before
the final repack. Magisk 31's host tool automatically applies BCJ filters to ELF
files; Magisk 27's embedded decoder cannot read those filters. The failed device
image reproduced this error for the original Android init and both Magisk
binaries. The verifier checks this encoding and the exact restored stock init,
including its permissions. A hash-bound `patch-validation.json` accompanies each
new image; the app refuses older images without this validation.

## Mac app

Open **~/Applications/Tonal Freedom.app**. It provides eight numbered steps with
readable logs and transfer progress: check the Mac, back up, patch the backed-up
boot image, flash boot, connect ADB, install Magisk, install/open Text Launcher,
and disable OTA updates. Backup and flashing run
inside the app; no mtkclient GUI or terminal commands are required.

Choose a backup destination in step 2, connect USB and power cycle when prompted.
The app reads the complete eMMC user area (including every GPT partition, userdata,
and both GPT copies) plus any reported boot1/boot2 regions. It extracts `boot.bin`
automatically, checks file sizes/hashes and writes `backup.json` only after success.
RPMB is not included. A failed/cancelled backup is never marked complete. Keep a
second copy separately. The backup waits for your power cycle without a countdown; once bootloader USB
appears, handshake/initialization has a two-minute deadline. On macOS the app uses
the native CDC serial connection, retrying the initial handshake after the
preloader's READY banner. This handshake has been verified on the physical Tonal;
the complete backup/flash workflow still requires device verification.
Session logs are saved in `~/Library/Logs/Tonal Freedom`.

Full backups use streaming legacy eMMC reads with per-packet checksum validation.
The app shows measured throughput and an estimated remaining time; actual speed
depends on the device and transport. Each saved 16 MiB chunk is flushed to disk
and recorded in `resume.json`. After cancellation or a disconnect, choose step 2
again to resume, or select an incomplete backup folder. The app verifies device
identity, layout, sizes, and every saved chunk before continuing. Old partial
backups without checkpoints cannot be resumed. The app prevents idle system sleep
during operations; keep USB and power connected.

Step 3 patches the saved boot automatically and records its relationship to the
verified backup. Step 4 rechecks all backup hashes, device identity, storage layout,
and the device's current boot before showing the final confirmation. It writes
only the boot partition, preserves any original trailing bytes, then reads it back
and compares the entire partition. No other partition is written. After verified
success, power cycle Tonal and use steps 5–6 for ADB and Magisk installation.
Flashing has no mid-write cancel action. Failure requires inspection; the app does
not silently retry writes or attempt an automatic restore. Backup and boot
write/read-back have been exercised on the device. The earlier patched image
bootlooped; restoring stock boot recovered normal operation. The compression fix
has offline validation; successful modified boot and wireless ADB still require
a physical Tonal test.

The app bundles the native patcher, verification script, **your local
Magisk-v27.0.apk**, and TextLauncher. Each patch uses a fresh folder under
`~/Library/Application Support/Tonal Freedom/Runs/`; the source image is copied
there and left unchanged. **Show output** opens the last successful run.
The preparation and ADB key are shared with the command-line workflow.

The app is standalone on Apple Silicon: Python, Qt, mtkclient (including loaders
and payloads), USB/assembler libraries, ADB, magiskboot and both APKs are bundled.
The installed app at `~/Applications/Tonal Freedom.app` is a real copy on the
internal drive. It needs neither DevSSD, this repository, Homebrew, Xcode nor
network access at runtime. macOS system utilities are used for shell/ZIP tasks.
It is locally ad-hoc signed, not notarized for distribution or tested on Intel.

Keys stay in `~/tonal_keys` and outputs/logs stay under your home folder, outside
the signed app. Existing keys are preserved; Check Mac creates a key if needed.
Back up that private key securely. No private keys are distributed in the app.

Developers can rebuild using `bash build-macos-app.sh` after preparation; only
building requires the repository, Homebrew and the Python development environment.
The build freezes the runtime with PyInstaller and copies the local APKs.
Replacing an APK in the repository does not change an already-built app.

Preparation and checks never flash a device. The boot write requires confirmation
in the app after the connected device and backup have been checked.
Physical Tonal compatibility remains unverified.

## Wireless access and later APK installation

New boot images enable authenticated network ADB on port 5555 at every boot.
The boot script first disables any previous listener, installs the dedicated
public key, enables `ro.adb.secure=1` and `ro.secure=1`, and starts network ADB only
if those properties match. ADB runs as the normal shell user, not root. The
Magisk service can still perform its boot tasks as root.

Keep USB attached for **step 5: Set up Wi-Fi ADB**. Connect the Tonal to your Wi-Fi
network in Android Settings and allow USB debugging on its screen. Step 5 can
use the USB transport already held by Android Studio without stopping that
server. It installs the bundled Magisk app if needed; complete Magisk's
additional setup/reboot, then retry step 5 and grant Shell superuser access.
The app installs an authenticated Wi-Fi startup service in
`/data/adb/service.d/tonal-wifi.sh`, preserves existing authorized keys, and adds
its own public key. This avoids relying on custom ramdisk files surviving
Magisk's root filesystem setup. No boot partition write is needed for this step.
It saves the address only after verifying the network device identity and
non-root, authenticated ADB. Then unplug USB and use **Reconnect Wi-Fi**. Repeat
after a Tonal power cycle before closing the cabinet.

For future installations, open the app and choose **Install APK**. It reconnects
to the saved Tonal, checks identity and authentication settings, and installs the
selected APK. **Install Magisk** uses the same wireless path. If DHCP changes the
address, enter its new IP using **Reconnect Wi-Fi**; no USB is needed to update it.

**Step 7: Install launcher** installs the bundled Text Launcher over Wi-Fi and
checks that it opens on the Tonal. It does not change the default home app.
**Step 8: Disable OTA updates** disables `com.innocomm.otaupdate` and
`com.tonal.apkupdater`, stops them, and saves a Magisk startup script to reapply
the block. It verifies both package states and the saved script. The separate
motor-controller firmware client is unchanged. **Allow OTA updates** removes
the startup script and restores the two updater packages to their default state.
Both steps are repeatable, show progress, and verify the saved Tonal's identity
before making changes. No boot flash or USB connection is required.
The app accepts private LAN IPv4 addresses and keeps its ADB server separate
from Android Studio on local port 5038 for network access; initial USB setup can
use Android Studio's existing port 5037 transport. Settings live in
`~/Library/Application Support/Tonal Freedom/wireless.json`; the private key
remains in `~/tonal_keys`. Keep the Mac and Tonal on a trusted local network;
legacy network ADB does not provide modern wireless-debugging TLS encryption.
Backup and boot flashing still use USB and require the initial physical access.

## Quick preparation (before connecting the Tonal)

From this folder run `bash prepare-macos.sh`, or double-click
**Tonal Tools.command** and choose **1**. Homebrew and Apple's command-line tools
must already be installed; Rust is needed only if native magiskboot needs building
(see the manual setup below).

Preparation installs missing Homebrew dependencies, reuses/builds native
magiskboot, downloads and validates both APK archives, creates/reuses the dedicated
ADB key, and installs a pinned mtkclient checkout in `.tools/mtkclient` with its
own Python environment. The setup excludes upstream's unrelated OpenStack
`keystone` package (the required assembler is `keystone-engine`) and optional
`mfusepy` filesystem mounting, uses Homebrew’s native assembler library, and uses installed
Apple command-line tools locally to avoid Xcode paths with spaces. It checks mtkclient imports, Qt initialization and the
libusb backend without connecting to a device or restarting ADB. Rerunning it
reuses the checkout and existing assets. Initial setup requires internet;
patching and the tool launcher use the locally prepared files afterward.

On the day:

1. Open **Tonal Tools.command**, choose **2**, and use mtkclient to back up all
   partitions. Keep the originals separately, including a second copy elsewhere.
2. Put a **copy** of the original `boot.bin` or `boot.img` in this repository
   folder, then choose **3** to create and check `boot.patched.img`.
3. In mtkclient, manually select the **boot partition only** and write that image
   after checking your original backups. Exit mtkclient and power cycle the Tonal.
4. Choose **4** to start ADB with the prepared key. Install Magisk using
   `adb install Magisk-v27.0.apk` (select a serial if multiple devices are attached).

Back up `~/tonal_keys` securely; it contains the private key needed for later
access. Do not share it. Preparation cannot verify physical USB detection,
firmware compatibility, boot success, or recovery without the actual Tonal.
The launcher does not automate flashing or install macFUSE/system extensions.

## 1. Install the Mac tools

Install Apple's command-line tools if needed:

```bash
xcode-select --install
```

With [Homebrew](https://brew.sh/) installed:

```bash
brew install python@3.13 libusb openssl
brew install --cask android-platform-tools
```

Install Rust using [rustup](https://rustup.rs/) if `rustup` is not already
available. Then, from this repository:

```bash
bash setup-macos.sh
```

This builds `.tools/bin/magiskboot` for your Mac's CPU. It downloads a pinned
Magisk source revision and Rust nightly toolchain, using the upstream Cargo
lockfile. The toolchain is selected for this build only; your default Rust
version is unchanged. Sources and build outputs stay under the ignored
`.tools` directory; Rust keeps its toolchain and dependency caches in its
usual directories. Subsequent setup runs reuse the downloads and build cache.
No Android SDK or full Magisk APK build is needed.

Install mtkclient in a separate directory from this repository:

```bash
git clone --recursive https://github.com/bkerler/mtkclient.git
cd mtkclient
"$(brew --prefix python@3.13)/bin/python3.13" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --no-binary capstone -r requirements.txt
export DYLD_LIBRARY_PATH="$(brew --prefix libusb)/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
python mtk_gui.py
```

See the [upstream macOS installation instructions](https://github.com/bkerler/mtkclient/blob/main/README-INSTALL.md#macos)
for troubleshooting. Upstream also documents macFUSE for filesystem mounting;
that is separate from reading/writing partitions. If your checkout requires it,
follow the upstream installation instructions. Use the Homebrew Python matching
your Mac architecture, rather than a Rosetta Python on Apple Silicon.

## 2. Connect and back up

Follow the physical connection instructions in [GUIDE.md](GUIDE.md). Connect the
SBC's micro-USB port to the Mac using a **data-capable cable** and a USB-C adapter
if needed. Run mtkclient directly on macOS.

With mtkclient waiting, power cycle the Tonal as described in the guide. Back up
**every partition**, including userdata, and keep the originals separately.
If mtkclient cannot detect/read the device, stop here and troubleshoot USB;
the patcher cannot fix a USB/BROM connection problem. macOS support upstream
does not establish compatibility with every Tonal firmware or USB adapter.

## 3. Patch a copy

In this repository's directory, place a **copy** of the original `boot.bin`
(or `boot.img`; if both exist, `boot.img` takes precedence), then run:

```bash
bash patcher.sh
```

Do not use `sudo`. The first patch run downloads Magisk v27.0 and
TextLauncher 1.4.1. Patching leaves the input image unchanged and produces `boot.patched.img` and `start.adb.sh` in the current
directory. Move any previous patched image aside before rerunning.

The patcher creates a dedicated ADB key pair in `~/tonal_keys` without deleting
your normal `~/.android` keys. Keep the Tonal private key backed up. Only the
public key is embedded in the boot image. Generated images, APKs and helpers
are ignored by Git.

The patcher checks that the output can be unpacked, that `init` and the injected
files have the expected root ownership and permissions, and that the embedded
public key matches. Those checks do **not** prove that the image will boot or
that the device can be recovered.

## 4. Flash and connect

After verifying your complete original backups, use the **native mtkclient GUI**
to write `boot.patched.img` to the **boot partition only**. Exit mtkclient and
power cycle the Tonal. Then, from this repository's directory:

```bash
bash start.adb.sh
adb devices -l
adb install Magisk-v27.0.apk
```

The helper restarts the Mac's ADB server with the dedicated key (interrupting
any current ADB sessions). It prints the detected devices. If more than one
device is attached, select the Tonal with `adb -s SERIAL ...` for subsequent
commands. An empty/unauthorized list requires connection troubleshooting; it
does not establish that patching or flashing succeeded.

The native patcher has been tested on Apple Silicon with synthetic boot images
and the saved Tonal boot image, including preservation of existing archive
ownership and file modes. Intel Mac execution and successful patched boot/ADB
remain unverified. Keep the recovery instructions in
[GUIDE.md](GUIDE.md) in mind before flashing.

## Development check

After setup, run `python3 tests/smoke_patcher.py`. It patches disposable synthetic
images natively and checks metadata preservation, public-key injection, key
reuse, paths with spaces, overwrite refusal, and invalid-input rejection. Its
images are not device firmware and must never be flashed.
