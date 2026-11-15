"""Bounded, packet-aligned direct USB reads after serial DA initialization."""
import time

class BulkTransport:
    def __init__(self, usb):
        self.usb = usb
        self.pending = bytearray()
    def write(self, data):
        count = self.usb.EP_OUT.write(data, timeout=2000)
        if count != len(data): raise IOError('Short direct USB write')
        return count
    def read(self, count, **kwargs):
        result = bytearray()
        deadline = time.monotonic() + 5
        packet = int(self.usb.EP_IN.wMaxPacketSize)
        while len(result) < count:
            if self.pending:
                take = min(len(self.pending), count - len(result))
                result.extend(self.pending[:take]); del self.pending[:take]
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise TimeoutError('Direct USB read timed out')
            size = min(1024 * 1024, ((count - len(result) + packet - 1) // packet) * packet)
            self.pending.extend(self.usb.EP_IN.read(size, timeout=max(1, int(remaining * 1000))))
        return bytes(result)
    def close(self):
        self.usb.close(reset=False)
