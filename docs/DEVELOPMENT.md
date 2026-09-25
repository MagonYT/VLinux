# Development

This snapshot exposes the source experiments and a repeatable host test. It does
not yet rebuild the entire enrolled Arch image from a clean checkout. The local
packaging workflow still depends on frozen RAM-root artifacts, extracted firmware
and private hardware evidence, none of which is included in this repository.

## Prepare sources

Requirements: Git and Python 3. m1n1's source helper fetches the exact upstream
revision, applies its checked patch and initializes the upstream artwork submodule:

```sh
python3 scripts/prepare-sources.py --component m1n1
python3 scripts/prepare-sources.py --component m1n1 --verify-only
```

For Linux, use a **case-sensitive filesystem**; its tree contains filenames that
collide on a default case-insensitive macOS volume:

```sh
python3 scripts/prepare-sources.py --component linux-asahi
```

`--directory PATH` chooses a parent directory other than `src/`. An existing
checkout is verified, never reset or overwritten. If a fetch is interrupted,
inspect that partial checkout or choose a new directory before trying again.
`sources.lock.json` records base revisions, patch digests and every selected
source file's expected SHA-256.

## Host checks

The buffer test needs Clang with AddressSanitizer and UndefinedBehaviorSanitizer.
On macOS it uses Homebrew LLVM when present; `--clang PATH` selects another Clang.
It runs ordinary host code with simulated MMIO, never the real storage controller.

```sh
python3 scripts/ssd/test-buffers.py --output build/ssd-buffers-check
cd scripts
python3 -m unittest test_driver_inventory
```

Choose a fresh output directory each time. The buffer test emits `result.json`
with source/fixture hashes, counts and its actual exit status. Its fixture contains
only the three relevant node paths and five non-identifying ADT properties.

The exported patches were independently applied to temporary Git indexes at the
pinned revisions. All 29 selected m1n1 files and 15 Linux files reconstructed
byte-for-byte. A fresh m1n1 checkout also passed the source helper and buffer test.
Linux reconstruction was checked through its Git objects; a fresh full kernel
build is not claimed for this source export.

## Bootloader build

m1n1 needs GNU Make, an AArch64 C toolchain, and Rust with the
`aarch64-unknown-none-softfloat` target. On macOS the Makefile uses LLVM/LLD.
The local buffer experiment used these flags:

```sh
gmake -C src/m1n1 -j4 \
  BOOT_TRACE=1 MMU_TRACE=1 INIT_TRACE=1 RAM_BOOT=1 HANDOFF_TRACE=1 \
  SSD_PROBE=1 SSD_POWER_PROBE=1 SSD_QUEUE_PROBE=1 SSD_IDENTIFY_PROBE=1 \
  SSD_FIRMWARE_PROBE=1 SSD_SERVICE_PROBE=1 SSD_BUFFER_PROBE=1
```

On Linux, `make` is normally GNU Make. Select a Rust compiler with the required
target installed through the `RUSTC` environment variable if needed. A successful
build alone does not produce an enrollable Arch image or establish native safety.
The buffer probe intentionally holds before the Linux handoff.

`kernel/config/neo-native.config` is copied from the tested RAM-desktop kernel.
The input/trackpad overlays in `kernel/dts/` include the patched upstream Apple
DTS files; they are not standalone DTBs. The kernel patch includes the small
Darwin initramfs host shim referenced by its Makefile; a complete portable macOS
kernel build environment is not supplied by this snapshot.

## Desktop tools

`scripts/test-center/` contains the QML UI, report collector and launch/install
helpers from the existing RAM desktop. Those helpers expect the development
image's `/etc/vlinux` layout, `alarm` account and generated desktop launchers.
They are source components, not a host-side installer.

`tools/input-monitor.c` is the Linux AArch64 trackpad event counter. It dynamically
uses libinput, checks the device name and bounds its run time. Its custom AArch64
entry point requires the matching Linux link setup; do not build it as an ordinary
macOS executable. The prebuilt monitor is intentionally excluded.

Keep native observations, host fault tests and QEMU desktop checks separate when
reporting results. The exact working fallback image must remain available during
hardware experiments.
