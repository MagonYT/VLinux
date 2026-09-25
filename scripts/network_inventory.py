#!/usr/bin/env python3
"""Read PCI identity and fixed Apple Sunrise driver metadata without device I/O.

Raw registry data is kept in memory. The output excludes interface addresses,
network names, credentials, device serials and arbitrary driver properties.
Static personality matching is not evidence of a usable Linux driver.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import subprocess
import sys

DRIVERS = ('com.apple.AppleSunriseWLAN', 'com.apple.AppleSunriseBluetooth')
DRIVER_CLASSES = frozenset(('AppleSunriseHALClient', 'IOUserNetworkWLAN',
                            'IOUserNetworkWLANDevice', 'IOUserNetworkEthernet'))
PCI_IDS = frozenset((0x7922, 0x7923, 0x7932, 0x792a, 0x792b, 0x793b))
VERSION = re.compile(r'[0-9]+(?:\.[0-9]+){0,5}')
MATCH = re.compile(r'0x([0-9a-fA-F]{8})(?:&0x([0-9a-fA-F]{8}))?')


def integer(value, bits=16):
    if isinstance(value, bytes) and len(value) in (1, 2, 4):
        value = int.from_bytes(value, 'little')
    if type(value) is int and 0 <= value < (1 << bits):
        return value
    return None


def children(node):
    return [item for item in node.get('IORegistryEntryChildren', [])
            if isinstance(item, dict)]


def walk(nodes):
    for node in nodes:
        if not isinstance(node, dict):
            continue
        yield node
        yield from walk(children(node))


def personality_match(expression, vendor, device):
    """Reject malformed match lists instead of partially accepting them."""
    if not isinstance(expression, str) or not expression.split():
        return None
    parts = [MATCH.fullmatch(token) for token in expression.split()]
    if not all(parts):
        return None
    combined = (device << 16) | vendor
    return any(combined & int(item[2] or 'ffffffff', 16) ==
               int(item[1], 16) & int(item[2] or 'ffffffff', 16) for item in parts)


def driver_metadata(identifier, source):
    info = plistlib.loads(source)
    if not isinstance(info, dict) or info.get('CFBundleIdentifier') != identifier:
        raise ValueError('Unexpected driver bundle identity')
    result = {'bundle_identifier': identifier, 'info_sha256': hashlib.sha256(source).hexdigest()}
    for key in ('CFBundleVersion', 'CFBundleShortVersionString'):
        value = info.get(key)
        if isinstance(value, str) and VERSION.fullmatch(value):
            result[key] = value
    expressions = []
    personalities = info.get('IOKitPersonalities', {})
    if isinstance(personalities, dict):
        for props in personalities.values():
            if not isinstance(props, dict) or props.get('IOProviderClass') != 'IOPCIDevice':
                continue
            expression = props.get('IOPCIMatch')
            if personality_match(expression, 0, 0) is not None:
                expressions.append(' '.join(expression.split()).lower())
    result['pci_match_expressions'] = sorted(set(expressions))
    return result


def inventory(pci_source, driver_sources):
    parsed = plistlib.loads(pci_source)
    if not isinstance(parsed, list):
        raise ValueError('Expected an ioreg plist array')
    drivers = [driver_metadata(name, driver_sources[name]) for name in DRIVERS if name in driver_sources]
    devices = []
    for node in walk(parsed):
        vendor, device = integer(node.get('vendor-id')), integer(node.get('device-id'))
        if vendor != 0x14c3 or device not in PCI_IDS:
            continue
        row = {'vendor_id': f'0x{vendor:04x}', 'device_id': f'0x{device:04x}'}
        for source_key, output_key in (('subsystem-vendor-id', 'subsystem_vendor_id'),
                                       ('subsystem-id', 'subsystem_device_id'),
                                       ('revision-id', 'revision_id')):
            value = integer(node.get(source_key))
            if value is not None:
                row[output_key] = f'0x{value:04x}'
        row['observed_descendant_classes'] = sorted({item.get('IOObjectClass') for item in walk(children(node))
                                                    if item.get('IOObjectClass') in DRIVER_CLASSES})
        row['matching_installed_personalities'] = [driver['bundle_identifier'] for driver in drivers
            if any(personality_match(expression, vendor, device) for expression in driver['pci_match_expressions'])]
        devices.append(row)
    return {'schema_version': 1, 'ioreg_sha256': hashlib.sha256(pci_source).hexdigest(),
            'scope': 'Registry and installed bundle metadata only; no driver calls, firmware upload or network connections.',
            'devices': devices, 'drivers': drivers,
            'linux_support_tested': False, 'static_match_proves_driver_function': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--live', action='store_true')
    source.add_argument('--pci-plist', type=Path)
    parser.add_argument('--driver-extensions', type=Path, default=Path('/System/Library/DriverExtensions'))
    parser.add_argument('-o', '--output', type=Path)
    args = parser.parse_args(argv)
    inputs = ([args.pci_plist] if args.pci_plist else []) + [args.driver_extensions / (name + '.dext') / 'Info.plist' for name in DRIVERS]
    if args.output and any(args.output.resolve() == path.resolve() or
                           (args.output.exists() and path.exists() and args.output.samefile(path)) for path in inputs):
        parser.error('Output must not overwrite an input file')
    try:
        raw = (subprocess.check_output(['/usr/sbin/ioreg', '-a', '-r', '-c', 'IOPCIDevice'], timeout=30)
               if args.live else args.pci_plist.read_bytes())
        bundles = {name: path.read_bytes() for name, path in zip(DRIVERS, inputs[-len(DRIVERS):]) if path.is_file()}
        encoded = json.dumps(inventory(raw, bundles), indent=2) + '\n'
        if args.output:
            args.output.write_text(encoded)
        else:
            print(encoded, end='')
    except (OSError, ValueError, plistlib.InvalidFileException, subprocess.SubprocessError):
        print('Network metadata capture failed; no raw registry data was exported.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
