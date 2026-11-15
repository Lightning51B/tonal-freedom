"""No-device tests of backup completeness and guarded boot-only writes."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'macos'))
import device_workflow as workflow


class StorageAreaTests(unittest.TestCase):
    def test_legacy_boot_regions_use_the_populated_legacy_fields(self):
        config = SimpleNamespace(
            storage=SimpleNamespace(flashsize=31268536320,
                emmc=SimpleNamespace(boot1_size=0, boot2_size=0)),
            legacy_storage=SimpleNamespace(emmc=SimpleNamespace(
                m_emmc_boot1_size=4194304, m_emmc_boot2_size=4194304)))
        self.assertEqual(workflow.emmc_areas(config, True),
                         {'user':31268536320, 'boot1':4194304, 'boot2':4194304})
        self.assertEqual(workflow.emmc_areas(config, False), {'user':31268536320})


class DeviceReadTests(unittest.TestCase):
    def test_large_read_uses_complete_single_packet_transactions(self):
        device = workflow.Device.__new__(workflow.Device)
        device.da = Mock()
        size = 2 * 1024 * 1024 + 512
        source = bytes(range(256)) * ((size + 4096) // 256)
        # Reproduce pinned legacy reader returning only the first 1MiB.
        device.da.readflash.side_effect = lambda addr, length, **kw: source[addr:addr + min(length, 1024 * 1024)]
        self.assertEqual(device.read('boot1', 4096, size), source[4096:4096 + size])
        calls = device.da.readflash.call_args_list
        self.assertEqual([c.kwargs['addr'] for c in calls], [4096, 4096 + 1048576, 4096 + 2097152])
        self.assertEqual([c.kwargs['length'] for c in calls], [1048576, 1048576, 512])
        self.assertTrue(all(c.kwargs['parttype'] == 'boot1' for c in calls))

    def test_short_packet_stops_without_requesting_next_transaction(self):
        device = workflow.Device.__new__(workflow.Device)
        device.da = Mock()
        device.da.readflash.return_value = b'bad'
        with self.assertRaisesRegex(ValueError, 'expected 1048576 bytes, received 3'):
            device.read('user', 0, 2097152)
        self.assertEqual(device.da.readflash.call_count, 1)


class FakeDevice:
    identity = {'hwcode': '1', 'meid': 'aabb', 'cid': 'ccdd'}
    description = 'TEST DEVICE — NEVER FLASH'
    areas = {'user': 8192, 'boot1': 512, 'boot2': 512}
    layout = [{'name': 'boot', 'offset': 512, 'size': 2048},
              {'name': 'userdata', 'offset': 2560, 'size': 5632}]
    boot = layout[0]

    def __init__(self):
        self.memory = {'user': bytearray(b'U' * 8192), 'boot1': b'1' * 512, 'boot2': b'2' * 512}
        self.memory['user'][512:520] = b'ANDROID!'
        self.writes = []
        self.short = False
        self.bad_write = False

    def read(self, area, offset, size):
        result = bytes(self.memory[area][offset:offset + size])
        if self.short:
            raise OSError('Simulated disconnect')
        return result

    def write_boot(self, data):
        self.writes.append((self.boot['offset'], len(data)))
        if not self.bad_write:
            self.memory['user'][512:2560] = data


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.backup = self.root / 'backup'; self.backup.mkdir()
        self.run = self.root / 'run'; self.run.mkdir()
        self.device = FakeDevice()
        self.stdout = contextlib.redirect_stdout(io.StringIO()); self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)
        workflow.backup(self.device, self.backup)
        self.manifest = workflow.validate_backup(self.backup)
        (self.run / 'boot.bin').write_bytes((self.backup / 'boot.bin').read_bytes())
        (self.run / 'boot.patched.img').write_bytes(b'ANDROID!' + b'P' * 1016)
        (self.run / 'patch-validation.json').write_text(json.dumps(dict(version=1, magisk27_xz=True,
            image=workflow.digest(self.run / 'boot.patched.img'),
            source=workflow.digest(self.run / 'boot.bin'))))
        workflow.seal_patch(self.run, self.backup)

    def attempt(self, approve=lambda _: True):
        workflow.flash(self.device, self.run, self.manifest, approve)

    def test_legacy_patch_rejected_before_device_read_or_write(self):
        (self.run / 'patch-validation.json').unlink()
        self.device.read = lambda *args: self.fail('Must reject before contacting device')
        with self.assertRaisesRegex(ValueError, 'predates'):
            self.attempt()
        self.assertFalse(self.device.writes)

    def test_stale_validation_rejected(self):
        report = json.loads((self.run / 'patch-validation.json').read_text())
        report['image'] = 'wrong'
        (self.run / 'patch-validation.json').write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.attempt()
        self.assertFalse(self.device.writes)

    def test_restore_original_boot_and_verify_without_touching_other_data(self):
        original = bytes(self.device.memory['user'])
        self.attempt()
        workflow.restore_boot(self.device, self.run, self.manifest, lambda _: True)
        self.assertEqual(bytes(self.device.memory['user']), original)
        self.assertTrue(json.loads((self.run / 'restore-result.json').read_text())['verified'])

    def test_restore_rejects_unknown_current_boot(self):
        self.attempt(); self.device.memory['user'][600] ^= 1
        count = len(self.device.writes)
        with self.assertRaisesRegex(ValueError, 'recorded flash'):
            workflow.restore_boot(self.device, self.run, self.manifest, lambda _: True)
        self.assertEqual(len(self.device.writes), count)

    def test_restore_requires_confirmation(self):
        self.attempt(); count = len(self.device.writes)
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            workflow.restore_boot(self.device, self.run, self.manifest, lambda _: False)
        self.assertEqual(len(self.device.writes), count)

    def test_restore_readback_failure_never_records_success(self):
        self.attempt(); self.device.bad_write = True
        with self.assertRaisesRegex(ValueError, 'RESTORE VERIFICATION FAILED'):
            workflow.restore_boot(self.device, self.run, self.manifest, lambda _: True)
        self.assertFalse((self.run / 'restore-result.json').exists())

    def test_restore_rejects_wrong_device(self):
        self.attempt(); self.device.identity = dict(self.device.identity, cid='different')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            workflow.restore_boot(self.device, self.run, self.manifest, lambda _: True)

    def test_complete_backup_and_exact_boot_write(self):
        self.assertEqual(set(self.manifest['files']), {'user', 'boot1', 'boot2', 'boot'})
        before = bytes(self.device.memory['user'])
        self.attempt()
        self.assertEqual(self.device.writes, [(512, 2048)])
        self.assertEqual(self.device.memory['user'][:512], before[:512])
        self.assertEqual(self.device.memory['user'][1536:], before[1536:])
        self.assertTrue(json.loads((self.run / 'flash-result.json').read_text())['verified'])

    def test_reject_wrong_device(self):
        self.device.identity = dict(self.device.identity, meid='different')
        with self.assertRaisesRegex(ValueError, 'device does not match'): self.attempt()
        self.assertEqual(self.device.writes, [])

    def test_reject_layout_change(self):
        self.device.layout = copy.deepcopy(self.device.layout)
        self.device.layout[0]['offset'] = 0
        with self.assertRaisesRegex(ValueError, 'layout changed'): self.attempt()
        self.assertEqual(self.device.writes, [])

    def test_reject_changed_current_boot(self):
        self.device.memory['user'][520] = 1
        with self.assertRaisesRegex(ValueError, 'Current boot differs'): self.attempt()
        self.assertEqual(self.device.writes, [])

    def test_reject_changed_patch(self):
        (self.run / 'boot.patched.img').write_bytes(b'ANDROID!' + b'wrong')
        with self.assertRaisesRegex(ValueError, 'image changed'): self.attempt()
        self.assertEqual(self.device.writes, [])

    def test_cancel_never_writes(self):
        with self.assertRaisesRegex(ValueError, 'cancelled'): self.attempt(lambda _: False)
        self.assertEqual(self.device.writes, [])

    def test_readback_failure_not_success(self):
        self.device.bad_write = True
        with self.assertRaisesRegex(ValueError, 'VERIFICATION FAILED'): self.attempt()
        self.assertFalse((self.run / 'flash-result.json').exists())

    def test_corrupt_backup_rejected(self):
        (self.backup / 'user.bin').write_bytes(b'X' * 8192)
        with self.assertRaisesRegex(ValueError, 'hash changed'): workflow.validate_backup(self.backup)

    def test_missing_backup_rejected(self):
        (self.backup / 'boot2.bin').unlink()
        with self.assertRaises(FileNotFoundError): workflow.validate_backup(self.backup)

    def test_partial_backup_never_complete(self):
        target = self.root / 'partial'; target.mkdir(); self.device.short = True
        with self.assertRaises(OSError): workflow.backup(self.device, target)
        self.assertFalse((target / 'backup.json').exists())

    def test_short_backup_read_never_complete(self):
        target = self.root / 'short'; target.mkdir()
        self.device.read = lambda area, offset, size: b'x' * (size - 1)
        with self.assertRaisesRegex(ValueError, 'Short backup read'): workflow.backup(self.device, target)
        self.assertFalse((target / 'backup.json').exists())

    def test_incomplete_manifest_rejected(self):
        manifest = dict(self.manifest, complete=False)
        (self.backup / 'backup.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'incomplete'): workflow.validate_backup(self.backup)

    def test_low_disk_space_stops_before_read(self):
        target = self.root / 'low'; target.mkdir()
        with patch.object(workflow.shutil, 'disk_usage', return_value=type('Usage', (), {'free': 0})()):
            with self.assertRaisesRegex(ValueError, 'free disk'): workflow.backup(self.device, target)
        self.assertFalse((target / 'backup.json').exists())

    def test_oversized_patch_rejected(self):
        (self.run / 'boot.patched.img').write_bytes(b'ANDROID!' + b'X' * 4096)
        with self.assertRaisesRegex(ValueError, 'exceeds boot'): workflow.seal_patch(self.run, self.backup)

    def test_existing_backup_not_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'new backup'): workflow.backup(self.device, self.backup)


if __name__ == '__main__': unittest.main()
