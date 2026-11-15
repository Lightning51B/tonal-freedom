"""Wireless setup/reconnect/install behavior without ADB or device access."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'macos'))
from wireless import Wireless


class FakeWireless(Wireless):
    def __init__(self, folder):
        self.state = Path(folder)
        self.settings = self.state / 'wireless.json'
        self.calls = []
        self.auth = '1'
        self.uid = '2000'
        self.network_id = '0123456789abcdef'
        self.port = '5555'
        self.authorized = True

    def command(self, *args, timeout=30):
        self.calls.append(args)
        if args[0] in ('connect', 'disconnect'):
            return 'connected'
        if args[:1] == ('-s',):
            target, command, *values = args[1:]
            if command == 'get-state':
                if not self.authorized: raise RuntimeError('unauthorized')
                return 'device'
            if command == 'install': return 'Success'
            if command == 'shell':
                if values[:1] == ['getprop']:
                    if values[1] == 'ro.serialno': return 'TONAL_TEST'
                    if values[1] in ('ro.secure', 'ro.adb.secure'): return self.auth
                    return self.port
                if values[:1] == ['id']: return self.uid
                if values[:1] == ['settings']:
                    return self.network_id if ':' in target else '0123456789abcdef'
                if values[:1] == ['ip']: return 'inet 192.168.1.42/24 scope global wlan0'
        raise AssertionError(args)


class WirelessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.client = FakeWireless(self.temp.name)

    def test_discovery_uses_existing_studio_usb_without_emulators(self):
        def listing(port, *args, **kwargs):
            if port == '5038': return 'List of devices attached\nemulator-5554 unauthorized transport_id:1'
            return 'List of devices attached\nTONAL device usb:123\n192.168.1.42:5555 device'
        with patch.object(self.client, 'command_on', side_effect=listing), \
             patch('wireless.socket.create_connection'):
            devices = self.client.usb_devices()
            self.assertEqual(set(devices), {'TONAL'})
            self.client.select_usb('TONAL')
        self.assertEqual(self.client.usb_port, '5037')

    def test_unauthorized_usb_requires_user_authorization(self):
        with patch.object(self.client, 'usb_devices', return_value={'TONAL': ('5037', 'unauthorized', '')}):
            with self.assertRaisesRegex(RuntimeError, 'allow USB debugging'):
                self.client.select_usb('TONAL')

    def test_only_selected_usb_commands_use_studio_server(self):
        self.client.usb_serial, self.client.usb_port = 'TONAL', '5037'
        with patch.object(self.client, 'command_on', return_value='ok') as command:
            Wireless.command(self.client, '-s', 'TONAL', 'shell', 'id')
            command.assert_called_with('5037', '-s', 'TONAL', 'shell', 'id', timeout=30)
            Wireless.command(self.client, 'connect', '192.168.1.42:5555')
            command.assert_called_with('5038', 'connect', '192.168.1.42:5555', timeout=30)

    def test_denied_root_never_installs_service(self):
        with patch.object(self.client, 'select_usb'), patch.object(self.client, 'shell',
                side_effect=['1', '1', 'package:magisk', 'Permission denied']):
            with self.assertRaisesRegex(RuntimeError, 'root access was not granted'):
                self.client.prepare_wireless('TONAL')
        self.assertEqual(self.client.calls, [])

    def test_setup_saves_only_after_network_verification(self):
        self.client.configure('USB_SERIAL')
        saved = json.loads(self.client.settings.read_text())
        self.assertEqual(saved['host'], '192.168.1.42')
        self.assertIn(('connect', '192.168.1.42:5555'), self.client.calls)

    def test_auth_disabled_blocks_setup(self):
        self.client.auth = '0'
        with self.assertRaisesRegex(RuntimeError, 'Authenticated'): self.client.configure('USB_SERIAL')
        self.assertFalse(self.client.settings.exists())
        self.assertFalse(any(x[0] == 'connect' for x in self.client.calls))

    def test_root_adb_blocks_setup(self):
        self.client.uid = '0'
        with self.assertRaisesRegex(RuntimeError, 'shell user'): self.client.configure('USB_SERIAL')

    def test_nonpersistent_port_blocks_setup(self):
        self.client.port = '-1'
        with self.assertRaisesRegex(RuntimeError, 'Persistent'): self.client.configure('USB_SERIAL')

    def test_wrong_network_device_not_saved(self):
        self.client.network_id = 'fedcba9876543210'
        with self.assertRaisesRegex(RuntimeError, 'different device'): self.client.configure('USB_SERIAL')
        self.assertFalse(self.client.settings.exists())

    def test_unauthorized_target_not_saved(self):
        self.client.authorized = False
        with patch('wireless.time.sleep'), self.assertRaisesRegex(RuntimeError, 'did not authorize'):
            self.client.configure('USB_SERIAL')
        self.assertFalse(self.client.settings.exists())

    def test_reconnect_and_install_use_saved_target(self):
        self.client.configure('USB_SERIAL')
        apk = Path(self.temp.name) / 'test app.apk'
        with zipfile.ZipFile(apk, 'w') as out: out.writestr('AndroidManifest.xml', 'test')
        self.client.install(apk)
        self.assertIn(('-s', '192.168.1.42:5555', 'install', '-r', str(apk.resolve())), self.client.calls)

    def test_changed_ip_requires_same_identity(self):
        self.client.configure('USB_SERIAL')
        self.client.connect('192.168.1.43')
        self.assertEqual(json.loads(self.client.settings.read_text())['host'], '192.168.1.43')
        self.client.network_id = 'fedcba9876543210'
        with self.assertRaises(RuntimeError): self.client.connect('192.168.1.44')
        self.assertEqual(json.loads(self.client.settings.read_text())['host'], '192.168.1.43')

    def test_unconfigured_install_stops(self):
        with self.assertRaisesRegex(RuntimeError, 'step 5'): self.client.connect()

    def test_reject_external_or_malformed_addresses(self):
        for address in ('8.8.8.8', '127.0.0.1', '192.168.1.2:5555', 'localhost', '0.0.0.0', '192.0.2.1', 'x;touch /tmp/no'):
            with self.subTest(address=address), self.assertRaises(ValueError): Wireless.address(address)


if __name__ == '__main__': unittest.main()
