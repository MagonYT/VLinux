#!/usr/bin/bash
set -euo pipefail
[[ ! -f /run/vlinux-test-center/launchers-installed ]] || exit 0
[[ $(id -u alarm) == 1000 ]]
install -d -o alarm -g alarm /home/alarm/.local/share/applications /home/alarm/Desktop
for file in /etc/vlinux/test-center/apps/*.desktop; do
    install -m 755 -o alarm -g alarm "$file" /home/alarm/.local/share/applications/
done
install -m 755 -o alarm -g alarm /etc/vlinux/test-center/apps/vlinux-test-center.desktop /home/alarm/Desktop/
mkdir -p /run/vlinux-test-center
: > /run/vlinux-test-center/launchers-installed
