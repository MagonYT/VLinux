#!/usr/bin/env python3
"""Prepare pinned upstream checkouts and apply the VLinux source patches."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(folder, *args):
    return subprocess.run(['git', '-C', str(folder), *args], check=True,
                          stdout=subprocess.PIPE, text=True).stdout.strip()


def verify(folder, item):
    if git(folder, 'rev-parse', 'HEAD') != item['revision']:
        raise ValueError('Different base revision in ' + str(folder))
    for name, expected in item['files_sha256'].items():
        path = folder / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise ValueError('Source differs: ' + str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', choices=['all', 'm1n1', 'linux-asahi'], default='all')
    parser.add_argument('--directory', type=Path, default=ROOT / 'src')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'sources.lock.json').read_text())
    names = list(lock['components']) if args.component == 'all' else [args.component]
    for name in names:
        item = lock['components'][name]
        patch = ROOT / item['patch']
        if digest(patch) != item['patch_sha256']:
            raise ValueError('Patch differs from sources.lock.json: ' + str(patch))
        folder = args.directory.resolve() / name
        if args.verify_only or folder.exists():
            # Existing work is never reset, overwritten, or patched again.
            verify(folder, item)
        else:
            folder.mkdir(parents=True)
            git(folder, 'init')
            git(folder, 'remote', 'add', 'upstream', item['url'])
            git(folder, 'fetch', '--depth', '1', 'upstream', item['revision'])
            git(folder, 'checkout', '--detach', 'FETCH_HEAD')
            git(folder, 'apply', '--check', str(patch))
            git(folder, 'apply', str(patch))
            git(folder, 'submodule', 'update', '--init', '--recursive')
            verify(folder, item)
        print(f'{name}: pinned base and {len(item["files_sha256"])} source files verified', flush=True)


if __name__ == '__main__':
    main()
