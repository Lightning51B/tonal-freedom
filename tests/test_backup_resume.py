import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'macos'))
import device_workflow as w

class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.data=bytes(range(256))*12
        self.calls=[]
        self.d=SimpleNamespace(identity={'cid':'test'},layout=[{'name':'boot','offset':0,'size':512}],
            areas={'user':3072},boot={'offset':0,'size':512},description='Test')
        def read(area,offset,size):self.calls.append(offset);return self.data[offset:offset+size]
        self.d.read=read
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(w,'CHUNK',1024))
    def interrupt(self):
        original=self.d.read
        def read(area,offset,size):
            if offset>=1024:raise OSError('disconnect')
            return original(area,offset,size)
        self.d.read=read
        with self.assertRaises(OSError):w.backup(self.d,self.folder)
        self.d.read=original;self.calls.clear()
    def test_resume_verified_prefix_and_discard_uncheckpointed_tail(self):
        self.interrupt()
        with (self.folder/'user.partial').open('ab') as f:f.write(b'unverified tail')
        w.backup(self.d,self.folder)
        self.assertEqual(self.calls,[1024,2048])
        self.assertEqual((self.folder/'user.bin').read_bytes(),self.data)
        self.assertTrue(w.validate_backup(self.folder)['complete'])
    def test_corrupt_prefix_rejected_before_any_device_reads(self):
        self.interrupt();(self.folder/'user.partial').write_bytes(b'x'*1024)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):w.backup(self.d,self.folder)
        self.assertEqual(self.calls,[])
    def test_wrong_device_rejected(self):
        self.interrupt();self.d.identity={'cid':'different'}
        with self.assertRaisesRegex(ValueError,'identity'):w.backup(self.d,self.folder)
        self.assertEqual(self.calls,[])
    def test_missing_checkpoint_data_rejected(self):
        self.interrupt();(self.folder/'user.partial').unlink()
        with self.assertRaisesRegex(ValueError,'missing'):w.backup(self.d,self.folder)
    def test_old_partial_cannot_be_resumed_blindly(self):
        (self.folder/'user.partial').write_bytes(b'old')
        with self.assertRaisesRegex(ValueError,'no resume checkpoints'):w.backup(self.d,self.folder)
    def test_resume_after_area_rename_before_manifest(self):
        w.backup(self.d,self.folder)
        (self.folder/'backup.json').unlink();self.calls.clear()
        w.backup(self.d,self.folder)
        self.assertEqual(self.calls,[])
        self.assertTrue(w.validate_backup(self.folder)['complete'])
