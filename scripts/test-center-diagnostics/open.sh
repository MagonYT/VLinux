#!/usr/bin/bash
set -euo pipefail
page=${1:-hardware}
case "$page" in hardware|ssd|network|input|logs|details) ;; *) exit 2 ;; esac
export QT_QUICK_BACKEND=software QT_QUICK_CONTROLS_STYLE=Basic
export QML_XHR_ALLOW_FILE_READ=1
exec /usr/lib/qt6/bin/qml /etc/vlinux/test-center/Main.qml -- "--page=$page"
