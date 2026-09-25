#!/usr/bin/env python3
"""Read-only SEP/Touch ID inventory from macOS registry metadata.

This lists known device paths, compatible strings and driver class names. It
never opens a driver user client, sends a mailbox command, or reads biometric
storage. Unknown properties and identifiers are discarded, not redacted later.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import plistlib
import struct
import subprocess


NODES = {
    '/arm-io': {'arm-io,t8140'},
    '/arm-io/sep': {'iop-sep,ascwrap-v6'},
    '/arm-io/sep/iop-sep-nub': {'iop-nub,sep'},
    '/arm-io/spi2': {'spi-1,spimc'},
    '/arm-io/spi2/mesa': {'biosensor,mesa'},
}
DRIVERS = frozenset({
    'AppleSEPManager', 'AppleSEPDeviceService', 'AppleSEPXARTService',
    'AppleMesaSEPDriver', 'AppleMesaShim', 'AppleSandDollar',
    'AppleBiometricSensor', 'AppleBiometricServices', 'AppleCredentialManager',
})
LIVE_CLASSES = ('AppleSEPManager', 'AppleBiometricSensor', 'AppleCredentialManager')


def walk(tree, path=''):
    if isinstance(tree, list):
        for item in tree:
            yield from walk(item, path)
    elif isinstance(tree, dict):
        name = tree.get('IORegistryEntryName')
        # A name containing slash cannot impersonate an allowlisted path.
        name = name if isinstance(name, str) and '/' not in name else '?'
        here = path + '/' + name
        yield here, tree
        children = tree.get('IORegistryEntryChildren', [])
        if isinstance(children, list):
            for item in children:
                yield from walk(item, here)


def decode_records(value, width):
    if not isinstance(value, bytes) or not value or len(value) > 1024 or len(value) % (width*8):
        return []
    return list(struct.iter_unpack('<' + 'Q'*width, value))


def canonical_path(path):
    for prefix in ('/Root/device-tree', '/device-tree'):
        if path.startswith(prefix + '/'):
            return path[len(prefix):]
    return None


def compatible(node, allowed):
    value = node.get('compatible', b'')
    if not isinstance(value, bytes) or len(value) > 256:
        return []
    return sorted(allowed.intersection(value.decode('ascii', errors='replace').split('\0')))


def scan(adt, service_trees=()):
    indexed = {}
    for path, node in walk(adt):
        key = canonical_path(path)
        if key in NODES:
            if key in indexed:
                raise ValueError('Duplicate hardware node')
            indexed[key] = node
    ranges = decode_records(indexed.get('/arm-io', {}).get('ranges'), 3)
    devices = []
    for path, allowed in NODES.items():
        if path not in indexed:
            continue
        node = indexed[path]
        row = {'path': path, 'compatible': compatible(node, allowed)}
        # These reg properties are address/size pairs under arm-io. The Mesa
        # SPI child's 1+7-cell reg has a different format; do not interpret it.
        if path in ('/arm-io/sep', '/arm-io/spi2'):
            row['resources'] = []
            for address, size in decode_records(node.get('reg'), 2):
                if not size or size > 0x10000000 or address + size > 2**64:
                    continue
                matches = [parent + address - child for child, parent, length in ranges
                           if child <= address and size <= length and
                           address-child <= length-size and parent + address-child+size <= 2**64]
                row['resources'].append({'bus_address': hex(address), 'bytes': size,
                                         'physical_address': hex(matches[0]) if len(matches) == 1 else None})
        if path == '/arm-io/spi2/mesa':
            value = node.get('spi-frequency')
            if isinstance(value, bytes) and len(value) == 4:
                frequency = int.from_bytes(value, 'little')
                if 0 < frequency <= 100_000_000:
                    row['spi_frequency_hz'] = frequency
        devices.append(row)
    present = set()
    for tree in service_trees:
        for _, node in walk(tree):
            for key in ('IOClass', 'IOObjectClass'):
                value = node.get(key)
                if isinstance(value, str) and value in DRIVERS:
                    present.add(value)
    return {
        'schema_version': 1,
        'scope': 'Registry metadata only; no driver user clients, mailbox messages or biometric data.',
        't8140_identified': any(d['path'] == '/arm-io' and 'arm-io,t8140' in d['compatible'] for d in devices),
        'devices': devices,
        'macos_driver_classes': sorted(present),
        'service_inventory_collected': bool(service_trees),
        'linux_enrollment_tested': False,
        'sep_bypass_demonstrated': False,
        'interpretation': 'A present macOS device or driver does not establish Linux support or a usable biometric protocol.',
    }


def load(data):
    if len(data) > 64*1024*1024:
        raise ValueError('Registry input exceeds 64 MiB')
    return plistlib.loads(data)


def live_registry(*args):
    result = subprocess.run(['/usr/sbin/ioreg', *args, '-a'], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    return load(result.stdout)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--adt', type=Path, help='Captured IODeviceTree plist')
    source.add_argument('--live', action='store_true', help='Read metadata using macOS ioreg')
    p.add_argument('--services', type=Path, action='append', default=[], help='Optional captured service plist')
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    if args.live and args.services:
        p.error('--services is for offline inputs')
    adt = live_registry('-p', 'IODeviceTree', '-l') if args.live else load(args.adt.read_bytes())
    services = ([live_registry('-r', '-c', cls) for cls in LIVE_CLASSES] if args.live else
                [load(file.read_bytes()) for file in args.services])
    result = scan(adt, services)
    result['observed_at'] = datetime.now(timezone.utc).isoformat()
    result['source_mode'] = 'live-registry' if args.live else 'offline-registry'
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
