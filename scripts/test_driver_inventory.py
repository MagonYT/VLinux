"""Synthetic-only regression tests for the offline sanitized inventory CLI."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

# Works both via unittest discovery and direct invocation, without installation.
spec = importlib.util.spec_from_file_location("driver_inventory", Path(__file__).with_name("driver_inventory.py"))
driver = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = driver
spec.loader.exec_module(driver)


def node(name, depth=0, props=None, controller="IOService", pipes=False):
    prefix = ("| " if pipes else "  ") * depth
    lines = [f"{prefix}+-o {name}  <class {controller}, id 0x123, retain 1>",
             prefix + "    {"]
    lines.extend(f'{prefix}      "{key}" = {value}' for key, value in (props or {}).items())
    lines.append(prefix + "    }")
    return "\n".join(lines) + "\n"


def report(text):
    return driver.inventory(text.encode())


class InventoryTests(unittest.TestCase):
    def test_little_endian_ids(self):
        self.assertEqual(driver.pci_id("<c3140000>"), "0x14c3")
        self.assertEqual(driver.pci_id("<32790000>"), "0x7932")
        self.assertEqual(driver.pci_id("<e414>"), "0x14e4")
        self.assertEqual(driver.pci_id("5315"), "0x14c3")
        self.assertEqual(driver.pci_id("0x7932"), "0x7932")
        for bad in ("<c31400>", "<c314000001>", "<00000100>", "65536", '"5315"', "<zz>"):
            self.assertIsNone(driver.pci_id(bad), bad)

    def test_compatible_hex_and_quoted(self):
        expected = ["wlan-pcie,bcm", "wlan-pcie,bcm4387"]
        self.assertEqual(driver.compatibles('<"wlan-pcie,bcm4387","wlan-pcie,bcm">'), expected)
        self.assertEqual(driver.compatibles("<" + b"wlan-pcie,bcm4387\0wlan-pcie,bcm\0".hex() + ">"), expected)
        self.assertEqual(driver.compatibles("<ff00>"), [])
        self.assertEqual(driver.compatibles('<"usb-drd,t8140" garbage>'), [])

    def test_depth_siblings_and_property_leakage(self):
        text = node("Root") + node("usb-drd@A280000", 1, {"compatible": '<"usb-drd,t8140">', "reg": "<01000000>"})
        text += node("usb-drd-port-hs@1", 2, {"reg": "<02000000>"}, pipes=True)
        # Wrong-depth and post-block properties must not mutate the child.
        text += '      "reg" = <bad00000>\n'
        text += '          "reg" = <bad10000>\n'
        text += node("usb-drd-port-ss@2", 2, {}, pipes=False)
        text += node("hpm0@C", 1, {"compatible": '<"usbc,sn201202x,spmi">'}, pipes=False)
        nodes = driver.parse_ioreg(text)
        self.assertEqual(nodes[2].facts, {"reg_hex": "02000000"})
        self.assertEqual(nodes[3].facts, {})
        self.assertIs(nodes[2].parent, nodes[1])
        self.assertIs(nodes[3].parent, nodes[1])
        self.assertIs(nodes[4].parent, nodes[0])
        self.assertEqual(nodes[4].path, "/Root/hpm0@C")

    def test_nested_dictionary_properties_not_adopted(self):
        text = ('+-o wlan@0  <class IOPCIDevice, id 0x123>\n'
                '    {\n'
                '      "arbitrary" = {\n'
                '        "vendor-id" = <c3140000>\n'
                '        "compatible" = <"wlan-pcie,bcm4387">\n'
                '      }\n'
                '      "device-id" = <32790000>\n'
                '    }\n')
        self.assertEqual(driver.parse_ioreg(text)[0].facts, {"pci_device_id": "0x7932"})

    def test_privacy_exclusion_and_path_sanitization(self):
        secrets = {"serial-number": '<"SERIAL_SECRET">', "IOPlatformUUID": '"UUID_SECRET"',
                   "local-mac-address": "<deadbeef1234>", "host-mac-address": "<102030405060>",
                   "IOKitDiagnostics": '"RAW_DUMP_SECRET"', "arbitrary": '"OTHER_SECRET"',
                   "IOName": '"PRIVATE_CONTROLLER"'}
        text = node("SERIAL_SECRET") + node("usb-drd@A280000", 1, {
            **secrets, "compatible": '<"usb-drd,t8140","SERIAL_SECRET","aa:bb:cc:dd:ee:ff">',
            "reg": "<01000000>"})
        text += node("SERIAL_SECRET-USB", 1, secrets, "PRIVATE_CONTROLLER")
        output = report(text)
        encoded = json.dumps(output)
        for secret in ("SERIAL_SECRET", "UUID_SECRET", "deadbeef1234", "102030405060", "RAW_DUMP_SECRET", "OTHER_SECRET", "PRIVATE_CONTROLLER", "aa:bb:cc:dd:ee:ff"):
            self.assertNotIn(secret, encoded)
        for key in secrets:
            self.assertNotIn(key, encoded)
        self.assertEqual(output["devices"][0]["path"], "/node-0/usb-drd@A280000")
        self.assertEqual(set(output["devices"][0]), {"path", "label", "compatible", "reg_hex"})

    def test_conflicting_pci_and_broadcom_compatible(self):
        props = {"compatible": '<"wlan-pcie,bcm4387","wlan-pcie,bcm">',
                 "vendor-id": "<c3140000>", "device-id": "<32790000>"}
        output = report(node("wlan@0", props=props, controller="IOPCIDevice"))
        self.assertEqual(output["devices"][0]["pci_vendor_id"], "0x14c3")
        self.assertEqual(output["devices"][0]["pci_device_id"], "0x7932")
        self.assertEqual(output["observations"]["wifi_identity_conflict"]["status"], "conflict")
        self.assertEqual(output["hypotheses"][0]["label"], "hypothesis")
        props["vendor-id"] = "<e4140000>"
        self.assertEqual(report(node("wlan@0", props=props, controller="IOPCIDevice"))["observations"]["wifi_identity_conflict"]["status"], "not_observed")

    def test_explicit_pci_compatible_conflict(self):
        output = report(node("wifi@0", props={"compatible": '<"pci14c3,793b">',
                                             "vendor-id": "<c3140000>", "device-id": "<32790000>"},
                             controller="IOPCIDevice"))
        self.assertEqual(output["observations"]["wifi_identity_conflict"]["status"], "conflict")

    def test_dockchannel_input_requires_ancestry(self):
        text = node("Root") + node("dockchannel-mtp@4B00000", 1, {"compatible": '<"dockchannel,t8002">'})
        text += node("mtp-transport", 2, controller="AppleDockChannelDevice")
        text += node("keyboard", 3, controller="AppleHIDTransportInterface")
        text += node("multi-touch", 3, controller="AppleHIDTransportInterface")
        text += node("keyboard", 1, controller="AppleHIDTransportInterface")
        paths = report(text)["observations"]["dockchannel_input"]["paths"]
        self.assertEqual(len(paths), 2)
        self.assertTrue(all("/dockchannel-mtp@4B00000/mtp-transport/" in p for p in paths))
        self.assertEqual(report(node("keyboard"))["observations"]["dockchannel_input"]["status"], "not_observed")

    def test_usb_categories(self):
        text = node("Root") + node("port-usb-c-1", 1, {"compatible": '<"dock,usb-c">'})
        text += node("usb-drd@A280000", 1, {"compatible": '<"usb-drd,t8140">'})
        text += node("hpm0@C", 1, {"compatible": '<"usbc,sn201202x,spmi">'})
        text += node("hpm1@A", 1)
        observations = report(text)["observations"]
        self.assertEqual(len(observations["usb_connectors"]["paths"]), 1)
        self.assertEqual(len(observations["usb_drd"]["paths"]), 1)
        self.assertEqual(len(observations["usb_hpm"]["paths"]), 2)

    def test_absent_and_incomplete_evidence(self):
        for text in ("", node("Root"), "not an ioreg capture", node("wlan@0", props={"compatible": '<"wlan-pcie,bcm4387">'})):
            output = report(text)
            self.assertEqual(output["observations"]["wifi_identity_conflict"]["status"], "not_observed")
            self.assertEqual(output["observations"]["dockchannel_input"]["status"], "not_observed")
            self.assertEqual(output["source"]["sha256"], hashlib.sha256(text.encode()).hexdigest())
            self.assertEqual(output["validation"], "offline_capture_only_no_hardware_validation")

    def test_cli_stdout_file_and_same_input_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.txt"
            destination = Path(directory) / "output.json"
            data = node("usb-drd").encode()
            source.write_bytes(data)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(driver.main([str(source)]), 0)
            self.assertEqual(json.loads(stdout.getvalue()), driver.inventory(data))
            self.assertEqual(driver.main([str(source), "--output", str(destination)]), 0)
            self.assertEqual(json.loads(destination.read_text()), driver.inventory(data))
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                driver.main([str(source), "-o", str(source)])
            self.assertEqual(source.read_bytes(), data)
            alias = Path(directory) / "alias.txt"
            alias.hardlink_to(source)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                driver.main([str(source), "-o", str(alias)])
            self.assertEqual(source.read_bytes(), data)

    def test_missing_file_diagnostic_does_not_echo_private_path(self):
        stderr = io.StringIO()
        with mock.patch.object(Path, "read_bytes", side_effect=OSError("PRIVATE_PATH")):
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                driver.main(["PRIVATE_PATH"])
        self.assertEqual(raised.exception.code, 1)
        self.assertNotIn("PRIVATE_PATH", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
