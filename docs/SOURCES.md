# Source provenance

The source export is anchored to these existing upstream revisions:

| Component | Upstream | Revision |
|---|---|---|
| m1n1 | `https://github.com/rusch95/m1n1.git` | `940439b9a407fbfc499bea933269219f3f62d4c7` |
| Linux | `https://github.com/AsahiLinux/linux.git` | `8de57da87a9b807b52d6844270aecf498559c9ed` |

The m1n1 base is a fork of the Asahi Linux project already used by the working
Neo prototype. The patches include the VLinux changes to boot tracing, memory
preservation, native handoff, input support and current SSD diagnostics.
`sources.lock.json` binds each patch to that base and records reconstructed file
hashes. Both patch sets were checked against their base Git objects.

The export includes selected source changes, not all differences in the original
development directory. OS metadata, local assistant instruction-file deletions,
vendored dependency caches and unrelated Linux filename-collision differences
were excluded. Upstream dependencies and artwork are obtained from their own
repositories. The patch snapshot is experimental; it does not imply every code
path has been exercised on the Neo.

The minimal SSD fixture contains compatibility strings, an empty `quiesced`
property, the SART version and three node paths. Full ADT/IORegistry dumps,
macOS/SPTM images, extracted firmware, physical-device photos, boot receipts,
APFS identifiers and built boot images are not part of this source release.

The VLinux logo was supplied by the project owner. Its ancillary provenance
metadata was removed for this repository; its dimensions and every compressed
pixel-data byte are unchanged. `assets/branding/source.json` records the exported
asset hash.

## Licensing

- The existing root Apache-2.0 license covers project tooling and documentation
  unless a file has different terms.
- m1n1 source and the patch retain the upstream MIT license and attribution;
  see `LICENSES/m1n1-MIT.txt`.
- Linux source changes retain the applicable upstream GPL/SPDX licenses;
  see `LICENSES/Linux-COPYING`, `LICENSES/GPL-2.0` and the syscall exception.
  Device trees carrying `GPL-2.0+ OR MIT` keep those dual-license terms.
- Fetching third-party source does not change its license. This repository does
  not distribute Apple firmware.
