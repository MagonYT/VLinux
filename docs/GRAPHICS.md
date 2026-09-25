# Graphics acceleration investigation

The current VLinux desktop uses the firmware framebuffer and software rendering.
Native KDE proves that the display path works; it does not establish GPU command
submission or acceleration.

## Observed hardware and source gap

A read-only registry capture on the development Neo, running macOS 26.5.2,
identified the active class `AGXAcceleratorG17P` and bundle `com.apple.AGXG17P`.
The installed accelerator and its G17P RTBuddy firmware bundle report version
351.2. Only fixed driver metadata and file hashes were collected; no accelerator
user client was opened or firmware copied. See the
[sanitized evidence](evidence/neo-graphics-20260925.json).

The prepared Linux source's `drivers/gpu/drm/asahi/hw/mod.rs` defines G13/G14
configurations, and `driver.rs` matches M1/M2 SoCs with specific firmware ABIs.
There is no t8140 match or G17P hardware configuration. The m1n1 GPU setup also
rejects unsupported chips. The native DT does not add a GPU node, and the tested
kernel enables simpledrm with no enabled `CONFIG_DRM_ASAHI` option. Adding a
compatible string or enabling that config option would not fill these gaps.

The official source files checked on 2026-09-25 still match these local files:
[Linux GPU configurations](https://github.com/AsahiLinux/linux/blob/94fb23346d522edf53722357c426a3e58030beea/drivers/gpu/drm/asahi/hw/mod.rs)
and [m1n1 GPU setup](https://github.com/AsahiLinux/m1n1/blob/4184923ffb2dff079b384d6a32cc02142aa14572/src/kboot_gpu.c).
This is a comparison at those exact revisions, not a claim about every developer
branch or work that has not been published.

## Practical porting milestones

1. Establish the G17P register, memory-translation and firmware interfaces using
   controlled traces. macOS driver metadata identifies the target but cannot
   establish those protocols.
2. Implement bootloader resource handoff and a kernel hardware configuration,
   including firmware startup, address-space handling, queues, completion and
   fault recovery. Start with a bounded command and verified output.
3. Establish userspace compiler and command-stream support for this GPU. A
   render node alone is not enough; a rendered result and API conformance tests
   must distinguish GPU execution from software fallback.
4. Integrate rendering with the display/compositor and then measure performance,
   stability and power. Keep the existing framebuffer desktop as a fallback.

Asahi's [GPU architecture overview](https://asahilinux.org/2022/12/gpu-drivers-now-in-asahi-linux/)
describes the kernel/userspace split. The newer
[progress report](https://asahilinux.org/2026/08/progress-report-7-2/)
also explains why firmware ABI matching and display-buffer sharing require work
beyond successful GPU rendering. Those reports do not establish Neo GPU support.

The diagnostics batch adds a report of DRM devices and render nodes. It does not
enable acceleration. SSD access and a usable development link remain more useful
near-term milestones for bringing this larger port up efficiently.
