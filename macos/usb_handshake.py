"""Packet-sized USB reads for the MediaTek bootloader's byte-wise handshake."""
import time
import sys


class SoftwareTimeoutSerial:
    """POSIX Serial.read uses _timeout in select(), not terminal VTIME.

    mtkclient changes timeout before every read. With a custom baud rate,
    PySerial also reapplies termios settings, which can block in Apple's CDC
    driver during DA upload. Keep those changes in the software timeout only.
    This wrapper is installed only for macOS's default select-based Serial.
    """
    def __init__(self, connection):
        object.__setattr__(self, '_connection', connection)

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def __setattr__(self, name, value):
        if name in ('timeout', 'write_timeout'):
            if value is not None:
                try:
                    valid = value >= 0
                except TypeError:
                    valid = False
                if not valid:
                    raise ValueError(f'Invalid serial timeout: {value!r}')
            setattr(self._connection, '_' + name, value)
        else:
            setattr(self._connection, name, value)


def serial_read_with_default_timeout(original_read, connection, resplen=None,
                                     maxtimeout=0, timeout=0, w_max_packet_size=None):
    # The upstream serial default becomes 20ms, including one-byte DA ACKs.
    # Use the transport's configured millisecond timeout when none was supplied.
    if timeout == 0 and maxtimeout == 0:
        timeout = connection.timeout / 1000
    return original_read(connection, resplen=resplen, maxtimeout=maxtimeout,
                         timeout=timeout, w_max_packet_size=w_max_packet_size)


def run_handshake(port, retries=5):
    incoming = port.cdc.EP_IN
    outgoing = port.cdc.EP_OUT
    packet_size = int(incoming.wMaxPacketSize)
    if packet_size <= 0:
        raise ValueError('Invalid USB IN packet size')
    port.cdc.set_line_coding(921600, 0, 8, 1)
    port.cdc.setcontrollinestate(rts=True)
    for attempt in range(retries):
        pending = bytearray()
        try:
            # Send each byte once. An extra unconsumed A0 can desynchronize echoes.
            for index, command in enumerate(b'\xa0\x0a\x50\x05'):
                if outgoing.write(bytes([command]), timeout=500) != 1:
                    raise ValueError('Short USB handshake write')
                deadline = time.monotonic() + .5
                expected = command ^ 0xff
                while True:
                    if not pending:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError('No handshake echo before deadline')
                        # A byte-sized request overflows on macOS when preloader
                        # sends a larger packet (e.g. its READY banner). Always
                        # receive one full endpoint packet and buffer its bytes.
                        pending.extend(incoming.read(packet_size, timeout=max(1, int(remaining * 1000))))
                        if not pending:
                            continue
                    echo = pending.pop(0)
                    if echo == expected:
                        break
                    if index != 0:
                        raise ValueError(f'Handshake echo {echo:02x}, expected {expected:02x}')
                    # Before the first echo, preloader may send a startup banner.
                    if time.monotonic() >= deadline:
                        raise TimeoutError('No initial handshake echo')
            if pending:
                raise ValueError(f'Unexpected trailing handshake bytes: {pending.hex()}')
            port.info('Device detected: USB handshake complete')
            return True
        except Exception as error:
            port.info(f'USB handshake attempt {attempt + 1} failed: {error}')
            # Drop stale responses before retrying; do not carry a partial echo
            # from a failed attempt into a new handshake.
            try:
                incoming.read(packet_size, timeout=50)
            except Exception:
                pass
    port.info('USB handshake failed after retries')
    return False


def run_serial_handshake(port):
    """Use macOS's CDC driver; retry A0 after the preloader READY banner."""
    connection = port.cdc.device
    connection.baudrate = 921600
    connection.timeout = .02
    connection.write_timeout = .5
    commands = b'\xa0\x0a\x50\x05'
    index = 0
    deadline = time.monotonic() + 3
    try:
        if connection.write(commands[:1]) != 1:
            return False
        while time.monotonic() < deadline:
            data = connection.read(1)
            if data:
                if data[0] == (commands[index] ^ 255):
                    index += 1
                    if index == len(commands):
                        port.info('Device detected: native serial handshake complete')
                        return True
                    if connection.write(commands[index:index + 1]) != 1:
                        return False
                elif index:
                    port.info(f'Unexpected serial handshake echo: {data.hex()}')
                    return False
            elif index == 0:
                if connection.write(commands[:1]) != 1:
                    return False
    except Exception as error:
        port.info(f'Native serial handshake failed: {error}')
    return False


def install():
    # Patch the class so mtkclient-created reconnect/bypass instances inherit it.
    from mtkclient.Library.Port import Port
    Port.run_handshake = run_handshake
    Port.run_serial_handshake = run_serial_handshake
    # Upstream discards this constructor argument on Port, but reuses it when
    # creating a new Mtk instance during reconnect/bypass.
    if not getattr(Port, '_tonal_serial_preserved', False):
        original_init = Port.__init__
        def initialize(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            if getattr(self.cdc, 'is_serial', False):
                self.serialportname = self.cdc.portname
        Port.__init__ = initialize
        Port._tonal_serial_preserved = True
    if sys.platform == 'darwin':
        from mtkclient.Library.Connection.seriallib import SerialClass
        if not getattr(SerialClass, '_tonal_software_timeout', False):
            original_connect = SerialClass.connect
            def connect(self, *args, **kwargs):
                result = original_connect(self, *args, **kwargs)
                if result:
                    self.device = SoftwareTimeoutSerial(self.device)
                return result
            SerialClass.connect = connect
            original_read = SerialClass.usbread
            def read(self, resplen=None, maxtimeout=0, timeout=0, w_max_packet_size=None):
                return serial_read_with_default_timeout(original_read, self, resplen,
                                                        maxtimeout, timeout, w_max_packet_size)
            SerialClass.usbread = read
            SerialClass._tonal_software_timeout = True
