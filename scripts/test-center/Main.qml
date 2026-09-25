import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: app
    width: Math.min(Screen.width - 40, 1100)
    height: Math.min(Screen.height - 80, 760)
    minimumWidth: 760
    minimumHeight: 540
    visible: true
    title: "VLinux Test Center — " + buildId
    color: "#171c25"
    palette.window: "#171c25"
    palette.base: "#111620"
    palette.text: "#edf2fa"
    palette.windowText: "#edf2fa"
    palette.buttonText: "#edf2fa"
    palette.button: "#303b50"
    palette.highlight: "#77acff"
    font.pixelSize: 16
    property string buildId: "@BUILD_ID@"
    property var pages: ["hardware", "ssd", "network", "input", "logs"]
    property var labels: ["Hardware", "SSD", "Network", "Input", "Boot Logs"]
    property string reportText: "Waiting for hardware report…"
    property string updated: "Waiting for first snapshot"
    property int requestId: 0
    property int clicks: 0
    property int wheels: 0
    property string lastKey: "Click the pad, then press a key."

    function readFile(name, done) {
        const xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE)
                done((xhr.status === 0 || xhr.status === 200) ? xhr.responseText : "");
        };
        xhr.open("GET", "file:///run/vlinux-test-center/" + name);
        xhr.send();
    }
    function refresh() {
        const serial = ++requestId;
        readFile(pages[tabs.currentIndex] + ".txt", function(text) {
            if (serial !== requestId) return;
            const next = text || "Report unavailable. Open Boot Logs or wait for the next snapshot.";
            if (reportText !== next) reportText = next;
        });
        readFile("updated.txt", function(text) { if (text) updated = "Snapshot: " + text.trim(); });
    }
    Component.onCompleted: {
        for (let i = 0; i < pages.length; i++) {
            if (Qt.application.arguments.indexOf("--page=" + pages[i]) >= 0) tabs.currentIndex = i;
        }
        refresh();
        console.log("VLINUX_TEST_CENTER_WINDOW_READY " + buildId);
    }
    Timer { interval: 5000; running: true; repeat: true; onTriggered: app.refresh() }
    Shortcut { sequence: "Alt+1"; onActivated: tabs.currentIndex = 0 }
    Shortcut { sequence: "Alt+2"; onActivated: tabs.currentIndex = 1 }
    Shortcut { sequence: "Alt+3"; onActivated: tabs.currentIndex = 2 }
    Shortcut { sequence: "Alt+4"; onActivated: tabs.currentIndex = 3 }
    Shortcut { sequence: "Alt+5"; onActivated: tabs.currentIndex = 4 }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            Label { text: "VLinux Test Center"; font.pixelSize: 28; font.bold: true; Layout.fillWidth: true }
            Label { text: "SSD SUITE  /  " + app.buildId; color: "#96bdff"; font.pixelSize: 14 }
        }
        Label {
            text: "Hardware reports and input tests in one boot. Reports stay in RAM and are lost on reboot."
            color: "#b3bed0"; wrapMode: Text.WordWrap; Layout.fillWidth: true
        }
        TabBar {
            id: tabs
            Layout.fillWidth: true
            Repeater {
                model: app.labels
                TabButton { required property string modelData; text: modelData; implicitHeight: 44 }
            }
            onCurrentIndexChanged: { app.refresh(); if (report) report.cursorPosition = 0; }
        }
        Rectangle {
            id: pad
            visible: tabs.currentIndex === 3
            Layout.fillWidth: true
            Layout.preferredHeight: 100
            color: activeFocus ? "#243e5e" : "#263044"
            border.color: activeFocus ? "#96bdff" : "#4b5b76"
            radius: 8
            Keys.onPressed: function(event) {
                app.lastKey = "Key code: " + event.key + "  |  Super/Meta: " + !!(event.modifiers & Qt.MetaModifier)
                        + "  Alt: " + !!(event.modifiers & Qt.AltModifier) + "  Ctrl: " + !!(event.modifiers & Qt.ControlModifier)
                        + "  Shift: " + !!(event.modifiers & Qt.ShiftModifier);
                event.accepted = true;
            }
            Column {
                anchors.centerIn: parent; spacing: 8
                Label { text: "INPUT PAD   Clicks: " + app.clicks + "    Scroll events: " + app.wheels; font.bold: true }
                Label { text: app.lastKey; font.pixelSize: 14 }
                Label { text: "Scroll here with two fingers, or scroll the report below. KDE may consume system shortcuts."; color: "#bac9dd"; font.pixelSize: 13 }
            }
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
                onClicked: { app.clicks++; pad.forceActiveFocus(); }
                onWheel: function(wheel) { app.wheels++; wheel.accepted = true; }
            }
        }
        ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            TextArea {
                id: report
                text: app.reportText
                readOnly: true
                selectByMouse: true
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.Wrap
                font.family: "monospace"
                font.pixelSize: 15
                padding: 18
                background: Rectangle { color: "#111620"; radius: 8 }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: app.updated; color: "#b3bed0"; font.pixelSize: 13; Layout.fillWidth: true }
            Label { text: "Alt+1…5 switches pages"; color: "#b3bed0"; font.pixelSize: 13 }
            Button { text: "Reload report"; onClicked: app.refresh() }
        }
    }
}
