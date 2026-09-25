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
| Wi-Fi | Not working in the tested desktop | Network discovery did not produce a usable interface |
| Bluetooth | Unverified | No native connection evidence |
| USB-C | Unverified | No claim of working external input/network/storage |
| GPU acceleration | Not implemented | Software-rendered desktop |
| Audio | Unverified | No native playback/capture evidence |
| SMC / power | Limited trackpad power work | Battery, suspend/resume and general power management unverified |
| Touch ID | Not implemented | No authentication path |

The current SSD buffer candidate has passed host fault tests and three diskless
VM checks. It still requires its own native test. A firmware endpoint, a successful
register read or a VM device must not be presented as usable physical SSD support.

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
