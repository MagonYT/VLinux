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
6. Corrected buffer v2 passed memory preflight and the complete SART mapping/
   readback checks. It sent a 32 KiB crashlog grant and a 16 KiB IOReport grant.
   It then held at **78**: `transmit packet/limit ep=4`. Final counts were six
   STARTs, 27 received messages, 64 service TX words, two grants, three SART
   writes and zero NVMe commands. IOP ON and buffer contents were unverified.

The photographed result is associated with the matching successful enrollment
receipt; the build ID is not visible in the photograph. The sanitized
[native result](evidence/ssd-buffers-v2-native-20260925.json) records those limits.

## Current buffer candidate

Capture v3 build `7d53a0b40d1b4814`, payload SHA-256
`051ef52ea29aaa9aa26aca998c53b34353964ba43db74a049e5e2f37857c289c`.
The payload is kept in the local test workspace; no boot binary is published here.

The old 64-word transmit budget allowed six STARTs (12 words), two grants (four
words) and 24 IOReport acknowledgments (48 words). It refused the next reply.
The new C harness reproduces that stop with a synthetic stream consistent with
the photographed counts and a simulated buffer layout. The photograph does not
show every packet; the replay uses the visible canonical type-8 report form for
all 25 post-grant endpoint-4 messages. The canonical report acknowledgment agrees
with the upstream [RTKit implementation](https://github.com/AsahiLinux/m1n1/blob/4184923ffb2dff079b384d6a32cc02142aa14572/src/rtkit.c).
Why the firmware repeats these reports, and whether it will reach IOP ON with
more replies, remains a native-test question.

V3 captures at most **256 RX messages** and **524 service TX words**, enough for
six STARTs plus at most one two-word reply per received message. It logs the first
16 raw packets and then final endpoint/IOReport counters. The existing 50000 total
receive polls, 10000 consecutive empty polls and 2000 outbound FIFO polls per
send remain. These are iteration limits, not a guaranteed wall-clock deadline.
Packet forms, address allowlists, SART writes and buffer sizes are unchanged.

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
NVMe readiness or a working SSD. The native result for v3 is pending. The exact
v2 image (`800d634c93e1c5c7` / `808d8b58fbb1`) remains a separate local fallback.

## Automated evidence

The actual C buffer policy passes ASan/UBSan with **202** simulated MMIO positions,
**74** before/after write-fault cases, **31** protocol scenarios and **18** polling
fault cases. Four stream cases cover the observed prefix, a hypothetical later
IOP ON, an endless stream and noncanonical metadata. Every one of the **1684**
access positions in the full 256-message stream is fault-injected, including
**1070** before/after write-fault cases. Synthetic IOP ON is not native evidence.
The unchanged reserved-pool size retains its memory/overlap test evidence locally.
The portable buffer test here uses the same C harness and a minimal fixture with
only compatibility strings, a quiesced property and the SART version.

The portable runner constructs an isolated source/build layout and generated
configuration header. This also fixes its missing-header failure on a clean,
unbuilt checkout; it does not alter an existing developer build. The pinned patch
reconstructs all 29 selected m1n1 source files exactly.

V3 passes 195 local host regressions, exact early m1n1 startup emulation and
matching systemd, headless Plasma and graphical desktop/input VM checks, including
all five report pages. The [preparation receipt](evidence/ssd-buffers-v3-preparation-20260925.json)
keeps those checks separate from the pending native result. VMs do not execute
the Neo's m1n1/SART/mailbox path and cannot replace native tests.

## Upstream comparison

On 2026-09-25, the NVMe and RTKit files in this checkout were compared with
official m1n1 `main` at `4184923ffb2dff079b384d6a32cc02142aa14572` and Linux
`asahi-wip` at `94fb23346d522edf53722357c426a3e58030beea`. All four files match
byte-for-byte. m1n1 already includes the M4 split NVMMU/NVMe resource handling
and additional I/O-queue address writes. This check found no newer change in
those files to import before the native buffer test; it does not rule out work
on other developer branches. Exact source links and hashes are in the
[comparison receipt](evidence/upstream-comparison-20260925.json).
