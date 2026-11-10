"""Check newc archive metadata without extracting files onto the host."""
from pathlib import Path
import stat
import sys


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


def verify(archive, public_key):
    entries = read_newc(Path(archive).read_bytes())
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
    print("    -> Ramdisk ownership, modes, payloads, and ADB key: PASS")


if __name__ == "__main__":
    verify(*sys.argv[1:])
