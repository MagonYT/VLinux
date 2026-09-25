# Contributing to VLinux

The pinned source patches and host test are now available. Start with
[development](docs/DEVELOPMENT.md) and [hardware status](docs/HARDWARE.md).
Useful contributions include:

- **Native test results.** Include the exact build ID, enrollment outcome,
  last checkpoint and relevant diagnostic lines. Keep a working boot fallback.
- **Source and tests.** Small driver changes, bounded fault tests, or improvements
  that make the build independent of the local development workspace.
- **Research.** Findings about Neo SoC blocks or peripherals, with primary sources
  and a clear distinction between observation and inference.
- **Docs.** Corrections and additions to `docs/`.

Kernel patches need a `Signed-off-by:`
line ([Developer Certificate of Origin](https://developercertificate.org/))
and must follow the kernel's coding style.

Keep native-device evidence separate from simulated host and VM results. Do not
attach complete macOS dumps, firmware, private identifiers or recovery logs.
