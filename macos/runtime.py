"""Frozen Python/Qt runtime: no external Python installation or source checkout."""
import os
import io
import lzma  # Bundle the patcher's Magisk 27 compatible compressor in frozen Python.
from pathlib import Path
import runpy
import sys


def main():
    command, *args = sys.argv[1:]
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    # PyUSB's system library search is not used: choose our bundled library.
    import usb.backend.libusb1
    get_backend = usb.backend.libusb1.get_backend
    usb.backend.libusb1.get_backend = lambda find_library=None: get_backend(
        find_library=lambda _: str(root / 'libusb-1.0.0.dylib'))
    if command == 'python':
        sys.argv = args
        if args[0] == '-':
            exec(compile(sys.stdin.read(), '<stdin>', 'exec'), {'__name__': '__main__'})
        else:
            runpy.run_path(args[0], run_name='__main__')
        return
    # mtkclient detaches/replaces its streams. Give it duplicates so frozen
    # runtime shutdown hooks can still flush the original standard streams.
    sys.stdout = io.TextIOWrapper(os.fdopen(os.dup(1), 'wb'), encoding='utf-8', line_buffering=True)
    sys.stderr = io.TextIOWrapper(os.fdopen(os.dup(2), 'wb'), encoding='utf-8', line_buffering=True)
    import usb_handshake
    usb_handshake.install()
    if command == 'wireless':
        import wireless
        try:
            wireless.main(args)
        except Exception as error:
            raise SystemExit(str(error))
        return
    if command == 'device':
        import device_workflow
        try:
            device_workflow.main(args)
        except Exception as error:
            device_workflow.event('status', message=str(error))
            raise SystemExit(str(error))
        return
    import mtk_gui
    from PySide6.QtWidgets import QApplication
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
    if command == 'check':
        assert Ks(KS_ARCH_ARM, KS_MODE_ARM).asm('nop')[1] == 1
        assert usb.backend.libusb1.get_backend() is not None, 'Bundled libusb unavailable'
        from mtkclient.config.payloads import PathConfig
        paths = PathConfig()
        for directory in (paths.get_loader_path(), paths.get_payloads_path(), paths.get_images_path()):
            assert Path(directory).is_dir(), directory
            assert any(Path(directory).iterdir()), directory
        app = QApplication(['tonal-check', '-platform', 'offscreen'])
        from PySide6.QtWidgets import QMainWindow
        from mtkclient.gui.main_gui import Ui_MainWindow
        window = QMainWindow()
        ui = Ui_MainWindow()
        ui.setupUi(window)
        print('PASS: bundled Python, Qt, mtkclient assets, assembler and USB library.')
        return
    if command == 'mtk':
        # Logs and connection state must never be written inside the signed app.
        work = Path.home() / 'Library/Application Support/Tonal Freedom/mtkclient'
        work.mkdir(parents=True, exist_ok=True)
        os.chdir(work)
        sys.argv = ['mtk_gui.py']
        mtk_gui.main()
        return
    raise SystemExit('Unknown runtime command')


if __name__ == '__main__':
    main()
