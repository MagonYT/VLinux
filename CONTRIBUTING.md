# Contributing to VLinux

Thanks for helping get Linux onto the MacBook Neo. The kernel source and
build tooling haven't been published yet, so for now the most useful
contributions are:

- **Hardware data.** If you own a MacBook Neo, the `ioreg` and
  `system_profiler` dumps described in [docs/HARDWARE.md](docs/HARDWARE.md)
  help most right now.
- **Research.** Anything you know about the Neo's boot security options,
  SoC blocks, or peripherals. Please open an issue.
- **Docs.** Corrections and additions to `docs/`.

Once the code is published, kernel patches will need a `Signed-off-by:`
line ([Developer Certificate of Origin](https://developercertificate.org/))
and must follow the kernel's coding style.
