"""Durable per-chunk checkpoints; only verified prefixes can be resumed."""
import hashlib
import json
import os
from pathlib import Path


def checkpoint(path, state):
    temp = path.with_suffix('.tmp')
    with temp.open('w') as stream:
        json.dump(state, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def prepare(folder, device, chunk_size, notify):
    path = folder / 'resume.json'
    expected = dict(version=1, identity=device.identity, layout=device.layout,
                    areas=device.areas, chunk_size=chunk_size)
    if not path.exists():
        if any(folder.glob('*.partial')) or any(folder.glob('*.bin')):
            raise ValueError('This older partial backup has no resume checkpoints. Use a new backup folder.')
        state = dict(expected, chunks={area: [] for area in device.areas})
        checkpoint(path, state)
        return state
    state = json.loads(path.read_text())
    if any(state.get(key) != value for key, value in expected.items()):
        raise ValueError('Resume device identity, partition layout, or storage size does not match')
    if set(state.get('chunks', {})) != set(device.areas):
        raise ValueError('Invalid resume areas')
    for area, size in device.areas.items():
        partial, complete = folder / (area + '.partial'), folder / (area + '.bin')
        if partial.exists() and complete.exists():
            raise ValueError('Ambiguous resume files')
        data = complete if complete.exists() else partial
        records = state['chunks'][area]
        maximum = (size + chunk_size - 1) // chunk_size
        if len(records) > maximum:
            raise ValueError('Resume has too many chunks')
        if not data.exists():
            if records: raise ValueError('Resume data is missing')
            continue
        notify('status', message='Verifying saved ' + area + ' before resuming')
        with data.open('rb') as stream:
            for index, checksum in enumerate(records):
                count = min(chunk_size, size - index * chunk_size)
                block = stream.read(count)
                if len(block) != count or hashlib.sha256(block).hexdigest() != checksum:
                    raise ValueError('Resume chunk hash mismatch; saved data was changed or damaged')
        verified = min(len(records) * chunk_size, size)
        if complete.exists() and (verified != size or data.stat().st_size != size):
            raise ValueError('Completed resume area has an invalid size')
        if partial.exists():
            # Bytes past the last durable checkpoint are unverified work only.
            with partial.open('r+b') as stream:
                stream.truncate(verified)
    return state
