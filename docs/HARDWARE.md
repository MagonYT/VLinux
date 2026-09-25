# Hardware support

Status as of **2026-09-25**, for the development Neo. Native observations come
from the tester's reports and boot photographs. Host/VM checks are listed
separately and do not establish physical driver support.

| Component | Native status | Evidence and limits |
|---|---|---|
| Custom-kernel boot / m1n1 | Working prototype | Reaches native Linux and Arch userland |
| Arch Linux ARM / KDE Plasma | Desktop reached | RAM root; session changes are lost at reboot |
| CPU | Single-core boot | Working boot arguments use `maxcpus=1`; SMP unverified |
| Interrupts / AIC | Enough for current boot and input | Full interrupt coverage unverified |
| Internal display | Working framebuffer | simpledrm/fbdev; software rendering |
| Built-in keyboard | Reported working | Command -> Super/Meta; Option -> Alt |
| Trackpad | Motion, scrolling and gestures reported working | Long-term stability and all gestures unverified |
| Internal SSD | Firmware bring-up | Protocol/map and first buffer request captured; no Linux block device |
| Wi-Fi | Not working in the tested desktop | macOS PCI ID `14c3:7932`; no usable Linux interface |
| Bluetooth | Unverified | macOS PCI ID `14c3:793b`; no native Linux connection evidence |
| USB-C | Unverified | No claim of working external input/network/storage |
| GPU acceleration | Not implemented | Software-rendered desktop |
| Audio | Unverified | No native playback/capture evidence |
| SMC / power | Limited trackpad power work | Battery, suspend/resume and general power management unverified |
| Touch ID | Not implemented | SEP/Mesa metadata and macOS drivers identified; no Linux enrollment or bypass demonstrated |

The first buffer candidate refused memory planning and returned to KDE; its
1 MiB/64 KiB configuration mismatch is corrected in the next candidate. Matching
VM and native evidence are tracked separately in [SSD bring-up](SSD.md).
A firmware endpoint, a successful
register read or a VM device must not be presented as usable physical SSD support.

The [Touch ID investigation](TOUCH-ID.md) includes a read-only metadata scanner
and an explicit list of unresolved protocol and storage requirements.
The [network investigation](NETWORK.md) resolves the conflicting Broadcom device
tree text against enumerated PCI IDs and installed Sunrise driver metadata.
The [diagnostics desktop](DIAGNOSTICS.md) adds a batch report for power, thermal,
backlight, USB and graphics interfaces without adding hardware drivers.
The [graphics investigation](GRAPHICS.md) records the active macOS G17P driver
and the missing kernel/firmware/userspace work for native acceleration.

## Battery and SMC scope

The current native configuration enables `CONFIG_MFD_MACSMC` but leaves
`CONFIG_MACSMC_POWER` disabled. The t8140 device-tree overlay deliberately selects
the Neo trackpad power path. In the patched `drivers/mfd/macsmc.c`, that path
returns `-EOPNOTSUPP` for generic SMC key reads/writes and key-info requests;
it exposes the bounded trackpad operation instead. Enabling the battery config
option alone would therefore not provide a working battery driver. A port must
first establish the Neo's generic key protocol and notification behavior while
preserving the working trackpad path.

## Sharing observations

Include the build ID, enrollment result, last checkpoint and relevant diagnostic
lines. Share the smallest useful excerpt rather than a complete machine dump.
The hardware inventory parser strips identifying fields and has dedicated tests:

```sh
cd scripts
python3 -m unittest test_driver_inventory
```

Do not upload firmware blobs, serial numbers, device UUIDs, boot-policy data or
private recovery logs. Reports remain useful without those fields.
