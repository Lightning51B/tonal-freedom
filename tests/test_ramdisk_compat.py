"""Reject XZ streams modern host tools can decode but Magisk 27 cannot."""
import lzma
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_ramdisk import compatible_xz, verify_runtime


class CompatibilityTests(unittest.TestCase):
    original = (0o100750, 0, 0, b'original Android init' * 1024)

    def entries(self, compressed):
        return {'.backup/init.xz': (*self.original[:3], compressed)}

    def verify(self, entries):
        with patch('verify_ramdisk.Path.read_bytes', return_value=b'archive'), \
             patch('verify_ramdisk.read_newc', return_value={'init': self.original}):
            verify_runtime(entries, 'original.cpio')

    def test_rejects_bcj_even_when_host_decompression_succeeds(self):
        data = lzma.compress(self.original[3], check=lzma.CHECK_CRC32,
            filters=[{'id': lzma.FILTER_ARMTHUMB}, {'id': lzma.FILTER_LZMA2, 'dict_size': 1 << 23}])
        self.assertEqual(lzma.decompress(data), self.original[3])
        with self.assertRaisesRegex(ValueError, 'incompatible XZ'):
            self.verify(self.entries(data))

    def test_rejects_crc64(self):
        with self.assertRaisesRegex(ValueError, 'incompatible XZ'):
            self.verify(self.entries(lzma.compress(self.original[3])))

    def test_accepts_compatible_original(self):
        self.verify(self.entries(compatible_xz(self.original[3])))

    def test_rejects_wrong_original(self):
        with self.assertRaisesRegex(ValueError, 'exact original init'):
            self.verify(self.entries(compatible_xz(b'wrong init')))

    def test_rejects_changed_original_permissions(self):
        entries = self.entries(compatible_xz(self.original[3]))
        entries['.backup/init.xz'] = (0o100644, *entries['.backup/init.xz'][1:])
        with self.assertRaisesRegex(ValueError, 'exact original init'):
            self.verify(entries)


if __name__ == '__main__':
    unittest.main()
