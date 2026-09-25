#!/usr/bin/env python3
"""Offline, allowlisted inventory from captured `ioreg -p IODeviceTree -l` text.

Only the four PROPERTY_KEYS are parsed. Unknown path components are replaced by
positional placeholders, and compatible/controller strings use bounded grammars.
This deliberately loses unsupported facts rather than exporting arbitrary data.
No hardware access, driver probing, subprocesses, or network access occurs.
"""

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import sys


PROPERTY_KEYS = frozenset({"compatible", "reg", "vendor-id", "device-id"})
NODE = re.compile(r"^([ |]*)\+-o (.*?)\s+<class ([A-Za-z0-9_]+),.*>$")
PROPERTY = re.compile(r'^([ |]*)"([^"\\]+)"\s*=\s*(.*?)\s*$')
# Full matches are essential: free-form suffixes could contain identifying data.
SAFE_COMPONENT = re.compile(
    r"(?:Root|device-tree|arm-io|soc|apcie\d?|pci-bridge\d?|pci\d?"
    r"|wlan|wifi|bluetooth-pcie|dockchannel-(?:mtp|uart)|mtp-transport"
    r"|keyboard|multi-touch|trackpad|port-usb-c-[1-9]"
    r"|hpm[0-9]|spmi[0-9]?|nub-spmi(?:[0-9]|-a[0-9])|spmi-allAce|i2c[0-9]?|usb-drd"
    r"|usb-drd-port-(?:hs|ss)|usb-drd-hs-hub-port[1-9]"
    r"|usb-(?:hub|repeater)-i2c|dart-usb|mapper-usb)"
    r"(?:@[0-9A-Fa-f]{1,9}(?:,[0-9A-Fa-f]{1,4})?)?"
)
SAFE_COMPATIBLE = re.compile(
    r"(?:aapl,dock-channels|dockchannel,t[0-9]{4}|aht-hibernator"
    r"|dock,usb-c|usb-drd,t[0-9]{4}|usbc,sn[0-9]{6}x,spmi"
    r"|wlan-pcie,bcm[0-9]{0,5}|brcm,bcm[0-9]{4,5}(?:-fmac)?"
    r"|pci[0-9a-fA-F]{1,4},[0-9a-fA-F]{1,4}"
    r"|usb-repeater-i2c,ticd[0-9]e[0-9]{2}|apcie-bridge)"
)
SAFE_CONTROLLER = re.compile(
    r"(?:AppleDockChannel(?:Device)?|AppleHIDTransport(?:Interface|DeviceFIFO)"
    r"|Apple(?:T[0-9]{4})?USB(?:XHCI|XDCI)"
    r"|AppleUSB(?:20|30)XHCI(?:ARM|TypeC)?Port"
    r"|AppleHPM(?:ARM|Embedded|ARMSPMI|InterfaceType[0-9]{1,2})?"
    r"|AppleTypeCPhy|AppleT[0-9]{4}TypeCPhy|IOPCIDevice|IOPCI2PCIBridge)"
)


@dataclass
class Node:
    """Internal node: only sanitized facts, with structural parent identity."""

    column: int
    name: str
    path: str
    controller: str | None
    parent: "Node | None"
    facts: dict = field(default_factory=dict)
    properties_open: bool = False


def data_bytes(value):
    """Accept bounded ioreg hex data, never dictionaries or quoted dumps."""
    if not re.fullmatch(r"<[0-9a-fA-F\s]*>", value):
        return None
    try:
        result = bytes.fromhex(value[1:-1])
    except ValueError:
        return None
    return result if len(result) <= 4096 else None


def pci_id(value):
    """ioreg OSData PCI IDs are little-endian, not DT big-endian cells."""
    data = data_bytes(value)
    if data is not None:
        if len(data) not in (2, 4):
            return None
        number = int.from_bytes(data, "little")
    elif re.fullmatch(r"(?:0x[0-9a-fA-F]{1,4}|[0-9]{1,5})", value):
        number = int(value, 16 if value.startswith("0x") else 10)
    else:
        return None
    return f"0x{number:04x}" if 0 <= number <= 0xffff else None


def compatibles(value):
    """Decode quoted OSData strings or NUL-separated ASCII hex strings."""
    inner = value[1:-1] if value.startswith("<") and value.endswith(">") else value
    if re.fullmatch(r'"[^"\\]*"(?:\s*,\s*"[^"\\]*")*', inner):
        strings = re.findall(r'"([^"\\]*)"', inner)
    else:
        data = data_bytes(value)
        if data is None:
            return []
        try:
            strings = data.decode("ascii").split("\0")
        except UnicodeDecodeError:
            return []
    return sorted({s for s in strings if SAFE_COMPATIBLE.fullmatch(s)})


def parse_ioreg(text):
    """Use marker columns and direct property columns, not pipe counts.

    Sibling leaf nodes have different pipe decorations but the same depth.
    Closing braces end a node's property block; nested properties, continuations,
    malformed lines and unrelated keys cannot leak into the last visited child.
    """
    nodes = []
    stack = []
    for line in text.splitlines():
        match = NODE.fullmatch(line)
        if match:
            column = len(match[1])
            while stack and stack[-1].column >= column:
                stack.pop()
            parent = stack[-1] if stack else None
            raw_name = match[2]
            name = raw_name if SAFE_COMPONENT.fullmatch(raw_name) else f"node-{len(nodes)}"
            controller = match[3] if SAFE_CONTROLLER.fullmatch(match[3]) else None
            node = Node(column, name, (parent.path if parent else "") + "/" + name,
                        controller, parent)
            nodes.append(node)
            stack.append(node)
            continue
        # A property belongs only to a node at its exact structural depth.
        brace = re.fullmatch(r"([ |]*)([{}])\s*", line)
        if brace:
            for node in reversed(stack):
                if len(brace[1]) == node.column + 4:
                    node.properties_open = brace[2] == "{"
                    break
            continue
        match = PROPERTY.fullmatch(line)
        if not match or match[2] not in PROPERTY_KEYS:
            continue
        owner = next((n for n in reversed(stack)
                      if n.properties_open and len(match[1]) == n.column + 6), None)
        if owner is None:
            continue
        key, value = match[2], match[3]
        if key == "compatible":
            result = compatibles(value)
        elif key == "reg":
            data = data_bytes(value)
            result = data.hex() if data else None
            key = "reg_hex"
        else:
            result = pci_id(value)
            key = "pci_" + key.replace("-", "_")
        if result:
            owner.facts[key] = result
    return nodes


def base_name(node):
    return node.name.split("@", 1)[0]


def is_dock(node):
    return (base_name(node).startswith("dockchannel-")
            or node.controller in {"AppleDockChannel", "AppleDockChannelDevice"}
            or any(c.startswith(("dockchannel,", "aapl,dock-channels"))
                   for c in node.facts.get("compatible", [])))


def ancestors(node):
    while node.parent:
        node = node.parent
        yield node


def inventory(source):
    """Return versioned JSON-compatible evidence; source is the exact bytes."""
    nodes = parse_ioreg(source.decode("utf-8", errors="replace"))
    groups = {key: [] for key in (
        "dockchannel", "dockchannel_input", "usb_connectors", "usb_drd", "usb_hpm",
        "wifi", "pci")}
    devices = []
    conflicts = []
    for node in nodes:
        name = base_name(node)
        compat = node.facts.get("compatible", [])
        categories = []
        if is_dock(node):
            categories.append("dockchannel")
        if name in {"keyboard", "multi-touch", "trackpad"} and any(
                is_dock(parent) for parent in ancestors(node)):
            categories.append("dockchannel_input")
        if name.startswith("port-usb-c-") or "dock,usb-c" in compat:
            categories.append("usb_connectors")
        if name == "usb-drd" or any(c.startswith("usb-drd,") for c in compat):
            categories.append("usb_drd")
        if re.fullmatch(r"hpm[0-9]", name) or any(c.startswith("usbc,") for c in compat):
            categories.append("usb_hpm")
        if name in {"wlan", "wifi"} or any(c.startswith(("wlan-pcie,", "brcm,bcm")) for c in compat):
            categories.append("wifi")
        is_pci = node.controller in {"IOPCIDevice", "IOPCI2PCIBridge"} or name.startswith("pci")
        if is_pci:
            categories.append("pci")
        if not categories and not node.controller and not name.startswith("usb-"):
            continue
        facts = {key: value for key, value in node.facts.items()
                 if is_pci or not key.startswith("pci_")}
        device = {"label": "observed", "path": node.path, **facts}
        if node.controller:
            device["controller_name"] = node.controller
        devices.append(device)
        for category in categories:
            groups[category].append(node.path)
        vendor = facts.get("pci_vendor_id")
        device_id = facts.get("pci_device_id")
        reasons = []
        if "wifi" in categories and vendor:
            if any(c.startswith(("wlan-pcie,bcm", "brcm,bcm")) for c in compat) and vendor != "0x14e4":
                reasons.append("Broadcom-compatible text disagrees with captured PCI vendor ID")
            for c in compat:
                match = re.fullmatch(r"pci([0-9a-fA-F]{1,4}),([0-9a-fA-F]{1,4})", c)
                if match and (int(match[1], 16) != int(vendor, 16) or
                              (device_id and int(match[2], 16) != int(device_id, 16))):
                    reasons.append("PCI-compatible text disagrees with captured PCI IDs")
        if reasons:
            conflicts.append({"label": "observed", "path": node.path, "reasons": sorted(set(reasons))})
    observations = {key: {"label": "observed", "status": "present_in_capture" if paths else "not_observed",
                          "paths": paths} for key, paths in groups.items()}
    observations["wifi_identity_conflict"] = {
        "label": "observed", "status": "conflict" if conflicts else "not_observed", "evidence": conflicts}
    hypotheses = []
    if groups["dockchannel_input"]:
        hypotheses.append({"label": "hypothesis", "topic": "input_transport",
                           "statement": "Input nodes beneath dockchannel suggest a dockchannel HID transport; Linux operation is untested."})
    if any(groups[k] for k in ("usb_connectors", "usb_drd", "usb_hpm")):
        hypotheses.append({"label": "hypothesis", "topic": "usb_topology",
                           "statement": "Connector, DRD and HPM nodes are inventory evidence, not proof of port routing, host/device roles or working USB."})
    if conflicts:
        hypotheses.append({"label": "hypothesis", "topic": "wifi_identity",
                           "statement": "Compatible text may be inherited or stale; resolve the conflicting identity before selecting a driver. No chipset or driver is validated."})
    return {"schema_version": 1, "source": {"format": "captured_ioreg_text", "sha256": hashlib.sha256(source).hexdigest()},
            "validation": "offline_capture_only_no_hardware_validation", "devices": devices,
            "observations": observations, "hypotheses": hypotheses}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="existing captured ioreg text (never runs ioreg)")
    parser.add_argument("-o", "--output", type=Path, help="JSON destination; omitted means stdout")
    args = parser.parse_args(argv)
    try:
        if args.output and (args.output.resolve() == args.input.resolve()
                            or (args.output.exists() and args.output.samefile(args.input))):
            parser.error("output must differ from input")
        result = inventory(args.input.read_bytes())
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except OSError:
        # Do not echo local paths or input contents in diagnostics.
        parser.exit(1, "Unable to read captured input or write JSON output.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
