"""Streaming legacy eMMC reads using the pinned DA's existing wire protocol."""
from struct import pack, unpack


def read_emmc(legacy, area, offset, length, serial=None):
    actual, partition = legacy.daconfig.legacy_storage.partitiontype_and_size(parttype=area, length=length)
    if actual != length or length <= 0:
        raise ValueError('Storage read exceeds selected area')
    packet_size = 1024 * 1024
    # Serial writes already handle partial OS writes. Responses pace each command;
    # the upstream flush + 5ms delay on every write is unnecessary here.
    def write(data):
        if serial is not None:
            if serial.write(data) != len(data):
                raise IOError('Short serial write during storage read')
        elif not legacy.usbwrite(data):
            raise IOError('Failed USB write during storage read')
    def read(size):
        data = legacy.usbread(size, w_max_packet_size=size)
        if len(data) != size:
            raise IOError(f'Short storage packet: expected {size}, received {len(data)}')
        return data
    def ack():
        if read(1) != legacy.Rsp.ACK:
            raise IOError('Storage command was not acknowledged')
    write(legacy.Cmd.SDMMC_SWITCH_PART_CMD); ack()
    write(pack('B', partition)); ack()
    write(legacy.Cmd.READ_CMD)
    write(b'\x0c'); write(b'\x02')
    write(pack('>Q', offset)); write(pack('>Q', length)); write(pack('>I', packet_size))
    ack()
    result = bytearray()
    while len(result) < length:
        packet = read(min(packet_size, length - len(result)))
        checksum = unpack('>H', read(2))[0]
        if (sum(packet) & 0xffff) != checksum:
            raise IOError('Storage packet checksum mismatch')
        result.extend(packet)
        write(legacy.Rsp.ACK)
    return bytes(result)
