# VLinux | Linux on MacBook Neo

A WIP beta to get Arch Linux running on a MacBook Neo.

> **Status: coming soon.** The kernel source and build tooling haven't been
> published yet. This repo holds the project overview for now. See
> [docs/HARDWARE.md](docs/HARDWARE.md) for what's being worked on.

## What is VLinux?

VLinux is a custom Linux kernel for the MacBook Neo. It builds on the
[Asahi Linux](https://asahilinux.org) work for Apple silicon and boots an
[Arch Linux ARM](https://archlinuxarm.org) (aarch64) userspace.

Planned components:

- **Kernel:** Apple silicon kernel tree plus MacBook Neo patches and a
  tuned config (16K pages, Apple SoC drivers)
- **Device trees:** hardware description for the MacBook Neo
- **Boot chain:** m1n1 → U-Boot → EFI bootloader → Linux
- **Root filesystem:** Arch Linux ARM image with the VLinux kernel and
  modules preinstalled

## Documentation

- [Architecture](docs/ARCHITECTURE.md): boot chain and planned layout
- [Hardware support](docs/HARDWARE.md): per-component status
- [Contributing](CONTRIBUTING.md)

## Disclaimer

This is experimental low-level software. Changing your Mac's boot security
settings and installing a third-party kernel can leave it unbootable until
it is restored from a second Mac via DFU. Back up your data first.

VLinux is not affiliated with Apple, Asahi Linux or Arch Linux ARM.

## License

[Apache License 2.0](LICENSE). Kernel patches and device trees will be
GPL-2.0, the same license as the Linux kernel.
