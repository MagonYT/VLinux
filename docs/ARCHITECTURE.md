# Architecture

The native prototype boots through Apple's custom-kernel enrollment into a
modified m1n1 payload. m1n1 preserves live firmware memory, prepares the Linux
device tree and hands off directly to the bundled Linux kernel and initramfs:

```text
Apple boot firmware / enrolled custom kernel
  -> modified m1n1
     -> Linux (16 KiB pages, Neo device tree)
        -> RAM initramfs and compressed Arch Linux ARM root
           -> systemd -> SDDM/Xorg -> KDE Plasma
```

U-Boot and an EFI bootloader are possible later stages, but are not part of the
currently demonstrated native path. The working desktop runs with one CPU
(`maxcpus=1`); multicore operation has not been established.

The current SSD diagnostics run inside m1n1 before the Linux handoff. They retain
firmware and private memory, perform bounded guarded operations, print results,
and intentionally hold for a photograph. That result is separate from the
working RAM desktop. No native SSD-backed root has been demonstrated.

## Repository layout

- `sources.lock.json`: upstream revisions, patch hashes and reconstructed file hashes.
- `patches/m1n1/`: boot, memory preservation, input handoff and SSD experiments.
- `patches/linux-asahi/`: Neo DT, input/DART/RTKit and limited SMC bring-up.
- `kernel/config/`: configuration from the tested RAM desktop kernel.
- `kernel/dts/`: input and trackpad overlays used during native bring-up.
- `scripts/prepare-sources.py`: fetch pinned sources and apply patches without replacing existing work.
- `scripts/ssd/`, `tests/fixtures/`: host fault test with minimal non-identifying metadata.
- `scripts/test-center/`: Hardware, SSD, Network, Input and Boot Logs UI.
- `tools/input-monitor.c`: Linux input-event counter; it does not record key values.

Generated sources, binaries, private firmware, raw device dumps and boot receipts
stay outside version control. The existing local enrollment workflow is specific
to the development machine and is not distributed as a general installation tool.
