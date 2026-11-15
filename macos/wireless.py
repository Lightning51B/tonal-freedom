"""Saved, authenticated ADB access using the app's own host server and key."""
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
import time
import zipfile
from guided_setup import install_launcher, set_ota_block

WIFI_BOOT_SCRIPT = '''#!/system/bin/sh
# Magisk late-start service; preserve authenticated, non-root ADB.
sleep 2
if [ "$(getprop ro.adb.secure)" != 1 ] || [ "$(getprop ro.secure)" != 1 ]; then
    setprop persist.adb.tcp.port -1
    setprop service.adb.tcp.port -1
    exit 1
fi
setprop service.adb.root 0
setprop persist.adb.tcp.port 5555
setprop service.adb.tcp.port 5555
setprop ctl.restart adbd
'''


class Wireless:
    def __init__(self):
        self.home = Path.home()
        self.state = self.home / 'Library/Application Support/Tonal Freedom'
        self.state.mkdir(parents=True, exist_ok=True)
        self.settings = self.state / 'wireless.json'
        self.adb = Path(sys.executable).resolve().parent.parent / 'bin/adb'
        self.env = dict(os.environ, ADB_VENDOR_KEYS=str(self.home / 'tonal_keys/adbkey'))
        # Keep this server separate from Android Studio and other devices.
        adb_home = self.state / 'ADB Home'; adb_home.mkdir(exist_ok=True)
        self.env['HOME'] = str(adb_home)
        self.env['ANDROID_USER_HOME'] = str(adb_home / '.android')
        for key in ('ADB_SERVER_SOCKET', 'ANDROID_ADB_SERVER_PORT', 'ADB_SERVER_PORT'):
            self.env.pop(key, None)

    def command(self, *args, timeout=30):
        port = getattr(self, 'usb_port', '5038') if args[:2] == ('-s', getattr(self, 'usb_serial', None)) else '5038'
        return self.command_on(port, *args, timeout=timeout)

    def command_on(self, port, *args, timeout=30):
        result = subprocess.run([str(self.adb), '-P', port, *args], env=self.env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stdout.strip() or 'ADB command failed')
        return result.stdout.strip()

    def usb_devices(self):
        found = {}
        # An existing Android Studio server may already own USB. Do not kill
        # it or replace its keys; use that transport for initial setup only.
        for port in ('5038', '5037'):
            if port == '5037':
                try:
                    with socket.create_connection(('127.0.0.1', 5037), timeout=1):
                        pass
                except OSError:
                    continue
            for line in self.command_on(port, 'devices', '-l').splitlines():
                fields = line.split()
                if len(fields) < 2 or fields[1] not in ('device', 'unauthorized', 'offline'):
                    continue
                serial = fields[0]
                if ':' in serial or serial.startswith('emulator-'):
                    continue
                if serial not in found or fields[1] == 'device':
                    found[serial] = (port, fields[1], line)
        return found

    def select_usb(self, serial):
        devices = self.usb_devices()
        if serial not in devices:
            raise RuntimeError('Tonal USB connection is missing. Keep USB connected and finish Android startup.')
        port, state, _ = devices[serial]
        if state != 'device':
            raise RuntimeError('Unlock the Tonal and allow USB debugging, then retry step 5.')
        self.usb_serial, self.usb_port = serial, port

    def prepare_wireless(self, serial):
        self.select_usb(serial)
        for prop in ('ro.adb.secure', 'ro.secure'):
            if self.shell(serial, 'getprop', prop) != '1':
                raise RuntimeError('Authenticated ADB must be enabled before wireless setup.')
        if not self.shell(serial, 'pm', 'path', 'com.topjohnwu.magisk'):
            print('Installing bundled Magisk. Complete its additional setup on the Tonal, then retry step 5.', flush=True)
            self.command('-s', serial, 'install', '-r', str(self.adb.parent.parent / 'Magisk-v27.0.apk'), timeout=180)
            self.shell(serial, 'am', 'start', '-n', 'com.topjohnwu.magisk/.ui.MainActivity')
            raise RuntimeError('Finish Magisk additional setup on the Tonal, allow its reboot, then retry step 5.')
        print('If Magisk asks, grant Superuser access to Shell on the Tonal.', flush=True)
        if self.shell(serial, 'su -c "id -u"') != '0':
            raise RuntimeError('Magisk root access was not granted. Complete Magisk setup and grant Shell access, then retry.')
        script = self.state / 'tonal-wifi.sh'
        script.write_text(WIFI_BOOT_SCRIPT)
        remote = '/data/local/tmp/tonal-wifi-setup'
        self.shell(serial, 'mkdir', '-p', remote)
        self.command('-s', serial, 'push', str(self.home / 'tonal_keys/adbkey.pub'), remote + '/adbkey.pub')
        self.command('-s', serial, 'push', str(script), remote + '/wifi.sh')
        install = ('set -e; mkdir -p /data/adb/service.d /data/misc/adb; '
            'touch /data/misc/adb/adb_keys; '
            f'grep -qF "$(cat {remote}/adbkey.pub)" /data/misc/adb/adb_keys || cat {remote}/adbkey.pub >> /data/misc/adb/adb_keys; '
            'chown 1000:2000 /data/misc/adb/adb_keys; chmod 0640 /data/misc/adb/adb_keys; '
            'restorecon /data/misc/adb/adb_keys; '
            f'cp {remote}/wifi.sh /data/adb/service.d/tonal-wifi.sh; '
            'chown 0:0 /data/adb/service.d/tonal-wifi.sh; chmod 0700 /data/adb/service.d/tonal-wifi.sh; '
            'echo TONAL_WIFI_INSTALLED; '
            '(/system/bin/sh /data/adb/service.d/tonal-wifi.sh </dev/null >/data/adb/tonal-wifi.log 2>&1 &)')
        result = self.shell(serial, 'su -c ' + shlex.quote(install))
        if 'TONAL_WIFI_INSTALLED' not in result:
            raise RuntimeError('Could not install persistent Wi-Fi setup: ' + result)
        for _ in range(20):
            time.sleep(1)
            try:
                self.verify_auth(serial)
                return
            except RuntimeError:
                pass
        raise RuntimeError('Wi-Fi setup has not completed. Keep USB connected and retry step 5.')

    def shell(self, target, *args):
        return self.command('-s', target, 'shell', *args).strip()

    def identity(self, target):
        serial = self.shell(target, 'getprop', 'ro.serialno')
        android_id = self.shell(target, 'settings', 'get', 'secure', 'android_id')
        if not serial or serial.lower() in ('unknown', 'null') or not re.fullmatch('[0-9a-fA-F]{16}', android_id):
            raise RuntimeError('Could not identify this Tonal reliably. Finish Android startup and retry.')
        return {'serial': serial, 'android_id': android_id.lower()}

    def verify_auth(self, target):
        for prop in ('ro.adb.secure', 'ro.secure'):
            if self.shell(target, 'getprop', prop) != '1':
                raise RuntimeError('Authenticated ADB is not enabled. Use a newly patched boot image before wireless setup.')
        if self.shell(target, 'id', '-u') != '2000':
            raise RuntimeError('ADB is not running as the normal shell user. Wireless setup stopped.')
        for prop in ('persist.adb.tcp.port', 'service.adb.tcp.port'):
            if self.shell(target, 'getprop', prop) != '5555':
                raise RuntimeError('Persistent wireless ADB is not active. Reboot the newly patched Tonal and retry over USB.')

    @staticmethod
    def address(host):
        address = ipaddress.IPv4Address(host.strip())
        if not any(address in ipaddress.IPv4Network(network) for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
            raise ValueError('Enter the Tonal’s private LAN IPv4 address, such as 192.168.1.50.')
        return str(address)

    def establish(self, host, identity):
        target = self.address(host) + ':5555'
        print('Connecting to ' + target, flush=True)
        print(self.command('connect', target), flush=True)
        for _ in range(10):
            try:
                if self.command('-s', target, 'get-state') == 'device':
                    break
            except RuntimeError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Wireless ADB did not authorize. Keep USB attached and check Wi-Fi / the Tonal key.')
        if self.identity(target) != identity:
            self.command('disconnect', target)
            raise RuntimeError('That IP belongs to a different device. No app was installed.')
        self.verify_auth(target)
        return target

    def save(self, value):
        temporary = self.settings.with_suffix('.tmp')
        temporary.write_text(json.dumps(value, indent=2))
        temporary.replace(self.settings)

    def configure(self, serial):
        if ':' in serial or not serial:
            raise ValueError('Select the USB-connected Tonal for initial wireless setup.')
        self.verify_auth(serial)
        identity = self.identity(serial)
        output = self.shell(serial, 'ip', '-4', 'addr', 'show', 'wlan0')
        match = re.search(r'\binet (\d+\.\d+\.\d+\.\d+)/', output)
        if not match:
            raise RuntimeError('Connect the Tonal to your Wi-Fi network in Android Settings, then retry.')
        host = self.address(match[1])
        self.establish(host, identity)
        self.save({'host': host, 'identity': identity})
        print('Wireless connection verified and saved. Unplug USB, then use Reconnect Wi-Fi to test cable-free access.', flush=True)
        print('Network ADB is reapplied at boot. Test a power cycle before closing the Tonal.', flush=True)

    def connect(self, host=''):
        if not self.settings.exists():
            raise RuntimeError('Complete step 5 over USB once before using wireless installation.')
        saved = json.loads(self.settings.read_text())
        chosen = self.address(host or saved['host'])
        target = self.establish(chosen, saved['identity'])
        if chosen != saved['host']:
            saved['host'] = chosen; self.save(saved)
        print('Connected to the saved Tonal over Wi-Fi.', flush=True)
        return target

    def install(self, path):
        path = Path(path).resolve()
        if not path.is_file() or path.suffix.lower() != '.apk' or not zipfile.is_zipfile(path):
            raise ValueError('Choose a valid APK file.')
        target = self.connect()
        print('Installing ' + path.name + ' on ' + target + '…', flush=True)
        print(self.command('-s', target, 'install', '-r', str(path), timeout=600), flush=True)


def main(args):
    client = Wireless()
    command, *values = args
    if command == 'devices':
        devices = client.usb_devices()
        if not devices:
            raise RuntimeError('No USB-connected Tonal found. Finish startup and keep the internal USB data cable connected.')
        print('List of devices attached', flush=True)
        for port, state, line in devices.values():
            print(line, flush=True)
        if not any(state == 'device' for _, state, _ in devices.values()):
            raise RuntimeError('Allow USB debugging on the Tonal screen, then retry step 5.')
    elif command == 'setup':
        client.prepare_wireless(values[0])
        client.configure(values[0])
    elif command == 'connect':
        client.connect(values[0] if values else '')
    elif command == 'install':
        client.install(values[0])
    elif command == 'launcher':
        install_launcher(client)
    elif command == 'block-ota':
        set_ota_block(client)
    elif command == 'allow-ota':
        set_ota_block(client, False)
    else:
        raise ValueError('Unknown wireless action')
