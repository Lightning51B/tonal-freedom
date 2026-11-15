"""Check newc archive metadata without extracting files onto the host."""
from pathlib import Path
import lzma
import hashlib
import json
import stat
import subprocess
import sys
import tempfile


def compatible_xz(content):
    # Magisk 27 embeds an LZMA2-only decoder (no BCJ filters, CRC32).
    # magiskboot 31 auto-selects ARM/ARM64 BCJ for ELF inputs.
    return lzma.compress(content, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC32,
                         filters=[{"id": lzma.FILTER_LZMA2, "dict_size": 1 << 23}])


def normalize_xz(archive, magiskboot):
    entries = read_newc(Path(archive).read_bytes())
    with tempfile.TemporaryDirectory(prefix="tonal-xz-") as directory:
        for index, (name, (mode, uid, gid, content)) in enumerate(entries.items()):
            if not name.endswith('.xz'):
                continue
            if not stat.S_ISREG(mode) or (uid, gid) != (0, 0):
                raise ValueError(f"Unexpected compressed payload metadata: {name}")
            payload = Path(directory) / str(index)
            payload.write_bytes(compatible_xz(lzma.decompress(content)))
            subprocess.run([magiskboot, 'cpio', archive,
                            f'add {stat.S_IMODE(mode):04o} {name} {payload}'], check=True)
    print("    -> Compressed payloads converted for Magisk 27")


def verify_runtime(entries, original):
    for name, (_, _, _, content) in entries.items():
        if name.endswith('.xz') and content != compatible_xz(lzma.decompress(content)):
            raise ValueError(f"Magisk 27 incompatible XZ encoding: {name}")
    stock = read_newc(Path(original).read_bytes())['init']
    if '.backup/init' in entries:
        restored = entries['.backup/init']
    else:
        mode, uid, gid, data = entries['.backup/init.xz']
        restored = (mode, uid, gid, lzma.decompress(data))
    if restored != stock:
        raise ValueError("Magisk cannot restore the exact original init and metadata")


def read_newc(data):
    entries = {}
    offset = 0
    while True:
        header = data[offset:offset + 110]
        if len(header) != 110 or header[:6] not in (b"070701", b"070702"):
            raise ValueError("Invalid or truncated newc archive")
        fields = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
        mode, uid, gid, size, namesize = fields[1], fields[2], fields[3], fields[6], fields[11]
        offset += 110
        name_bytes = data[offset:offset + namesize]
        if not name_bytes or name_bytes[-1:] != b"\0":
            raise ValueError("Invalid archive entry name")
        name = name_bytes[:-1].decode()
        offset = (offset + namesize + 3) & ~3
        content = data[offset:offset + size]
        if len(content) != size:
            raise ValueError("Truncated archive entry")
        offset = (offset + size + 3) & ~3
        if name == "TRAILER!!!":
            return entries
        if name in entries:
            raise ValueError(f"Duplicate archive entry: {name}")
        entries[name] = (mode, uid, gid, content)


def verify(archive, public_key, original, image=None, source=None, receipt=None):
    entries = read_newc(Path(archive).read_bytes())
    verify_runtime(entries, original)
    expected = {
        "init": 0o750,
        "overlay.d/adb_keys": 0o640,
        "overlay.d/custom.rc": 0o644,
        "overlay.d/sbin/bypass_kiosk.sh": 0o755,
        "overlay.d/sbin/textlauncher.apk": 0o644,
    }
    for name, permissions in expected.items():
        mode, uid, gid, content = entries[name]
        if (uid, gid) != (0, 0) or stat.S_IMODE(mode) != permissions:
            raise ValueError(f"Incorrect ownership or permissions: {name}")
        if not stat.S_ISREG(mode) or not content:
            raise ValueError(f"Missing regular file payload: {name}")
    if entries["overlay.d/adb_keys"][3] != Path(public_key).read_bytes():
        raise ValueError("Injected ADB public key does not match")
    if receipt:
        Path(receipt).write_text(json.dumps(dict(version=1, magisk27_xz=True,
            image=hashlib.sha256(Path(image).read_bytes()).hexdigest(),
            source=hashlib.sha256(Path(source).read_bytes()).hexdigest()), indent=2) + '\n')
    print("    -> Magisk 27 compression, original init, ownership, modes, payloads, and ADB key: PASS")


if __name__ == "__main__":
    if sys.argv[1] == '--normalize-xz':
        normalize_xz(*sys.argv[2:])
    else:
        verify(*sys.argv[1:])
