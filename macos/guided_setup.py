"""Verified, repeatable post-boot actions for the guided Mac app."""
import json
from pathlib import Path
import re
import shlex

OTA_PACKAGES = ('com.innocomm.otaupdate', 'com.tonal.apkupdater')
OTA_SERVICE = '/data/adb/service.d/tonal-block-ota.sh'


def progress(message, percent):
    print('TONAL_EVENT ' + json.dumps(dict(kind='progress', message=message, percent=percent)), flush=True)


def root(client, target, command):
    return client.shell(target, 'su -c ' + shlex.quote(command))


def require_root(client, target):
    progress('Checking Magisk root access — grant Shell access on the Tonal if prompted', 15)
    if root(client, target, 'id -u') != '0':
        raise RuntimeError('Grant Shell superuser access in Magisk, then retry this step.')


def package_state(client, target, package):
    output = client.shell(target, 'dumpsys', 'package', package)
    match = re.search(r'User 0:.*?enabled=(\d+)', output)
    if not match:
        raise RuntimeError('Cannot verify installed package: ' + package)
    return int(match[1])


def install_launcher(client):
    progress('Connecting to the saved Tonal over Wi-Fi', 5)
    target = client.connect()
    apk = client.adb.parent.parent / 'textlauncher.apk'
    if not apk.is_file():
        raise RuntimeError('The bundled launcher APK is missing. Reinstall Tonal Freedom.')
    progress('Installing Text Launcher', 30)
    result = client.command('-s', target, 'install', '-r', str(apk), timeout=180)
    print(result, flush=True)
    if not any(line.strip() == 'Success' for line in result.splitlines()):
        raise RuntimeError('Android did not confirm launcher installation.')
    if not client.shell(target, 'pm', 'path', 'ademar.textlauncher').startswith('package:'):
        raise RuntimeError('Launcher installation could not be verified.')
    progress('Opening Text Launcher on the Tonal', 75)
    client.shell(target, 'am', 'start', '-W', '-n', 'ademar.textlauncher/.Activity')
    activities = client.shell(target, 'dumpsys', 'activity', 'activities')
    if not any('mResumedActivity:' in line and 'ademar.textlauncher/' in line for line in activities.splitlines()):
        raise RuntimeError('Launcher is installed, but Android did not leave it in the foreground. Check the Tonal screen.')
    progress('Text Launcher installed and open — tap an app on the Tonal', 100)


def set_ota_block(client, blocked=True):
    progress('Connecting to the saved Tonal over Wi-Fi', 5)
    target = client.connect()
    require_root(client, target)
    folder = client.state / 'OTA'; folder.mkdir(exist_ok=True)
    states = {pkg: package_state(client, target, pkg) for pkg in OTA_PACKAGES}
    before = folder / 'guided-original-states.json'
    if blocked and not before.exists():
        before.write_text(json.dumps(states, indent=2) + '\n')
    progress('Disabling system and app OTA updates' if blocked else 'Allowing system and app OTA updates', 40)
    if blocked:
        script = '#!/system/bin/sh\n# Tonal Freedom: OS and app OTA block; motor firmware client unchanged.\n'
        for pkg in OTA_PACKAGES:
            script += f'pm disable-user --user 0 {pkg}\nam force-stop --user 0 {pkg}\n'
        local = folder / 'tonal-block-ota.sh'; local.write_text(script)
        client.command('-s', target, 'push', str(local), '/data/local/tmp/tonal-block-ota.sh')
        root(client, target, 'mkdir -p /data/adb/service.d; '
             f'cp /data/local/tmp/tonal-block-ota.sh {OTA_SERVICE}; '
             f'chown 0:0 {OTA_SERVICE}; chmod 0700 {OTA_SERVICE}; /system/bin/sh {OTA_SERVICE}')
        if root(client, target, f'cat {OTA_SERVICE}') != script.strip():
            raise RuntimeError('OTA startup block was not saved correctly.')
        expected = 3
    else:
        root(client, target, f'rm -f {OTA_SERVICE}; ' + '; '.join(f'pm default-state --user 0 {pkg}' for pkg in OTA_PACKAGES))
        if root(client, target, f'if [ -e {OTA_SERVICE} ]; then echo present; else echo absent; fi') != 'absent':
            raise RuntimeError('OTA startup block could not be removed.')
        expected = 0
    progress('Verifying both updater settings', 85)
    for pkg in OTA_PACKAGES:
        if package_state(client, target, pkg) != expected:
            raise RuntimeError('OTA setting did not persist for ' + pkg)
    (folder / 'guided-status.json').write_text(json.dumps(dict(blocked=blocked, packages=list(OTA_PACKAGES), startup_service=OTA_SERVICE), indent=2) + '\n')
    progress('System and app OTA updates blocked; startup block verified' if blocked else 'System and app OTA updates allowed; startup block removed', 100)
