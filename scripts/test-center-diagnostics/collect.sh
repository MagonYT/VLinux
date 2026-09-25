#!/usr/bin/bash
# Read the running Linux system. No device commands, mounts, connections or raw I/O.
set -euo pipefail
umask 022
out=/run/vlinux-test-center
mkdir -p "$out"

value() { if [[ -r $1 ]]; then tr -d '\000' < "$1"; else printf 'unavailable'; fi; }
driver() {
    local path
    path=$(readlink -f "$1" 2>/dev/null) || { printf 'unbound'; return; }
    while [[ $path == /sys/* ]]; do
        if [[ -L $path/driver ]]; then
            path=$(readlink "$path/driver"); printf '%s' "${path##*/}"; return
        fi
        path=${path%/*}
    done
    printf 'unbound'
}
heading() { printf '%s\n\n' "$1"; }
hardware() {
    heading 'HARDWARE IDENTIFICATION'
    printf 'Firmware model: '; value /sys/firmware/devicetree/base/model; printf '\n'
    printf 'Firmware compatibility: '
    if [[ -r /sys/firmware/devicetree/base/compatible ]]; then
        tr '\000' ' ' < /sys/firmware/devicetree/base/compatible
    else printf 'unavailable'; fi
    printf '\nKernel: %s\n' "$(uname -srmo)"
    printf 'Online CPU IDs: '; value /sys/devices/system/cpu/online; printf '\n'
    awk '/MemTotal/ {printf "Memory available to Linux: %.2f GiB\n", $2/1048576}' /proc/meminfo
    printf 'Root: %s\n\n' "$(findmnt -n -o SOURCE,FSTYPE /)"
    printf 'The firmware model describes this boot. Driver binding below means Linux\nattached a driver; it does not prove every function works.\n\n'
    printf 'INPUT DEVICES\n'
    local node found=0
    for node in /sys/class/input/event*; do
        [[ -r $node/device/name ]] || continue
        found=1
        printf '%s: %s | driver: %s\n' "${node##*/}" "$(value "$node/device/name")" "$(driver "$node/device")"
    done
    (( found )) || printf 'No input event devices detected.\n'
    printf '\nDISPLAY\n'
    for node in /sys/class/graphics/fb[0-9]*; do
        [[ -d $node ]] || continue
        printf '%s: %s | size: %s | driver: %s\n' "${node##*/}" "$(value "$node/name")" "$(value "$node/virtual_size")" "$(driver "$node/device")"
    done
    printf 'DRM render nodes: '
    if compgen -G '/dev/dri/renderD*' >/dev/null; then printf '%s ' /dev/dri/renderD*; printf '\n'; else printf 'none detected\n'; fi
    printf '\nLINUX DEVICE BINDINGS\n'
    for node in /sys/bus/platform/devices/* /sys/bus/pci/devices/* /sys/bus/hid/devices/*; do
        [[ -d $node ]] || continue
        printf '%s | %s' "${node##*/}" "$(driver "$node")"
        if [[ -r $node/of_node/compatible ]]; then
            printf ' | '; tr '\000' ' ' < "$node/of_node/compatible"
        fi
        printf '\n'
    done
}
ssd() {
    heading 'SSD DISCOVERY / BOOTLOADER SNAPSHOT'
    printf 'This build still boots its Arch root from RAM.\nThe register probe does not create an SSD block device.\n\n'
    printf 'LINUX BLOCK DEVICES\n'
    # These columns use sysfs; deliberately avoid filesystem probing/blkid.
    lsblk -o NAME,TYPE,SIZE,RO,MOUNTPOINTS 2>&1 || true
    local node found=0
    for node in /sys/class/nvme/nvme*; do
        [[ -d $node ]] || continue
        found=1
        printf '\nController %s: model=%s state=%s driver=%s\n' "${node##*/}" "$(value "$node/model")" "$(value "$node/state")" "$(driver "$node")"
    done
    (( found )) || printf '\nNo NVMe controller registered with Linux.\n'
    printf '\nM1N1 REPORT\n'
    if [[ -r /run/vlinux-ssd/report.log ]]; then cat /run/vlinux-ssd/report.log
    else printf 'SSD report service has not produced a report. Check Boot Logs.\n'; fi
}
network() {
    heading 'NETWORK DISCOVERY'
    printf 'Interfaces and bound drivers only. No connection attempts.\n\n'
    ip -brief link 2>&1 || true
    ip -brief address 2>&1 || true
    local node found=0
    for node in /sys/class/net/*; do
        [[ -d $node && ${node##*/} != lo ]] || continue
        found=1
        printf '\n%s: state=%s driver=%s\n' "${node##*/}" "$(value "$node/operstate")" "$(driver "$node/device")"
    done
    (( found )) || printf '\nNo non-loopback network interface detected.\n'
    printf '\nAn interface or driver is not evidence of working Internet access.\n'
}
input() {
    heading 'INPUT DEVICES / EVENT ACTIVITY'
    printf 'Command maps to Super/Meta; Option maps to Alt.\nUse the input pad above to test clicks, scrolling and modifier keys.\n\n'
    cat /proc/bus/input/devices
    printf '\nLATEST DIAGNOSTICS (activity counts, no saved keystrokes)\n'
    tail -n 35 /run/vlinux-input/report.log 2>/dev/null || true
    printf '\nTRACKPAD CAPTURE\n'
    tail -n 30 /run/vlinux-input/batch.log 2>/dev/null || true
}
logs() {
    heading 'BOOT LOGS'
    printf 'Services:\n'
    systemctl --no-pager --plain list-units 'vlinux-*' 2>&1 || true
    printf '\nRECENT KERNEL MESSAGES\n'
    dmesg --color=never 2>&1 | tail -n 160 || true
}
details() {
    heading 'POWER, USB AND GRAPHICS DISCOVERY'
    printf 'Read-only Linux metadata. Device presence and driver binding do not\nprove a feature works. Missing nodes mean this boot has not exposed them.\n\n'
    local node found=0
    printf 'BATTERY / POWER SUPPLIES\n'
    for node in /sys/class/power_supply/*; do
        [[ -d $node ]] || continue
        found=1
        printf '%s: type=%s status=%s capacity=%s%% | driver=%s\n' "${node##*/}" \
            "$(value "$node/type")" "$(value "$node/status")" "$(value "$node/capacity")" "$(driver "$node/device")"
    done
    (( found )) || printf 'No battery or power supply exposed by Linux.\n'
    printf '\nTHERMAL SENSORS (raw millidegrees Celsius)\n'
    found=0
    for node in /sys/class/thermal/thermal_zone*; do
        [[ -d $node ]] || continue
        found=1
        printf '%s: %s temp=%s\n' "${node##*/}" "$(value "$node/type")" "$(value "$node/temp")"
    done
    (( found )) || printf 'No thermal zones exposed by Linux.\n'
    printf '\nBACKLIGHT\n'
    found=0
    for node in /sys/class/backlight/*; do
        [[ -d $node ]] || continue
        found=1
        printf '%s: brightness=%s max=%s\n' "${node##*/}" "$(value "$node/actual_brightness")" "$(value "$node/max_brightness")"
    done
    (( found )) || printf 'No controllable backlight exposed by Linux.\n'
    printf '\nUSB DEVICES (no serial numbers)\n'
    found=0
    for node in /sys/bus/usb/devices/*; do
        [[ -r $node/idVendor && -r $node/idProduct ]] || continue
        found=1
        printf '%s: vendor=%s product=%s speed=%s Mbit/s | driver=%s\n' "${node##*/}" \
            "$(value "$node/idVendor")" "$(value "$node/idProduct")" "$(value "$node/speed")" "$(driver "$node")"
    done
    (( found )) || printf 'No USB device descriptors exposed by Linux.\n'
    printf '\nGRAPHICS\n'
    found=0
    for node in /sys/class/drm/card[0-9]*; do
        [[ -d $node && -e $node/device ]] || continue
        found=1
        printf '%s: driver=%s\n' "${node##*/}" "$(driver "$node/device")"
    done
    (( found )) || printf 'No DRM card exposed by Linux.\n'
    if compgen -G '/dev/dri/renderD*' >/dev/null; then
        printf 'Render devices: %s\n' /dev/dri/renderD*
        printf 'A render node does not prove applications use hardware acceleration.\n'
    else
        printf 'No render device: this boot exposes no GPU rendering interface.\n'
    fi
    printf 'A working framebuffer/KDE display alone does not prove GPU acceleration.\n'
    printf '\nDEFERRED DRIVER PROBES\n'
    if [[ -r /sys/kernel/debug/devices_deferred ]]; then
        head -n 60 /sys/kernel/debug/devices_deferred
    else
        printf 'Deferred-probe list unavailable; debugfs was not mounted by this tool.\n'
    fi
    printf '\nVLINUX_DIAGNOSTICS_DETAILS_READY\n'
}
for report in hardware ssd network input logs details; do
    # Keep unchanged report text stable so a periodic refresh does not reset
    # selection/scrolling while the user photographs the SSD register pages.
    "$report" > "$out/$report.tmp"
    mv "$out/$report.tmp" "$out/$report.txt"
done
date -Iseconds > "$out/updated.txt"
echo VLINUX_TEST_CENTER_REPORTS_READY
