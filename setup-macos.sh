#!/bin/bash
# Build only the host boot-image utility from pinned upstream Magisk sources.
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
if [ "$(uname -s)" != Darwin ] || [ "$(id -u)" = 0 ]; then
    echo "Run this on macOS without sudo." >&2
    exit 1
fi
export PATH="$HOME/.cargo/bin:$PATH"
for cmd in git rustup cargo xcrun; do
    command -v "$cmd" >/dev/null || { echo "Missing $cmd; see MACOS.md." >&2; exit 1; }
done
xcrun --find clang++ >/dev/null
case "$(uname -m)" in
    arm64) TARGET=aarch64-apple-darwin ;;
    x86_64) TARGET=x86_64-apple-darwin ;;
    *) echo "Unsupported Mac architecture" >&2; exit 1 ;;
esac
SOURCE="$SCRIPT_DIR/.tools/Magisk"
REVISION=0972f67d97f9b6302b67c5171283330c74114b4a
TOOLCHAIN=nightly-2026-11-10
if [ ! -d "$SOURCE" ]; then
    git clone --depth 1 --branch v31.1 --recurse-submodules --shallow-submodules \
        https://github.com/topjohnwu/Magisk.git "$SOURCE"
fi
if [ "$(git -C "$SOURCE" rev-parse HEAD)" != "$REVISION" ]; then
    echo "Unexpected Magisk checkout at $SOURCE; move it aside and rerun." >&2
    exit 1
fi
git -C "$SOURCE" submodule update --init --recursive --depth 1
rustup toolchain install "$TOOLCHAIN" --profile minimal
# The host-only Cargo build needs this generated header, normally emitted by
# upstream build.py along with Android-only build configuration.
mkdir -p "$SOURCE/native/out/generated" "$SCRIPT_DIR/.tools/bin"
cat > "$SOURCE/native/out/generated/flags.h" <<'EOF'
#pragma once
#define MAGISK_VERSION "31.1"
#define MAGISK_VER_CODE 31100
#define MAGISK_DEBUG 0
EOF
# Run outside native/src so its Android Cargo configuration is not inherited.
cd "$SCRIPT_DIR"
cargo +"$TOOLCHAIN" build --manifest-path "$SOURCE/native/src/Cargo.toml" \
    --target "$TARGET" --target-dir "$SCRIPT_DIR/.tools/build" \
    --release --locked -p magiskboot --config 'profile.release.panic="abort"'
cp "$SCRIPT_DIR/.tools/build/$TARGET/release/magiskboot" "$SCRIPT_DIR/.tools/bin/magiskboot"
chmod 0755 "$SCRIPT_DIR/.tools/bin/magiskboot"
file "$SCRIPT_DIR/.tools/bin/magiskboot"
echo "Native Mac patcher ready. Run: bash patcher.sh"
