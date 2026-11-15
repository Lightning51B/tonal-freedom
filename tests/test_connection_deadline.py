"""The deadline must escape an upstream retry loop that catches exceptions."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

MODULES = str(Path(__file__).resolve().parents[1] / 'macos')


class ConnectionDeadlineTests(unittest.TestCase):
    def run_child(self, body):
        program = f'import sys; sys.path.insert(0, {MODULES!r})\nimport time\nfrom device_workflow import ConnectionDeadline\n' + body
        return subprocess.run([sys.executable, '-c', program], capture_output=True, text=True, timeout=3)

    def test_timeout_escapes_retry_loop(self):
        result = self.run_child('with ConnectionDeadline(.15):\n while True:\n  try: time.sleep(.01)\n  except Exception: pass\n')
        self.assertEqual(result.returncode, 124)
        self.assertIn('before any backup reads or flash writes', result.stdout)

    def test_success_disarms_deadline_before_transfer(self):
        result = self.run_child('with ConnectionDeadline(.1):\n pass\ntime.sleep(.2)\nprint("transfer continues")\n')
        self.assertEqual(result.returncode, 0)
        self.assertIn('transfer continues', result.stdout)


class InitialHandshakeTests(unittest.TestCase):
    def test_fresh_session_does_handshake_before_da_setup(self):
        sys.path.insert(0, MODULES)
        from device_workflow import initialize_device
        handler = Mock()
        handler.mtk.preloader.init.return_value = True
        handler.configure_da.return_value = handler.mtk
        self.assertIs(initialize_device(handler), handler.mtk)
        handler.connect.assert_not_called()
        handler.mtk.preloader.init.assert_called_once()
        handler.configure_da.assert_called_once_with(handler.mtk)

    def test_failed_handshake_never_uploads_da(self):
        sys.path.insert(0, MODULES)
        from device_workflow import initialize_device
        handler = Mock()
        handler.mtk.preloader.init.return_value = False
        with self.assertRaisesRegex(ValueError, 'handshake'):
            initialize_device(handler)
        handler.configure_da.assert_not_called()


class BootloaderWaitTests(unittest.TestCase):
    def test_previous_loader_session_requires_new_power_cycle(self):
        sys.path.insert(0, MODULES)
        from device_workflow import wait_for_bootloader
        loader = SimpleNamespace(idProduct=0x2000)
        states = iter([[loader], [loader], [], [loader]])
        sleep = Mock()
        wait_for_bootloader(lambda: next(states), sleep, {0x2000, 3})
        self.assertEqual(sleep.call_count, 3)

    def test_waits_through_android_and_power_off_without_claiming(self):
        sys.path.insert(0, MODULES)
        from device_workflow import wait_for_bootloader
        states = iter([[SimpleNamespace(idProduct=0x2008)], [], [SimpleNamespace(idProduct=0x2000)]])
        sleep = Mock()
        wait_for_bootloader(lambda: next(states), sleep, {0x2000, 3})
        self.assertEqual(sleep.call_count, 2)

    def test_multiple_bootloaders_fail_closed(self):
        sys.path.insert(0, MODULES)
        from device_workflow import wait_for_bootloader
        with self.assertRaisesRegex(ValueError, 'Multiple'):
            wait_for_bootloader(lambda: [SimpleNamespace(idProduct=0x2000)]*2, Mock(), {0x2000, 3})


if __name__ == '__main__': unittest.main()
