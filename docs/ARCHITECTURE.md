# Architecture

VLinux follows the boot model that Asahi Linux established for Apple silicon
Macs, and reuses its kernel tree as a base.

## Boot chain

```
iBoot (Apple, in ROM/NOR)
  └─ m1n1 stage 1         installed as a "custom kernel" via kmutil in 1TR
       └─ m1n1 stage 2    turns the Apple device tree (ADT) into a Linux DT
            └─ U-Boot     provides a UEFI environment
                 └─ GRUB / systemd-boot (EFI)
                      └─ Linux (VLinux kernel, out/boot/Image + DTB)
                           └─ Arch Linux ARM userspace
```

| Stage       | Source                                   | VLinux status |
|-------------|------------------------------------------|---------------|
| m1n1        | https://github.com/AsahiLinux/m1n1       | Needs SoC support for the Neo's chip |
| U-Boot      | https://github.com/AsahiLinux/u-boot     | Needs the new DT |
| Kernel      | Asahi Linux tree + VLinux patches        | This repo (coming soon) |
| Userspace   | Arch Linux ARM aarch64 tarball           | This repo (coming soon) |

The biggest open question is stage 0: whether the MacBook Neo allows booting
a non-Apple kernel at all (the "Permissive Security" setting in the
Startup Security Utility that other Apple silicon Macs expose). Until that is
confirmed, everything downstream is preparation.

## Planned repository layout

```
kernel/config/   Kernel config for the MacBook Neo
kernel/patches/  Patch series applied on top of the base kernel tree
kernel/dts/      MacBook Neo device tree sources
scripts/         Kernel and rootfs build scripts
docs/            Project documentation
```

## Why 16K pages

Apple silicon's IOMMU (DART) works in 16K pages, so the kernel will be built with
`CONFIG_ARM64_16K_PAGES`. Almost all of Arch Linux ARM's userspace works
unmodified; a handful of packages that hard-code 4K pages (some builds of
jemalloc, for instance) may need rebuilding. Track those in the issue tracker.
