"""Build-time audit: reject external symlinks and non-system absolute dylibs."""
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
count = 0
for path in root.rglob('*'):
    if path.is_symlink():
        assert path.resolve().is_relative_to(root), f'External symlink: {path}'
        assert path.exists(), f'Broken symlink: {path}'
    elif path.is_file():
        with path.open('rb') as stream:
            magic = stream.read(4)
        if magic not in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'):
            continue
        count += 1
        output = subprocess.check_output(['/usr/bin/otool', '-L', str(path)], text=True)
        for line in output.splitlines():
            if not line.startswith('\t'):
                continue
            library = line.strip().split(' (compatibility')[0]
            assert not library.startswith('/') or library.startswith(('/usr/lib/', '/System/Library/')), (path, library)
assert count > 10, 'Unexpectedly few native components'
assert not (root / 'Contents/Resources/repository-path.txt').exists()
print(f'PASS: {count} native files audited; no external symlinks or non-system absolute library dependencies.')
