import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'macos'))
from bulk_read import BulkTransport

class BulkTests(unittest.TestCase):
    def test_packet_alignment_and_buffered_trailing_bytes(self):
        endpoint=NS(wMaxPacketSize=512,read=Mock(side_effect=[b'Zabcd',b'x'*512]))
        transport=BulkTransport(NS(EP_IN=endpoint))
        self.assertEqual(transport.read(1),b'Z')
        self.assertEqual(transport.read(4),b'abcd')
        self.assertEqual(transport.read(512),b'x'*512)
        self.assertEqual([c.args[0] for c in endpoint.read.call_args_list],[512,512])
    def test_large_read_uses_large_transfers(self):
        endpoint=NS(wMaxPacketSize=512,read=Mock(side_effect=[b'x'*1048576,b'y'*512]))
        transport=BulkTransport(NS(EP_IN=endpoint))
        self.assertEqual(len(transport.read(1049088)),1049088)
        self.assertEqual([c.args[0] for c in endpoint.read.call_args_list],[1048576,512])
    def test_empty_reads_have_deadline(self):
        endpoint=NS(wMaxPacketSize=512,read=Mock(return_value=b''))
        transport=BulkTransport(NS(EP_IN=endpoint))
        with patch('bulk_read.time.monotonic',side_effect=[0,0,6]):
            with self.assertRaises(TimeoutError):transport.read(1)
    def test_short_write_stops(self):
        transport=BulkTransport(NS(EP_OUT=NS(write=Mock(return_value=0))))
        with self.assertRaisesRegex(IOError,'Short'):transport.write(b'Z')
