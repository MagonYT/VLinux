# Hardware support

Status of MacBook Neo hardware under VLinux. Update this table as things
start working, with a link to the commit or issue.

Legend: ✅ works · 🟡 partial · 🔬 being investigated · ❌ not started

| Component          | Status | Notes |
|--------------------|--------|-------|
| Boot (m1n1 chain)  | 🔬     | Depends on the Neo permitting third-party kernels |
| CPU cores / SMP    | ❌     | |
| Interrupts (AIC)   | ❌     | |
| Serial console     | ❌     | Needed for all early bring-up |
| Framebuffer        | ❌     | simpledrm on the iBoot-initialised display |
| Internal NVMe      | ❌     | |
| Keyboard/trackpad  | ❌     | |
| USB-C              | ❌     | |
| Wi-Fi / Bluetooth  | ❌     | |
| Audio              | ❌     | |
| GPU acceleration   | ❌     | |
| Power management   | ❌     | |
| Battery / SMC      | ❌     | |

## Collecting hardware information

The most useful thing contributors with a MacBook Neo can do right now is
share hardware data from macOS:

```sh
ioreg -l > ioreg.txt
system_profiler SPHardwareDataType SPUSBDataType SPNVMeDataType > profile.txt
```

Attach these to an issue. Remove anything identifying (serial numbers, UDIDs)
first.
