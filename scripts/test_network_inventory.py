import contextlib
import io
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest import mock

import network_inventory as network


def bundle(name, match):
    return plistlib.dumps({'CFBundleIdentifier': name, 'CFBundleVersion': '1',
        'IOKitPersonalities': {'private-label': {'IOProviderClass': 'IOPCIDevice', 'IOPCIMatch': match,
                                               'arbitrary': 'PRIVATE_SECRET'}}})


def pci(device=0x7932):
    return {'vendor-id': bytes.fromhex('c3140000'), 'device-id': device.to_bytes(4, 'little'),
            'revision-id': 0, 'subsystem-vendor-id': 0x14c3, 'subsystem-id': device,
            'IORegistryEntryName': 'PRIVATE_DEVICE', 'local-mac-address': b'PRIVATE_MAC',
            'IORegistryEntryChildren': [{'IOObjectClass': 'AppleSunriseHALClient',
                                         'ssid': 'PRIVATE_NETWORK', 'serial': 'PRIVATE_SERIAL'}]}


class NetworkInventoryTests(unittest.TestCase):
    def test_actual_device_pairs_match_separate_drivers(self):
        sources = dict(zip(network.DRIVERS, [bundle(network.DRIVERS[0], '0x792214c3 0x792314c3 0x793214c3'),
                                              bundle(network.DRIVERS[1], '0x792a14c3 0x792b14c3 0x793b14c3')]))
        report = network.inventory(plistlib.dumps([{'IORegistryEntryChildren': [pci(), pci(0x793b)]}]), sources)
        self.assertEqual([row['matching_installed_personalities'] for row in report['devices']], [[network.DRIVERS[0]], [network.DRIVERS[1]]])
        self.assertEqual(report['devices'][0]['observed_descendant_classes'], ['AppleSunriseHALClient'])
        self.assertFalse(report['linux_support_tested'])
        self.assertFalse(report['static_match_proves_driver_function'])
        self.assertNotIn('PRIVATE', json.dumps(report))
        self.assertNotIn('private-label', json.dumps(report))

    def test_match_masks_and_malformed_lists(self):
        self.assertTrue(network.personality_match('0x793014c3&0xfff0ffff', 0x14c3, 0x7932))
        self.assertFalse(network.personality_match('0x793214c3', 0x14e4, 0x7932))
        for value in ('', None, [], '0x793214c3 PRIVATE', '793214c3', '0x793214c3&0xshort'):
            self.assertIsNone(network.personality_match(value, 0x14c3, 0x7932))

    def test_missing_bundles_and_unrelated_pci(self):
        unrelated = pci(); unrelated['vendor-id'] = 0x14e4
        report = network.inventory(plistlib.dumps([pci(), unrelated, pci(0x0001)]), {})
        self.assertEqual(len(report['devices']), 1)
        self.assertEqual(report['devices'][0]['matching_installed_personalities'], [])

    def test_invalid_numbers_and_bundle_identity(self):
        for value in (True, -1, 65536, '0x14c3', b'123', b'12345'):
            self.assertIsNone(network.integer(value))
        with self.assertRaises(ValueError):
            network.driver_metadata(network.DRIVERS[0], bundle('unexpected', '0x793214c3'))

    def test_offline_cli_protects_input_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'pci.plist'; target = root / 'result.json'
            source.write_bytes(plistlib.dumps([pci()]))
            self.assertEqual(network.main(['--pci-plist', str(source), '--driver-extensions', str(root), '-o', str(target)]), 0)
            self.assertEqual(json.loads(target.read_text())['devices'][0]['device_id'], '0x7932')
            alias = root / 'alias'; alias.hardlink_to(source)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                network.main(['--pci-plist', str(source), '-o', str(alias)])

    def test_failed_capture_does_not_echo_raw_error(self):
        output = io.StringIO()
        with mock.patch.object(network.subprocess, 'check_output', side_effect=OSError('PRIVATE_SECRET')):
            with contextlib.redirect_stderr(output):
                self.assertEqual(network.main(['--live']), 1)
        self.assertNotIn('PRIVATE_SECRET', output.getvalue())


if __name__ == '__main__':
    unittest.main()
