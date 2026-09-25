# Desktop diagnostics batch

The optional Test Center revision in `scripts/test-center-diagnostics/` adds a
sixth **Power & USB** page to Hardware, SSD, Network, Input and Boot Logs. It also
adds text-size controls, **Pause updates**, **Copy report** and **Reload report**.
Alt+1 through Alt+6 selects a page.

The new report reads Linux's existing battery/power-supply, thermal, backlight,
USB and DRM metadata. It explicitly reports missing interfaces. USB entries
show vendor/product IDs and speed without serial numbers. It reads the deferred
probe list only if already accessible; it does not mount debugfs. A bound driver
or a render node is not treated as proof that the hardware works.

Pause freezes automatic display refreshes. Switching pages or pressing Reload
still retrieves the current report; the background collector continues. Reports,
clipboard text and the current desktop remain in RAM and disappear on reboot.
The Input pad displays the current key/modifiers and click/scroll counts; the
background input diagnostics retain activity counts, not typed text.

## Candidate and validation

The locally prepared candidate has build ID `7772e6cf0aa14b71` and payload SHA-256
`3515e3509efb5a3bd83c6785a4d5b8432415134dd25d8ff86a2ef19c1fb306e0`.
It preserves the exact native-confirmed queue bootloader, kernel, device tree,
RAM root and input firmware. Only the three UI/collector assets, build label and
new page launcher are overlaid. Its inherited bootloader includes the existing
single power-domain enable; it sends no storage command or firmware buffer grant.

195 host regressions passed in the private packaging workspace. Matching
systemd, headless Plasma and graphical QEMU checks passed with clean shutdown.
All six actual report pages passed OCR identity checks and visual review;
virtual keyboard/mouse event checks passed. The VM used one CPU, 4 GiB, no disk
or NIC, and an Xorg modesetting override for its virtual display. It did not
exercise m1n1, the native device tree or physical input hardware. The controls
were rendered; their interaction is part of the pending native test.

The evidence summary and exact source hashes are in
[`evidence/diagnostics-preparation-20260925.json`](evidence/diagnostics-preparation-20260925.json).
The public repository's CI covers source preparation and host tests; it does not
reproduce the private boot-package VM checks.

The SSD report intentionally identifies queue bootloader build
`217398cacb607050`, while the window identifies the diagnostics overlay above.
The original hardware snapshot must keep the identity of the code that took it.
The separate SSD firmware-buffer candidate remains independently selectable.

## Native test

Check the window build ID first. Photograph Hardware and Power & USB, including
the lower USB/graphics sections. Exercise keyboard modifiers, pointer motion,
clicks, two-finger scrolling and previously working KDE gestures. Then try font
size, pause, copy and reload. Record absent interfaces as observations rather
than assuming the report collector has added driver support.

These files extend the existing private RAM desktop integration. They require
its report services and Qt 6 runtime and are not a standalone boot builder or
installer. No additional SSD, wireless, battery, GPU or Touch ID driver is
included in this UI revision.
