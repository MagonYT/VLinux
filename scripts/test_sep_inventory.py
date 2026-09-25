import json
import struct
import unittest

import sep_inventory as inv


def node(name, children=(), **props):
    return dict(IORegistryEntryName=name, IORegistryEntryChildren=list(children), **props)


def fixture():
    return [node('Root', [node('device-tree', [node('arm-io', [
        node('sep', compatible=b'iop-sep,ascwrap-v6\0', reg=struct.pack('<QQ', 0x72600000, 0x88000)),
        node('spi2', [node('mesa', compatible=b'biosensor,mesa\0', **{'spi-frequency': struct.pack('<I', 8000000)})]),
    ], compatible=b'arm-io,t8140\0', ranges=struct.pack('<QQQ', 0, 0x210000000, 0x2f0000000))])])]


class SepInventoryTests(unittest.TestCase):
    def test_address_translation_and_sensor(self):
        result = inv.scan(fixture())
        self.assertTrue(result['t8140_identified'])
        sep = next(x for x in result['devices'] if x['path'] == '/arm-io/sep')
        self.assertEqual(sep['resources'][0]['physical_address'], '0x282600000')
        self.assertEqual(result['devices'][-1]['spi_frequency_hz'], 8000000)
        self.assertFalse(result['linux_enrollment_tested'])
        self.assertFalse(result['sep_bypass_demonstrated'])

    def test_private_properties_never_exported(self):
        tree = fixture()
        for _, n in inv.walk(tree):
            n.update(serial='PRIVATE-SERIAL', template=b'PRIVATE-TEMPLATE', username='PRIVATE-USER')
        services = [node('PRIVATE-USER', IOClass='AppleSEPManager', enrollment=b'PRIVATE-ENROLLMENT')]
        report = json.dumps(inv.scan(tree, services))
        self.assertNotIn('PRIVATE', report)
        self.assertIn('AppleSEPManager', report)

    def test_unknown_driver_and_compatible_suffix_not_exported(self):
        tree = fixture()
        for path, n in inv.walk(tree):
            if path.endswith('/sep'):
                n['compatible'] = b'iop-sep,ascwrap-v6-PRIVATE\0'
        services = [node('x', IOClass='AppleSEPManager-PRIVATE')]
        report = json.dumps(inv.scan(tree, services))
        self.assertNotIn('PRIVATE', report)
        self.assertNotIn('iop-sep,ascwrap-v6', report)

    def test_ambiguous_ranges_are_not_guessed(self):
        tree = fixture()
        for path, n in inv.walk(tree):
            if path.endswith('/arm-io'):
                n['ranges'] *= 2
        result = inv.scan(tree)
        sep = next(x for x in result['devices'] if x['path'] == '/arm-io/sep')
        self.assertIsNone(sep['resources'][0]['physical_address'])

    def test_malformed_records_and_missing_devices(self):
        for data in (None, 'bad', b'\0', bytes(1032)):
            self.assertEqual(inv.decode_records(data, 2), [])
        result = inv.scan([])
        self.assertFalse(result['t8140_identified'])
        self.assertEqual(result['devices'], [])
        self.assertFalse(result['service_inventory_collected'])

    def test_path_injection_and_duplicate_rejected(self):
        fake = [node('Root/device-tree/arm-io', compatible=b'arm-io,t8140\0')]
        self.assertEqual(inv.scan(fake)['devices'], [])
        tree = fixture()
        with self.assertRaises(ValueError):
            inv.scan(tree + tree)


if __name__ == '__main__':
    unittest.main()
