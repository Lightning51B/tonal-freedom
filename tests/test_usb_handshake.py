import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'macos'))
from usb_handshake import run_handshake, run_serial_handshake, SoftwareTimeoutSerial, serial_read_with_default_timeout


class Endpoint:
    wMaxPacketSize = 512
    def __init__(self, banner=b'', bad=False):
        self.queued = []; self.writes = []; self.read_sizes = []
        self.banner = banner; self.bad = bad
    def write(self, data, timeout):
        self.writes.append(data)
        self.queued.append(self.banner + bytes([data[0] ^ (0 if self.bad else 255)]))
        self.banner = b''
        return len(data)
    def read(self, size, timeout):
        self.read_sizes.append(size)
        if self.queued:
            data = self.queued.pop(0)
            if size < len(data): raise OSError(84, 'Overflow')
            return data
        raise TimeoutError('USB timeout')


def port(endpoint):
    return SimpleNamespace(cdc=SimpleNamespace(EP_IN=endpoint, EP_OUT=endpoint,
                           set_line_coding=Mock(), setcontrollinestate=Mock()), info=Mock())


class HandshakeTests(unittest.TestCase):
    def test_startup_banner_does_not_overflow_or_desync(self):
        endpoint = Endpoint(b'READY')
        self.assertTrue(run_handshake(port(endpoint)))
        self.assertEqual(endpoint.writes, [bytes([x]) for x in b'\xa0\x0a\x50\x05'])
        self.assertEqual(endpoint.read_sizes, [512]*4)

    def test_bare_echo_handshake(self):
        endpoint = Endpoint()
        self.assertTrue(run_handshake(port(endpoint)))

    def test_wrong_echo_never_succeeds(self):
        self.assertFalse(run_handshake(port(Endpoint(bad=True)), retries=2))

    def test_short_write_never_succeeds(self):
        endpoint = Endpoint(); endpoint.write = lambda *a, **k: 0
        self.assertFalse(run_handshake(port(endpoint), retries=1))

    def test_pipe_error_is_reported_and_bounded(self):
        endpoint = Endpoint()
        endpoint.read = Mock(side_effect=OSError(32, 'Pipe error'))
        connection = port(endpoint)
        self.assertFalse(run_handshake(connection, retries=2))
        self.assertEqual(len(endpoint.writes), 2)
        self.assertTrue(any('Pipe error' in str(call) for call in connection.info.call_args_list))


class SerialHandshakeTests(unittest.TestCase):
    def connection(self, replies):
        serial = Mock()
        serial.read.side_effect = replies
        serial.write.side_effect = lambda data: len(data)
        return SimpleNamespace(cdc=SimpleNamespace(device=serial), info=Mock())

    def test_observed_ready_then_retry_then_four_echoes(self):
        p = self.connection([bytes([c]) for c in b'READY'] +
                            [b'', b'\x5f', b'\xf5', b'\xaf', b'\xfa'])
        self.assertTrue(run_serial_handshake(p))
        self.assertEqual([c.args[0] for c in p.cdc.device.write.call_args_list],
                         [b'\xa0', b'\xa0', b'\x0a', b'\x50', b'\x05'])
        self.assertEqual(p.cdc.device.baudrate, 921600)

    def test_wrong_intermediate_echo_stops(self):
        p = self.connection([b'\x5f', b'\x00'])
        self.assertFalse(run_serial_handshake(p))
        self.assertEqual(p.cdc.device.write.call_count, 2)

    def test_missing_echo_is_bounded(self):
        p = self.connection([b''])
        with patch('usb_handshake.time.monotonic', side_effect=[0, 0, 4]):
            self.assertFalse(run_serial_handshake(p))

    def test_short_serial_write_fails(self):
        p = self.connection([])
        p.cdc.device.write.side_effect = lambda data: 0
        self.assertFalse(run_serial_handshake(p))
        p.cdc.device.read.assert_not_called()


class SoftwareTimeoutTests(unittest.TestCase):
    def test_default_ack_read_uses_transport_timeout(self):
        original = Mock(return_value=b'\x5a')
        connection = SimpleNamespace(timeout=1000)
        self.assertEqual(serial_read_with_default_timeout(original, connection, 1), b'\x5a')
        self.assertEqual(original.call_args.kwargs['timeout'], 1)
        serial_read_with_default_timeout(original, connection, 1, maxtimeout=250)
        self.assertEqual(original.call_args.kwargs['maxtimeout'], 250)
        self.assertEqual(original.call_args.kwargs['timeout'], 0)
        serial_read_with_default_timeout(original, connection, 1, timeout=.5)
        self.assertEqual(original.call_args.kwargs['timeout'], .5)

    def test_timeout_updates_do_not_reconfigure_open_port(self):
        class Connection:
            _timeout = 500
            _write_timeout = None
            @property
            def timeout(self): return self._timeout
            @timeout.setter
            def timeout(self, value): raise AssertionError('Unexpected termios reconfiguration')
            def read(self, count): return self._timeout, count
        original = Connection()
        connection = SoftwareTimeoutSerial(original)
        connection.timeout = .02
        connection.write_timeout = .5
        self.assertEqual(connection.read(4), (.02, 4))
        self.assertEqual(original._write_timeout, .5)
        connection.baudrate = 921600
        self.assertEqual(original.baudrate, 921600)
        for value in (-1, 'invalid'):
            with self.assertRaises(ValueError): connection.timeout = value
        self.assertEqual(connection.timeout, .02)


if __name__ == '__main__': unittest.main()
