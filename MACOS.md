# Running natively from a Mac

Backup, patching, flashing, and ADB all run directly on macOS. Apple Silicon
and Intel Macs use a native Mach-O `magiskboot` executable built from the
[official Magisk v31.1 sources](https://github.com/topjohnwu/Magisk/tree/v31.1).
No Docker, Linux VM, or emulation is required. The Android payload and patch
script remain **Magisk v27.0**, as in the original project; v31.1 supplies only
the host boot-image utility. This project still targets Tonal 1, not Tonal 2.

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

The native patcher has been tested on Apple Silicon with synthetic boot images,
including preservation of existing archive ownership and file modes. Intel Mac
execution and physical Tonal backup, flash, boot, and ADB connection remain
unverified. Keep the risks and recovery instructions in
[GUIDE.md](GUIDE.md) in mind before flashing.

## Development check

After setup, run `python3 tests/smoke_patcher.py`. It patches disposable synthetic
images natively and checks metadata preservation, public-key injection, key
reuse, paths with spaces, overwrite refusal, and invalid-input rejection. Its
images are not device firmware and must never be flashed.
