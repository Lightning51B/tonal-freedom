import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'macos'))
from legacy_read import read_emmc

class StreamingTests(unittest.TestCase):
    def setup_stream(self, packets):
        replies = [b'Z'] * 3
        for packet in packets:
            replies.extend([packet, (sum(packet)&65535).to_bytes(2,'big')])
        legacy = NS(daconfig=NS(legacy_storage=NS(partitiontype_and_size=lambda parttype,length:(length,8))),
                    Cmd=NS(SDMMC_SWITCH_PART_CMD=b'\x60',READ_CMD=b'\xd6'),Rsp=NS(ACK=b'Z'),
                    usbread=Mock(side_effect=replies),usbwrite=Mock(return_value=True))
        serial=NS(write=Mock(side_effect=lambda data:len(data)))
        return legacy,serial

    def test_multiple_packets_and_short_final_packet(self):
        packets=[b'a'*1048576,b'b'*1048576,b'c'*512]
        legacy,serial=self.setup_stream(packets)
        result=read_emmc(legacy,'user',4096,sum(map(len,packets)),serial)
        self.assertEqual(result,b''.join(packets))
        self.assertEqual(sum(c.args[0]==b'\xd6' for c in serial.write.call_args_list),1)
        legacy.usbwrite.assert_not_called()
        self.assertEqual([c.args[0] for c in legacy.usbread.call_args_list], [1,1,1,1048576,2,1048576,2,512,2])

    def test_checksum_mismatch_stops_without_acknowledging_packet(self):
        legacy,serial=self.setup_stream([b'x'*512])
        legacy.usbread.side_effect=[b'Z']*3+[b'x'*512,b'\x00\x01']
        with self.assertRaisesRegex(IOError,'checksum'):read_emmc(legacy,'user',0,512,serial)
        self.assertNotEqual(serial.write.call_args.args[0],b'Z')

    def test_short_read_is_rejected(self):
        legacy,serial=self.setup_stream([b'x'])
        with self.assertRaisesRegex(IOError,'Short storage packet'):read_emmc(legacy,'user',0,512,serial)

    def test_rejected_command_stops(self):
        legacy,serial=self.setup_stream([]);legacy.usbread.side_effect=[b'X']
        with self.assertRaisesRegex(IOError,'acknowledged'):read_emmc(legacy,'user',0,512,serial)
        self.assertEqual(serial.write.call_count,1)
