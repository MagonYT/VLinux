# SSD bring-up

The Neo's internal storage is not yet exposed as a Linux block device. The current
work investigates firmware startup in m1n1 before attempting NVMe again.

## Native observations

1. Power/queue diagnostics obtained guarded register snapshots and returned to
   the working RAM KDE desktop.
2. The earlier Identify setup timed out waiting for controller READY (`CSTS=0`).
   No Identify command was submitted.
3. Marker **67** confirmed RTKit protocol 12 and endpoint-map pages `0x51f`, `0x3`.
4. Marker **71** confirmed START requests for
   endpoints 1, 2, 3, 4, 8 and 10. Endpoint 1 requested a fresh **32 KiB** crashlog
   buffer. No buffer was granted; no IOP power acknowledgment was observed.
5. The first buffer build returned to KDE with `arena is not fresh heap memory`.
   Its caller planned 1 MiB, but the planner compiled for 64 KiB because it did
   not include the generated build configuration. No buffer exchange occurred.

The firmware may be waiting for that first buffer reply before starting the other
services. That is the hypothesis for the next test, not a confirmed cause.

## Current buffer candidate

Corrected build `800d634c93e1c5c7`, payload SHA-256
`808d8b58fbb1925a44ac86920df54572c146ea5f1f70f1c3a77aba03249e3396`.
The payload is kept in the local test workspace; no boot binary is published here.

The shared memory header now includes the generated configuration directly.
The original host test masked the error with a command-line define. Its replacement
uses a native-style source/build layout, checks both 64 KiB and 1 MiB builds, and
replays the photographed allocation values. It fails against the old header and
passes with the correction. The original ownership checks remain intact.

The probe reserves an owned 1 MiB pool, requires the photographed first request,
checks the entire SART version-3 table and requires slot 2 to be empty. It zeros
and cache-cleans the pool, then writes only that slot's page, length and enable
fields, with individual readbacks and another full table comparison.

It can grant one fresh buffer to each of endpoints 1, 2, 4 and 8, capped at
256 KiB each, plus bounded canonical syslog/ioreport acknowledgments. Faults stop
further MMIO. All reservations and any mapping stay in place until poweroff.
It does not request AP power, start application endpoints, configure NVMe, issue
storage commands or hand off to Linux after discovery begins.

| Marker | Meaning |
|---|---|
| 72 / 73 / 74 | Mapping / verified mapping / buffer grant in progress |
| 75 | Bounded capture with at least one grant; IOP ON unconfirmed |
| 76 | IOP power acknowledgment `0x20` after at least one grant |
| 78 | Refusal, fault or timeout; capture the reason above the summary |

Marker 76 would not establish complete service initialization, correct DMA data,
NVMe readiness or a working SSD. The native result for this candidate is pending.

## Automated evidence

The actual C buffer policy passes ASan/UBSan with **202** simulated MMIO positions,
**74** before/after write-fault cases, **27** protocol scenarios and **18** polling
fault cases. The new reserved-pool size also passes memory/overlap tests locally.
The portable buffer test here uses the same C harness and a minimal fixture with
only compatibility strings, a quiesced property and the SART version.

The corrected payload passes 195 host regressions and exact early m1n1 startup
emulation. Its matching systemd, headless Plasma and graphical desktop/input VM
checks pass, including all five report pages. It is staged locally for the next
native test. VMs do not execute the Neo's m1n1/SART/mailbox path, so those results do
not replace the next physical test.
