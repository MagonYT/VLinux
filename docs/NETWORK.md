# Neo Wi-Fi and Bluetooth: verified identity and porting path

Read-only macOS inspection on 25 September 2026 identifies the wireless devices
as MediaTek PCI functions. The captured Broadcom-compatible device-tree text
does not agree with their enumerated PCI IDs.

| Function | PCI vendor:device | Installed matching personality | Observed descendant |
| --- | --- | --- | --- |
| Wi-Fi | `14c3:7932` | `com.apple.AppleSunriseWLAN` | `AppleSunriseHALClient`, `IOUserNetworkWLAN` |
| Bluetooth | `14c3:793b` | `com.apple.AppleSunriseBluetooth` | `AppleSunriseHALClient` |

Both functions report revision zero and matching subsystem vendor/device IDs.
The installed WLAN personality accepts `7922`, `7923` and `7932`; the Bluetooth
personality accepts `792a`, `792b` and `793b`, all with vendor `14c3`. A matching
personality alone does not prove the driver is attached or operational. The
observed descendants supply separate evidence of the macOS service tree.

The WLAN bundle also contains `IZUBA_W7932_2.bin`,
`IZUBA_WIFI_MT7932_patch_mcu_1_2_hdr.bin` and `IZUBA_EEPROM_MT7932_1.bin`.
These names support the MT7932 identification; they do not establish compatibility
with a Linux mt76 register layout or firmware protocol. Firmware, calibration
data and driver binaries were not copied into the public repository.

## Reproduce the metadata scan

```sh
python3 scripts/network_inventory.py --live --output network-inventory.json
python3 -m unittest discover -s scripts -p test_network_inventory.py
```

The scanner reads the PCI registry and two fixed installed bundle plists.
It exports only selected numeric IDs, known driver classes, static PCI matches,
bundle versions and source hashes. It does not open driver user clients, upload
firmware, connect to a network or export MAC addresses, SSIDs or serial numbers.
Six synthetic tests cover the actual device pairs, match masks, malformed input,
missing bundles, privacy exclusions and protection against overwriting inputs.
The sanitized live result is [neo-network-20260925.json](evidence/neo-network-20260925.json).

## PCIe controller resources captured separately

The macOS device tree reports `apcie,t8140`, three ports and 25 register ranges.
The array can be grouped as seven shared ranges plus six per port, matching the
*shape* of m1n1's newer t8132 descriptor. This is a comparison to investigate,
not confirmation that its reset bits, tunables or initialization sequence apply.
The current m1n1 controller matcher has no `apcie,t8140` branch.

| Resource metadata | Observed value |
| --- | --- |
| Controller range 0 | `0x1cb0000000`, length `0x10000000` |
| Controller range 1 | `0x394000000`, length `0x4000` |
| Port-group starting ranges 7 / 13 / 19 | `0x390028000` / `0x391028000` / `0x392028000` |
| Controller interrupt IDs | `0x4b5`, `0x4be`, `0x4c7` |
| Observed bridge metadata | `pci-bridge0`, PCI `106b:100c` |
| DART compatible | `dart,t8110` |
| DART register ranges | `0x390000000` + `0x20000`; `0x30079c000` + `0x4000` |
| DART interrupt ID | `0x4b6` |

The first range's size and the existing descriptors suggest an ECAM window;
that role remains an inference. Raw interrupt IDs are ADT metadata, not ready-made
Linux interrupt specifiers. No register was accessed and no PCIe reset, power,
clock, IOMMU mapping or device-binding operation was attempted.

The full sanitized resource table is [neo-pcie-20260925.json](evidence/neo-pcie-20260925.json).

## What blocks Linux today

The inspected kernel is pinned to `8de57da87a9b807b52d6844270aecf498559c9ed`
with VLinux's local bring-up changes. Its `mt7921/pci.c` and `mt7925/pci.c`
tables do not contain `7932`. The MediaTek wireless and Bluetooth source trees
have no `7932` or `793b` support entry in this checkout. This is a statement
about the checked-out sources, not every external development branch.

The current native t8140 device tree also has no PCIe host or wireless node.
Adding a Wi-Fi PCI ID would therefore not make this build discover the device.
Existing mt76 probe paths perform chip-specific resets and DMA setup, so a new
ID must follow a register/protocol comparison rather than assume equivalence.
The Bluetooth function is PCIe in the observed macOS topology; the existing
MediaTek USB Bluetooth path is not evidence that this PCIe transport works.

The next useful milestones are:

1. Map t8140 PCIe controller, port, power, clock, reset, interrupt and DART
   dependencies from the native device tree and existing Apple PCIe driver.
   Preserve this separately from the working input device tree.
2. Add a bounded controller discovery test, then establish PCI enumeration
   without binding a guessed WLAN driver or issuing wireless firmware commands.
3. Compare Sunrise/MT7932 register and firmware transport metadata with mt76.
   Determine whether it needs a new chip variant and transport implementation.
4. Add local firmware extraction only after its required files and protocol are
   understood; keep board calibration tied to the correct device.
5. Test firmware startup, interface creation and packet traffic as separate
   milestones. Interface presence alone is not a connectivity result.

No Wi-Fi, Bluetooth or Internet-access support is claimed by this investigation.
