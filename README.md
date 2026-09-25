# VLinux | Arch Linux on MacBook Neo

<img src="assets/branding/vlinux-logo.png" alt="VLinux" width="220">

Experimental native Linux bring-up for **MacBook Neo / J700 / A18 Pro (t8140)**,
based on m1n1 and the Asahi Linux kernel with Arch Linux ARM and KDE Plasma.

**Native Arch/KDE, the built-in keyboard, and trackpad scrolling/gestures have
been reported working. Internal SSD access and networking are still in development.**
The desktop currently boots from a RAM filesystem and does not persist changes.

The current SSD diagnostic has reached RTKit service discovery and photographed
a 32 KiB crashlog buffer request. The first shared-buffer test exposed a memory
configuration mismatch, now corrected with a reproducing regression test;
native buffer acceptance remains pending. See [hardware status](docs/HARDWARE.md) and
[the SSD work](docs/SSD.md) for the distinction between native and automated evidence.

## Source and tools

This repository contains pinned, hash-checked patch sets for m1n1 and the Linux
kernel, the native kernel configuration and device-tree overlays, a host fault
test, hardware inventory tools, and the Test Center UI. Upstream sources are
fetched into an ignored `src/` directory:

```sh
python3 scripts/prepare-sources.py --component m1n1
python3 scripts/ssd/test-buffers.py --output build/ssd-buffers-check
```

The source preparation command refuses to overwrite an existing checkout that
has different contents. See [development](docs/DEVELOPMENT.md) for dependencies,
Linux source preparation, tests and build limitations.

This is a development source release, not an installer or a downloadable boot
image. The locally tested boot packages depend on private build artifacts and
firmware obtained from the machine's own macOS installation; those are not
included here. The source preparation and host test commands do not enroll a
kernel, reboot a machine, or issue native SSD-controller commands.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Hardware support](docs/HARDWARE.md)
- [SSD bring-up](docs/SSD.md)
- [Wi-Fi and Bluetooth identity and porting path](docs/NETWORK.md)
- [Touch ID investigation and read-only scanner](docs/TOUCH-ID.md)
- [Development and validation](docs/DEVELOPMENT.md)
- [Source provenance and licenses](docs/SOURCES.md)
- [Contributing](CONTRIBUTING.md)

VLinux is experimental. Keep a working macOS installation and a known-good boot
fallback when testing hardware changes. VLinux is not affiliated with Apple,
Asahi Linux or Arch Linux ARM.

## AI disclosure

AI tools were used during VLinux's development, mainly as a reference and
guide. They helped with debugging, explained unfamiliar kernel and hardware
behaviour, and drafted some code. Every piece of AI-assisted code was
reviewed by hand, and much of it was rewritten to fit the project's design
and the kernel's conventions.

## License

Project tooling and documentation use the existing [Apache License 2.0](LICENSE),
unless a file says otherwise. m1n1 patches retain its MIT license; Linux patches
retain their upstream GPL/SPDX terms, including dual-licensed device trees.
See [source provenance](docs/SOURCES.md) and `LICENSES/`.
