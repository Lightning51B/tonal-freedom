"""Device operations with fail-closed backup provenance and boot-only writes."""
import hashlib
import json
import logging
import os
from pathlib import Path
import select
import shutil
import threading
import sys
import tempfile
import time

CHUNK = 16 * 1024 * 1024


def require(condition, message):
    # These checks must remain enabled even with optimized Python builds.
    if not condition:
        raise ValueError(message)


def event(kind, **values):
    print('TONAL_EVENT ' + json.dumps(dict(kind=kind, **values)), flush=True)


def digest(path, label='Verifying backup'):
    h = hashlib.sha256()
    size = path.stat().st_size
    done = 0
    with path.open('rb') as source:
        while data := source.read(CHUNK):
            h.update(data)
            done += len(data)
            event('progress', message=label, percent=done * 100 / max(size, 1))
    return h.hexdigest()


def save(path, value):
    temp = path.with_suffix('.partial')
    temp.write_text(json.dumps(value, indent=2))
    temp.replace(path)


def validate_backup(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'backup.json').read_text())
    require(manifest['version'] == 1 and manifest['complete'] is True, 'Backup incomplete')
    expected = set(manifest['areas']) | {'boot'}
    require(set(manifest['files']) == expected and 'user' in expected, 'Missing backup areas')
    for name, record in manifest['files'].items():
        require(name in {'user', 'boot1', 'boot2', 'boot'}, 'Unexpected backup file')
        path = folder / (name + '.bin')
        require(path.stat().st_size == record['size'], f'{name}: backup size changed')
        require(digest(path, 'Verifying ' + name) == record['sha256'], f'{name}: backup hash changed')
    return manifest


class ConnectionDeadline:
    """Only guards connection/DA setup, never a backup read or flash write.

    mtkclient catches Exception (including TimeoutError) inside its USB retry
    loop. A Python alarm exception therefore cannot enforce a time limit.
    """
    def __init__(self, seconds=120, exit_process=None):
        self.exit_process = exit_process or os._exit
        self.lock = threading.Lock()
        self.active = False
        self.timer = threading.Timer(seconds, self.expire)
        self.timer.daemon = True

    def expire(self):
        with self.lock:
            if self.active:
                event('status', message='Connection initialization timed out before any backup reads or flash writes. See the last output lines for the stage that stopped, then retry after a power cycle.')
                self.exit_process(124)

    def __enter__(self):
        self.active = True
        self.timer.start()
        return self

    def __exit__(self, *_):
        with self.lock:
            self.active = False
        self.timer.cancel()


def describe_usb():
    import usb.core
    devices = [(dev.idVendor, dev.idProduct) for dev in usb.core.find(find_all=True)
               if dev.idVendor == 0x0e8d]
    if not devices:
        event('status', message='No MediaTek USB device visible yet. Waiting for the Tonal power cycle.')
    for vendor, product in devices:
        mode = 'Trainer/Android mode; waiting for its bootloader' if product == 0x2008 else 'MediaTek USB device'
        event('status', message=f'USB {vendor:04x}:{product:04x} — {mode}')


def wait_for_bootloader(enumerate_devices=None, pause=time.sleep, allowed_pids=None):
    if enumerate_devices is None:
        import usb.core
        enumerate_devices = lambda: usb.core.find(find_all=True, idVendor=0x0e8d)
    if allowed_pids is None:
        from mtkclient.config.usb_ids import default_ids
        allowed_pids = default_ids[0x0e8d]
    previous = None
    fresh_cycle_required = None
    while True:
        devices = list(enumerate_devices())
        modes = sorted(dev.idProduct for dev in devices)
        matching = [dev for dev in devices if dev.idProduct in allowed_pids]
        require(len(matching) < 2, 'Multiple MediaTek bootloader devices connected; leave only the Tonal attached')
        if fresh_cycle_required is None:
            fresh_cycle_required = bool(matching)
            if fresh_cycle_required:
                event('status', message='Previous bootloader session is still connected. Power Tonal off for 10 seconds, then on to start a fresh backup.')
        if fresh_cycle_required:
            if not matching:
                fresh_cycle_required = False
            else:
                pause(.05)
                continue
        if matching:
            event('status', message=f'Bootloader USB 0e8d:{matching[0].idProduct:04x} detected — starting handshake')
            return
        if modes != previous:
            if 0x2008 in modes:
                message = 'Tonal is in normal Trainer mode. Leave USB attached and power cycle when ready.'
            elif not modes:
                message = 'Waiting for Tonal to power on; leave the data cable attached.'
            else:
                message = 'Waiting for a supported Tonal bootloader USB mode.'
            event('status', message=message)
            previous = modes
        pause(.05)


def initialize_device(handler):
    # A fresh session has no DA state to resume. Calling handler.connect first
    # claims a transient preloader port without doing the handshake; upstream
    # Port.handshake then skips its loop while cdc.connected is already true.
    mtk = handler.mtk
    require(mtk.preloader.init(directory=os.getcwd()), 'Could not complete the Tonal bootloader handshake')
    mtk = handler.configure_da(mtk)
    require(mtk is not None, 'Could not initialize download agent')
    return mtk


def emmc_areas(daconfig, legacy):
    areas = {'user': int(daconfig.storage.flashsize)}
    for name in ('boot1', 'boot2'):
        # Legacy DA populates legacy_storage only; the generic EmmcInfo fields
        # remain zero even when the device reports boot regions.
        info = daconfig.legacy_storage.emmc if legacy else daconfig.storage.emmc
        field = 'm_emmc_' + name + '_size' if legacy else name + '_size'
        size = int(getattr(info, field))
        require(size >= 0, 'Invalid eMMC boot-region size')
        if size:
            areas[name] = size
    return areas


class Device:
    def __init__(self, wait_for_power_cycle=True):
        from mtkclient.config.mtk_config import MtkConfig
        from mtkclient.Library.Partitions.gpt import GptSettings
        from mtkclient.Library.mtk_class import Mtk
        from mtkclient.Library.DA.mtk_da_handler import DaHandler
        config = MtkConfig(loglevel=logging.INFO)
        config.gpt_settings = GptSettings(0, 0, 0)
        config.reconnect = True
        config.uartloglevel = 2
        config.logchannel = 'UART'
        config.write_preloader_to_file = False
        # macOS owns the preloader CDC interface. Its native serial transport
        # completed the physical Tonal handshake where direct libusb did not.
        serial_port = 'DETECT' if sys.platform == 'darwin' else None
        handler = DaHandler(Mtk(config=config, loglevel=logging.INFO,
                               serialportname=serial_port), logging.INFO)
        if wait_for_power_cycle:
            wait_for_bootloader()
        else:
            event('status', message='Waiting for Tonal — connect USB and power cycle now (2-minute timeout)')
            describe_usb()
        with ConnectionDeadline():
            mtk = initialize_device(handler)
        self.mtk = mtk
        self.da = mtk.daloader
        from mtkclient.config.brom_config import DAmodes
        self.streaming_legacy = self.da.flashmode == DAmodes.LEGACY
        storage = self.da.daconfig.storage
        require(storage.flashtype == 'emmc', 'Only eMMC Tonal 1 devices are supported')
        self.areas = emmc_areas(self.da.daconfig, self.streaming_legacy)
        require(self.da.partition_table_category() == 'GPT', 'Unsupported partition table')
        _, gpt = self.da.get_gpt(parttype='user')
        require(gpt is not None, 'Could not read GPT')
        self.layout = [{'name': p.name, 'offset': int(p.sector * mtk.config.pagesize),
                        'size': int(p.sectors * mtk.config.pagesize)} for p in gpt.partentries]
        names = [p['name'] for p in self.layout]
        require(names.count('boot') == 1 and names.count('userdata') == 1, 'Expected Tonal 1 boot/userdata layout not found')
        require(len(names) == len(set(names)), 'Ambiguous partition table')
        self.boot = next(p for p in self.layout if p['name'] == 'boot')
        for part in self.layout:
            require(part['offset'] >= 0 and part['size'] > 0 and part['offset'] + part['size'] <= self.areas['user'], 'Invalid partition bounds')
        def hexvalue(value):
            return value.hex() if isinstance(value, (bytes, bytearray)) else str(value or '')
        self.identity = {'hwcode': str(mtk.config.hwcode), 'meid': hexvalue(mtk.config.meid),
                         'cid': hexvalue(mtk.config.cid or storage.emmc.cid)}
        require(any(self.identity[k] and set(self.identity[k]) != {'0'} for k in ('meid', 'cid')), 'No stable device identity available')
        self.description = str(mtk.config.chipconfig.name)
        event('status', message='Connected: ' + self.description)
        if wait_for_power_cycle and self.streaming_legacy and sys.platform == 'darwin':
            self.enable_bulk_reads()

    def enable_bulk_reads(self):
        from bulk_read import BulkTransport
        from mtkclient.Library.Connection.usblib import UsbClass
        from types import SimpleNamespace
        from legacy_read import read_emmc
        event('status', message='Testing direct USB for faster backup reads')
        reference = self.read('user', 0, 1024 * 1024)
        serial = self.mtk.port.cdc
        config = serial.portconfig
        serial.close()
        usb = UsbClass(portconfig=config, loglevel=logging.INFO, devclass=10)
        require(usb.connect(), 'Direct USB could not open after loader setup; saved backup checkpoints are retained')
        bulk = BulkTransport(usb)
        legacy = self.da.da
        reader = SimpleNamespace(daconfig=legacy.daconfig, Cmd=legacy.Cmd, Rsp=legacy.Rsp,
                                 usbread=bulk.read, usbwrite=bulk.write)
        try:
            start = time.monotonic()
            probe = read_emmc(reader, 'user', 0, 1024 * 1024, bulk)
            require(probe == reference, 'Direct USB probe does not match the serial read')
            speed = len(probe) / max(time.monotonic() - start, .001) / 1024**2
            event('status', message=f'Direct USB verified against serial data — probe {speed:.1f} MiB/s; full-transfer ETA will follow')
        except BaseException:
            bulk.close()
            raise
        self.bulk = bulk
        self.bulk_reader = reader

    def read(self, area, offset, size):
        if getattr(self, 'streaming_legacy', False):
            from legacy_read import read_emmc
            if hasattr(self, 'bulk'):
                return read_emmc(self.bulk_reader, area, offset, size, self.bulk)
            cdc = self.mtk.port.cdc
            return read_emmc(self.da.da, area, offset, size,
                             cdc.device if getattr(cdc, 'is_serial', False) else None)
        # Pinned legacy mtkclient reverses its in-memory remaining-byte count,
        # returning only one 1MiB packet for larger requests. Issue complete,
        # single-packet transactions rather than leaving its transfer unfinished.
        data = bytearray()
        while len(data) < size:
            count = min(1024 * 1024, size - len(data))
            position = offset + len(data)
            part = self.da.readflash(addr=position, length=count, filename='',
                                     parttype=area, display=False)
            actual = len(part) if isinstance(part, (bytes, bytearray)) else 0
            require(actual == count,
                    f'Short or failed storage read: {area} at 0x{position:x}, expected {count} bytes, received {actual}')
            data.extend(part)
        return bytes(data)

    def write_boot(self, data):
        require(len(data) == self.boot['size'], 'Boot write must exactly match partition size')
        class Progress:
            previous = -1
            def emit(self, done):
                percent = min(100, int(done * 100 / len(data)))
                if percent != self.previous:
                    self.previous = percent
                    event('progress', message='Writing boot — do not disconnect', percent=percent)
        self.mtk.config.guiprogress = Progress()
        try:
            require(self.da.writeflash(addr=self.boot['offset'], length=len(data), wdata=data,
                                     parttype='user', display=True), 'Boot write failed; keep the original backup')
        finally:
            self.mtk.config.guiprogress = None

    def close(self):
        if hasattr(self, 'bulk'):
            self.bulk.close()
        self.mtk.port.close()


def backup(device, folder):
    folder = Path(folder)
    from backup_resume import prepare, checkpoint
    require(not (folder / 'backup.json').exists(), 'Use a new backup folder')
    total = sum(device.areas.values())
    state = prepare(folder, device, CHUNK, event)
    done = sum(min(len(state['chunks'][area]) * CHUNK, size) for area, size in device.areas.items())
    require(shutil.disk_usage(folder).free > total - done + device.boot['size'] + 1024**3,
            'Not enough free disk space for a full backup')
    files = {}
    started = time.monotonic()
    initial = done
    last_log = 0
    for area, size in device.areas.items():
        require(size > 0, 'Invalid storage size')
        target = folder / (area + '.partial')
        final = folder / (area + '.bin')
        offset = min(len(state['chunks'][area]) * CHUNK, size)
        h = hashlib.sha256()
        if offset:
            with (final if final.exists() else target).open('rb') as prefix:
                for _ in range(0, offset, CHUNK):
                    h.update(prefix.read(CHUNK))
        if not final.exists():
            with target.open('r+b' if target.exists() else 'xb') as out:
                out.seek(offset)
                for position in range(offset, size, CHUNK):
                    data = device.read(area, position, min(CHUNK, size - position))
                    require(len(data) == min(CHUNK, size - position), 'Short backup read')
                    h.update(data)
                    out.write(data)
                    out.flush()
                    os.fsync(out.fileno())
                    state['chunks'][area].append(hashlib.sha256(data).hexdigest())
                    checkpoint(folder / 'resume.json', state)
                    done += len(data)
                    elapsed = max(time.monotonic() - started, .001)
                    speed = (done - initial) / elapsed
                    minutes = (total - done) / max(speed, 1) / 60
                    message = (f'Backing up {area} — {done / 1024**3:.2f}/{total / 1024**3:.2f} GiB'
                               f' • {speed / 1024**2:.1f} MiB/s • about {minutes:.0f} min left')
                    event('progress', message=message, percent=done * 100 / total)
                    if elapsed - last_log >= 30:
                        event('status', message=message)
                        last_log = elapsed
            target.replace(final)
        files[area] = {'size': size, 'sha256': h.hexdigest()}
    with (folder / 'user.bin').open('rb') as source:
        source.seek(device.boot['offset'])
        data = source.read(device.boot['size'])
    require(len(data) == device.boot['size'], 'Boot extraction failed')
    (folder / 'boot.bin').write_bytes(data)
    files['boot'] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    # Re-read saved files so an incomplete/failed write never becomes a complete backup.
    for name, record in files.items():
        require(digest(folder / (name + '.bin'), 'Checking saved ' + name) == record['sha256'], 'Operation validation failed')
    save(folder / 'backup.json', dict(version=1, complete=True, identity=device.identity,
         description=device.description, layout=device.layout, areas=device.areas, files=files))
    event('status', message='Backup verified. All user-area partitions, GPT and available boot regions saved. RPMB is not included.')


def validate_patch_receipt(folder, image_hash, source_hash):
    path = Path(folder) / 'patch-validation.json'
    require(path.is_file(), 'Patch predates the Magisk 27 compatibility fix; rebuild it before flashing')
    report = json.loads(path.read_text())
    require(report.get('version') == 1 and report.get('magisk27_xz') is True
            and report.get('image') == image_hash and report.get('source') == source_hash,
            'Patch compatibility validation does not match this image; rebuild it')


def seal_patch(folder, backup_folder):
    folder, backup_folder = Path(folder), Path(backup_folder)
    manifest = validate_backup(backup_folder)
    require(digest(folder / 'boot.bin') == manifest['files']['boot']['sha256'], 'Patch source does not match backup')
    image = folder / 'boot.patched.img'
    require(0 < image.stat().st_size <= manifest['files']['boot']['size'], 'Patched image exceeds boot partition')
    require(image.read_bytes()[:8] == b'ANDROID!', 'Unexpected patched image format')
    validate_patch_receipt(folder, digest(image), manifest['files']['boot']['sha256'])
    save(folder / 'patch.json', dict(version=1, backup=str(backup_folder.resolve()),
         source=manifest['files']['boot']['sha256'], image=digest(image)))


def flash(device, folder, manifest, approve):
    folder = Path(folder)
    record = json.loads((folder / 'patch.json').read_text())
    require(device.identity == manifest['identity'], 'Connected device does not match backup')
    require(device.layout == manifest['layout'] and device.areas == manifest['areas'], 'Device storage layout changed')
    image = (folder / 'boot.patched.img').read_bytes()
    require(hashlib.sha256(image).hexdigest() == record['image'], 'Patched image changed')
    require(record['source'] == manifest['files']['boot']['sha256'], 'Wrong patch source')
    validate_patch_receipt(folder, record['image'], record['source'])
    require(image[:8] == b'ANDROID!' and 0 < len(image) <= device.boot['size'], 'Invalid boot image size or format')
    original = (Path(record['backup']) / 'boot.bin').read_bytes()
    require(hashlib.sha256(original).hexdigest() == record['source'], 'Original boot backup changed')
    event('status', message='Checking current boot against the original backup')
    current = device.read('user', device.boot['offset'], device.boot['size'])
    require(current == original, 'Current boot differs from backup; refusing to overwrite it')
    # Preserve the original partition tail when the image is smaller than the partition.
    payload = image + original[len(image):]
    details = f"Device: {device.description}\nIdentity: {json.dumps(device.identity)}\nImage: {folder / 'boot.patched.img'}\nSHA-256: {record['image']}\nWrite: boot only ({len(payload):,} bytes)\nBackup: {record['backup']}"
    require(approve(details), 'Flash cancelled; no flash write was issued')
    event('status', message='Writing boot — keep USB connected and do not power off')
    # One bounded partition write; never a general-purpose raw flash command.
    device.write_boot(payload)
    event('status', message='Reading boot back to verify the write')
    actual = device.read('user', device.boot['offset'], device.boot['size'])
    require(actual == payload, 'FLASH VERIFICATION FAILED. Do not assume the device is bootable; retain original backups.')
    save(folder / 'flash-result.json', dict(verified=True, identity=device.identity,
         sha256=hashlib.sha256(actual).hexdigest()))
    event('progress', message='Boot flash and read-back verified. Power cycle Tonal, then connect ADB.', percent=100)


def restore_boot(device, run_folder, manifest, approve_restore):
    run_folder = Path(run_folder)
    record = json.loads((run_folder / 'patch.json').read_text())
    result = json.loads((run_folder / 'flash-result.json').read_text())
    require(device.identity == manifest['identity'] == result['identity'], 'Restore device does not match the backup')
    require(device.layout == manifest['layout'] and device.areas == manifest['areas'], 'Restore storage layout changed')
    original = (Path(record['backup']) / 'boot.bin').read_bytes()
    require(len(original) == device.boot['size'], 'Original boot has the wrong size')
    source = hashlib.sha256(original).hexdigest()
    require(source == record['source'] == manifest['files']['boot']['sha256'], 'Original boot hash mismatch')
    require(original[:8] == b'ANDROID!', 'Invalid original boot format')
    event('status', message='Reading current boot before recovery')
    current = device.read('user', device.boot['offset'], device.boot['size'])
    if current == original:
        event('status', message='Original boot is already installed; no write needed')
        return
    require(result.get('verified') is True and hashlib.sha256(current).hexdigest() == result['sha256'],
            'Current boot does not match the recorded flash; inspect before restoring')
    details = f'Restore original boot only: {len(original):,} bytes at 0x{device.boot["offset"]:x}. SHA-256: {source}. Userdata and all other partitions are untouched.'
    require(approve_restore(details), 'Restore cancelled; no write issued')
    event('status', message='Restoring original boot — keep USB and power connected')
    device.write_boot(original)
    event('status', message='Verifying restored boot against the original backup')
    actual = device.read('user', device.boot['offset'], device.boot['size'])
    require(actual == original, 'RESTORE VERIFICATION FAILED; keep USB attached and retain backups')
    save(run_folder / 'restore-result.json', dict(verified=True, identity=device.identity, sha256=source))
    event('status', message='Original boot restored and read-back verified. Power cycle to test normal startup.')


def approve(details):
    event('confirm', message=details)
    ready, _, _ = select.select([sys.stdin], [], [], 300)
    return bool(ready) and sys.stdin.readline().strip() == 'FLASH'


def main(args):
    command, *paths = args
    if command == 'seal':
        seal_patch(*paths)
        return
    manifest = None
    if command == 'flash':
        record = json.loads((Path(paths[0]) / 'patch.json').read_text())
        manifest = validate_backup(record['backup'])
    else:
        require(command == 'backup', 'Unknown device action')
    # Never reuse another device/session's .state or hwparam cache.
    with tempfile.TemporaryDirectory(prefix='tonal-usb-') as work:
        os.chdir(work)
        device = Device(wait_for_power_cycle=command == 'backup')
        try:
            if command == 'backup':
                backup(device, paths[0])
            else:
                flash(device, paths[0], manifest, approve)
        finally:
            device.close()
