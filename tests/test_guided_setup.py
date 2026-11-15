import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'macos'))
import guided_setup as setup


class GuidedSetupTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)
        self.client = Mock(state=self.path, adb=self.path / 'bin/adb')
        self.client.connect.return_value = '192.168.1.42:5555'
        (self.path / 'textlauncher.apk').write_bytes(b'fixture')
        self.output = contextlib.redirect_stdout(io.StringIO()); self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_launcher_checks_install_and_foreground(self):
        self.client.command.return_value = 'Success\r\n'
        self.client.shell.side_effect = ['package:/data/app/base.apk', 'Starting', 'mResumedActivity: ademar.textlauncher/.Activity']
        setup.install_launcher(self.client)
        self.client.connect.assert_called_once()
        self.assertEqual(self.client.shell.call_count, 3)

    def test_android_install_failure_does_not_launch(self):
        self.client.command.return_value = 'Failure [INSTALL_FAILED]'
        with self.assertRaisesRegex(RuntimeError, 'did not confirm'):
            setup.install_launcher(self.client)
        self.client.shell.assert_not_called()

    def test_missing_launcher_foreground_is_not_success(self):
        self.client.command.return_value = 'Success'
        self.client.shell.side_effect = ['package:/data/app/base.apk', 'Starting', 'mResumedActivity: com.tonal.other']
        with self.assertRaisesRegex(RuntimeError, 'foreground'):
            setup.install_launcher(self.client)

    def test_root_denial_blocks_ota_mutations(self):
        self.client.shell.return_value = 'Permission denied'
        with self.assertRaisesRegex(RuntimeError, 'superuser'):
            setup.set_ota_block(self.client)
        self.client.command.assert_not_called()
        self.assertFalse((self.path / 'OTA').exists())

    def test_ota_requires_verified_disabled_states(self):
        with patch.object(setup, 'require_root'), patch.object(setup, 'root', return_value='wrong startup script'), \
             patch.object(setup, 'package_state', return_value=0):
            with self.assertRaisesRegex(RuntimeError, 'not saved correctly'):
                setup.set_ota_block(self.client)
        self.assertFalse((self.path / 'OTA/guided-status.json').exists())

    def test_allow_ota_removes_service_and_checks_both_packages(self):
        with patch.object(setup, 'require_root'), patch.object(setup, 'root', side_effect=['', 'absent']) as root, \
             patch.object(setup, 'package_state', return_value=0) as state:
            setup.set_ota_block(self.client, False)
            self.assertIn('rm -f /data/adb/service.d/tonal-block-ota.sh', root.call_args_list[0].args[2])
            self.assertEqual(state.call_count, 4)
        self.assertTrue((self.path / 'OTA/guided-status.json').exists())

    def test_allow_ota_does_not_report_success_for_still_disabled_package(self):
        with patch.object(setup, 'require_root'), patch.object(setup, 'root', side_effect=['', 'absent']), \
             patch.object(setup, 'package_state', side_effect=[3, 3, 3]):
            with self.assertRaisesRegex(RuntimeError, 'did not persist'):
                setup.set_ota_block(self.client, False)
        self.assertFalse((self.path / 'OTA/guided-status.json').exists())
