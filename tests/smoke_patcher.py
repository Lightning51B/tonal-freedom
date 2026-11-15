"""Native patcher integration test using a synthetic image; never flash it.

Run after setup-macos.sh: python3 tests/smoke_patcher.py
Downloads the pinned APKs. No USB access or device commands are issued.
"""
import gzip
import hashlib
import os
import shutil
import sys
from pathlib import Path
import struct
import subprocess
import tempfile


def cpio_entry(name, data=b'', mode=0o100750, uid=0, gid=0):
    name = name.encode() + b'\0'
    fields = (1, mode, uid, gid, 1, 0, len(data), 0, 0, 0, 0, len(name), 0)
    header = b'070701' + ''.join(f'{v:08x}' for v in fields).encode() + name
    header += b'\0' * (-len(header) % 4)
    return header + data + b'\0' * (-len(data) % 4)


def page(data):
    return data + b'\0' * (-len(data) % 2048)


ROOT = Path(os.environ.get("TONAL_PATCHER_ROOT", Path(__file__).resolve().parents[1])).resolve()
sys.dont_write_bytecode = True  # Do not modify a signed app bundle during testing.
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_ramdisk import read_newc, compatible_xz
import lzma

with tempfile.TemporaryDirectory(prefix='tonal native smoke ') as directory:
    work = Path(directory)
    # Reuse bundled assets so standalone validation can deny network access.
    for name in ('Magisk-v27.0.apk', 'textlauncher.apk'):
        if (ROOT / name).is_file():
            shutil.copy2(ROOT / name, work / name)
    sentinel = cpio_entry('preserved', b'original metadata', mode=0o100640, uid=1000, gid=2000)
    # ELF machine 183 triggers the host tool's ARM64 BCJ optimization. Plain
    # text did not exercise the compression incompatibility that broke boot.
    original_init = b'\x7fELF\x02\x01' + bytes(12) + b'\xb7\x00' + b'synthetic init NEVER FLASH\n' * 512
    ramdisk = gzip.compress(cpio_entry('init', original_init) + sentinel + cpio_entry('TRAILER!!!', mode=0))
    kernel = b'Synthetic kernel - NEVER FLASH\n'
    header = struct.pack('<8s10I', b'ANDROID!', len(kernel), 0x10008000,
                         len(ramdisk), 0x11000000, 0, 0, 0x10000100, 2048, 0, 0)
    header += bytes(16 + 512 + 32 + 1024)
    boot = work / 'boot.bin'
    boot.write_bytes(page(header) + page(kernel) + page(ramdisk))
    before = hashlib.sha256(boot.read_bytes()).digest()
    env = dict(os.environ, TONAL_KEY_DIR=str(work / 'test keys'))
    run = ['bash', str(ROOT / 'patcher-macos.sh')]
    subprocess.run(run, cwd=work, env=env, check=True)
    assert hashlib.sha256(boot.read_bytes()).digest() == before
    output = work / 'boot.patched.img'
    assert output.stat().st_size > 0
    helper = work / 'start.adb.sh'
    subprocess.run(['bash', '-n', str(helper)], check=True)
    assert 'test\\ keys/adbkey' in helper.read_text()
    key = work / 'test keys/adbkey'
    private_before = key.read_bytes()
    assert key.stat().st_mode & 0o777 == 0o600
    # A second run must refuse to overwrite an existing result.
    patched_hash = hashlib.sha256(output.read_bytes()).digest()
    assert subprocess.run(run, cwd=work, env=env).returncode != 0
    assert hashlib.sha256(output.read_bytes()).digest() == patched_hash
    output.unlink()
    subprocess.run(run, cwd=work, env=env, check=True)
    assert key.read_bytes() == private_before
    inspect = work / 'inspect'
    inspect.mkdir()
    subprocess.run([str(ROOT / '.tools/bin/magiskboot'), 'unpack', str(output)], cwd=inspect, check=True)
    entries = read_newc((inspect / 'ramdisk.cpio').read_bytes())
    assert lzma.decompress(entries['.backup/init.xz'][3]) == original_init
    for name, entry in entries.items():
        if name.endswith('.xz'):
            assert entry[3] == compatible_xz(lzma.decompress(entry[3])), name
    assert entries['preserved'] == (0o100640, 1000, 2000, b'original metadata')
    assert entries['overlay.d/adb_keys'][3] == (work / 'test keys/adbkey.pub').read_bytes()
    init = entries['overlay.d/custom.rc'][3].decode()
    startup = entries['overlay.d/sbin/bypass_kiosk.sh'][3].decode()
    assert 'setprop ro.adb.secure 1' in init and 'setprop ro.secure 1' in init
    assert 'setprop service.adb.root 0' in init
    assert 'setprop service.adb.tcp.port -1' in init
    assert 'setprop persist.adb.tcp.port 5555' in startup
    assert startup.index('/sbin/resetprop ro.adb.secure 1') < startup.index('setprop persist.adb.tcp.port 5555')
    assert 'leaving network ADB disabled' in startup
    assert 'setprop ro.adb.secure 0' not in init

    # Malformed inputs must fail without leaving a purported patched image.
    output.unlink()
    boot.write_bytes(b'not a boot image')
    assert subprocess.run(run, cwd=work, env=env).returncode != 0
    assert not output.exists()
    print('PASS: native patch, metadata preserved, keys reused, helper quoting, overwrite guard, invalid input rejected')
