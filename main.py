
import sys
import subprocess
import winreg
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QLineEdit, QPushButton, QCheckBox, QComboBox,
    QTextEdit, QGridLayout, QVBoxLayout, QHBoxLayout,
    QGroupBox, QMessageBox, QSystemTrayIcon, QMenu, QInputDialog, QStyle,
    QSizePolicy
)
from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap

if getattr(sys, "frozen", False):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).resolve().parent

TOOLS = ROOT / "tools"
ADB = TOOLS / "adb.exe"
SCRCPY = TOOLS / "scrcpy.exe"
REGISTRY_KEY = r"Software\KiraMirror"
OLD_REGISTRY_KEY = r"Software\KiraScrcpy"


class KiraMirror(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kira Mirror")
        logo_path = ROOT / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.resize(850, 650)
        self.proc = None
        self._really_quit = False
        self.log_entries = []
        self.tray = None
        self.status_timer = None

        self.create_interface()
        self.load_settings()
        self.setup_tray()
        self.setup_status_timer()
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #11151d;
                color: #e8edf5;
                font-family: Segoe UI;
                font-size: 10pt;
            }
            QGroupBox {
                border: 1px solid #344256;
                border-radius: 9px;
                margin-top: 12px;
                padding: 12px;
                color: #76d7c4;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QTextEdit {
                background: #1b2330;
                border: 1px solid #3b485c;
                border-radius: 6px;
                padding: 8px;
                color: white;
            }
            QPushButton {
                background: #246b65;
                color: white;
                border: none;
                border-radius: 7px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2f8b80;
            }
        """)

    def create_interface(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        logo_path = ROOT / "logo.png"
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path))
            logo_label.setPixmap(
                pixmap.scaledToHeight(80, Qt.SmoothTransformation)
            )
            logo_label.setAlignment(Qt.AlignHCenter)
            layout.addWidget(logo_label)

        title = QLabel("KIRA MIRROR")
        title.setStyleSheet(
            "font-size: 25pt; font-weight: bold; color: #76d7c4;"
        )
        title.setAlignment(Qt.AlignHCenter)
        layout.addWidget(title)

        connection = QGroupBox("Wireless Connection")
        grid = QGridLayout(connection)

        self.ip = QLineEdit()
        self.ip.setPlaceholderText("192.168.1.100")

        self.pair_port = QLineEdit()
        self.pair_port.setPlaceholderText("Pairing Port")

        self.code = QLineEdit()
        self.code.setPlaceholderText("Pairing Code")

        self.port = QLineEdit()
        self.port.setPlaceholderText("Connect Port")

        grid.addWidget(QLabel("IP Address"), 0, 0)
        grid.addWidget(self.ip, 0, 1)
        grid.addWidget(QLabel("Connect Port"), 0, 2)
        grid.addWidget(self.port, 0, 3)

        grid.addWidget(QLabel("Pairing Code"), 1, 0)
        grid.addWidget(self.code, 1, 1)
        grid.addWidget(QLabel("Pairing Port"), 1, 2)
        grid.addWidget(self.pair_port, 1, 3)

        pair = QPushButton("Pair Device")
        pair.clicked.connect(self.pair_device)

        connect = QPushButton("Connect")
        connect.clicked.connect(self.connect_device)

        disconnect = QPushButton("Disconnect")
        disconnect.clicked.connect(self.disconnect_device)

        detect = QPushButton("Detect Devices")
        detect.clicked.connect(self.detect_devices)

        check = QPushButton("Check Status")
        check.clicked.connect(self.refresh_status)

        self.status_label = QLabel("Status: Unknown")
        self.status_label.setStyleSheet("color: #f1c40f; font-weight: bold;")

        grid.addWidget(pair, 2, 0, 1, 2)
        grid.addWidget(connect, 2, 2)
        grid.addWidget(disconnect, 2, 3)
        grid.addWidget(detect, 3, 0, 1, 2)
        grid.addWidget(check, 3, 2)
        grid.addWidget(self.status_label, 3, 3)

        layout.addWidget(connection)

        settings = QGroupBox("Display Settings")
        sg = QGridLayout(settings)

        self.screen_off = QCheckBox("Turn Screen Off")
        self.screen_off.setChecked(True)

        self.stay_awake = QCheckBox("Stay Awake")
        self.stay_awake.setChecked(True)

        self.no_audio = QCheckBox("Disable Audio")
        self.no_audio.setChecked(True)

        self.fullscreen = QCheckBox("Fullscreen")

        self.fps = QComboBox()
        self.fps.addItems(["30", "60", "90", "120"])
        self.fps.setCurrentText("60")

        self.bitrate = QComboBox()
        self.bitrate.addItems(["4M", "8M", "12M", "16M", "24M"])
        self.bitrate.setCurrentText("8M")

        sg.addWidget(self.screen_off, 0, 0)
        sg.addWidget(self.stay_awake, 0, 1)
        sg.addWidget(self.no_audio, 1, 0)
        sg.addWidget(self.fullscreen, 1, 1)
        sg.addWidget(QLabel("FPS"), 2, 0)
        sg.addWidget(self.fps, 2, 1)
        sg.addWidget(QLabel("Bitrate"), 2, 2)
        sg.addWidget(self.bitrate, 2, 3)

        layout.addWidget(settings)

        buttons = QHBoxLayout()

        start = QPushButton("START SCRCPY")
        start.clicked.connect(self.start_scrcpy)

        stop = QPushButton("STOP SCRCPY")
        stop.clicked.connect(self.stop_scrcpy)

        buttons.addWidget(start)
        buttons.addWidget(stop)
        layout.addLayout(buttons)

        logs = QGroupBox("Activity Log")
        log_layout = QHBoxLayout(logs)

        self.output = QTextEdit()
        self.output.setReadOnly(True)

        log_buttons = QVBoxLayout()
        copy_log = QPushButton("Copy")
        copy_log.clicked.connect(self.copy_log)
        copy_log.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        clear_log = QPushButton("Clear")
        clear_log.clicked.connect(self.clear_log)
        clear_log.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        log_buttons.addWidget(copy_log)
        log_buttons.addWidget(clear_log)

        log_layout.addWidget(self.output, 1)
        log_layout.addLayout(log_buttons)
        layout.addWidget(logs)

        self.log("Welcome to Kira Mirror.")

    def log(self, message, level="info"):
        text = str(message)
        if level == "info":
            lower = text.lower()
            if any(
                word in lower
                for word in [
                    "error", "failed", "cannot", "could not", "not found",
                    "refused", "unauthorized", "exception", "timed out"
                ]
            ):
                level = "error"
            elif any(word in lower for word in ["warn", "warning", "offline"]):
                level = "warn"
        self.log_entries.append({"text": text, "level": level})
        self.render_logs()

    def render_logs(self):
        if not hasattr(self, "output"):
            return
        filter_text = ""
        if hasattr(self, "log_filter"):
            filter_text = self.log_filter.text().strip().lower()
        self.output.clear()
        for entry in self.log_entries:
            text = entry["text"]
            if filter_text and filter_text not in text.lower():
                continue
            if entry["level"] == "error":
                color = "#ff6b6b"
            elif entry["level"] == "warn":
                color = "#f1c40f"
            else:
                color = "#e8edf5"
            escaped = (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            self.output.append(f'<span style="color:{color};">{escaped}</span>')

    def copy_log(self):
        QApplication.clipboard().setText(self.output.toPlainText())
        self.log("Log copied to clipboard.")

    def clear_log(self):
        self.log_entries.clear()
        self.render_logs()

    def run_adb(self, args):
        if not ADB.exists():
            QMessageBox.warning(
                self, "Error",
                "adb.exe not found inside tools folder."
            )
            return ""

        try:
            result = subprocess.run(
                [str(ADB)] + args,
                capture_output=True,
                text=True,
                timeout=25
            )
            output = (result.stdout or "") + (result.stderr or "")
            self.log(output.strip() or "ADB command completed.")
            return output
        except Exception as error:
            self.log(str(error))
            return ""

    def address(self, field):
        ip = self.ip.text().strip()
        port = field.text().strip()

        if not ip or not port:
            QMessageBox.warning(
                self, "Missing Information",
                "Enter IP address and port."
            )
            return None

        if ":" in ip or any(c.isspace() for c in ip):
            QMessageBox.warning(self, "Invalid IP", "Enter IP only.")
            return None

        if not port.isdigit() or not 1 <= int(port) <= 65535:
            QMessageBox.warning(self, "Invalid Port", "Invalid port number.")
            return None

        return f"{ip}:{port}"

    def pair_device(self):
        address = self.address(self.pair_port)
        code = self.code.text().strip()

        if not address or not code:
            return

        self.log("Pairing device...")
        self.run_adb(["pair", address, code])

    def connect_device(self):
        address = self.address(self.port)
        if address:
            self.log("Connecting...")
            self.run_adb(["connect", address])

    def disconnect_device(self):
        address = self.address(self.port)
        if address:
            self.run_adb(["disconnect", address])
            self.refresh_status()

    def detect_devices(self):
        output = self.run_adb(["devices", "-l"])
        devices = []
        for line in output.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("list of devices"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                devices.append(f"{parts[0]}  [{parts[1]}]")
        if not devices:
            QMessageBox.information(self, "Devices", "No ADB devices found.")
            self.refresh_status()
            return

        choice, ok = QInputDialog.getItem(
            self, "Detect Devices", "Select a device:", devices, 0, False
        )
        if not ok or not choice:
            return

        serial = choice.split()[0]
        if ":" in serial and "._" not in serial:
            ip, port = serial.rsplit(":", 1)
            self.ip.setText(ip)
            self.port.setText(port)
            self.log(f"Selected wireless device: {serial}")
        else:
            resolved = self.resolve_mdns_device(serial)
            if resolved:
                ip, port = resolved.rsplit(":", 1)
                self.ip.setText(ip)
                self.port.setText(port)
                self.log(f"Selected device: {serial} -> {resolved}")
            else:
                self.ip.setText(serial)
                self.log(
                    f"Selected device: {serial}. "
                    "Could not auto-fill IP/Port; enter them manually if needed.",
                    "warn",
                )
        self.refresh_status()

    def resolve_mdns_device(self, serial):
        try:
            result = subprocess.run(
                [str(ADB), "mdns", "services"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = (result.stdout or "") + (result.stderr or "")
        except Exception as error:
            self.log(f"Could not read mDNS services: {error}", "warn")
            return None

        serial_name = serial.split("._")[0]
        for line in output.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("list of discovered"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            instance, service, address = parts[0], parts[1], parts[2]
            if instance == serial_name or serial.startswith(instance):
                if ":" in address:
                    return address
        return None

    def refresh_status(self):
        if not hasattr(self, "status_label"):
            return
        if not ADB.exists():
            self.status_label.setText("Status: ADB missing")
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
            return

        try:
            result = subprocess.run(
                [str(ADB), "devices"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = (result.stdout or "") + (result.stderr or "")
        except Exception as error:
            self.status_label.setText("Status: Error")
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
            self.log(f"Status check failed: {error}", "error")
            return

        target = ""
        ip = self.ip.text().strip()
        port = self.port.text().strip()
        if ip and port:
            target = f"{ip}:{port}"

        connected = False
        for line in output.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("list of devices"):
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                if not target or parts[0] == target:
                    connected = True
                    if not target:
                        target = parts[0]
                    break

        scrcpy_running = self.proc is not None and self.proc.state() != QProcess.NotRunning
        if connected:
            text = f"Status: Connected ({target})"
            if scrcpy_running:
                text += " | Scrcpy running"
            self.status_label.setText(text)
            self.status_label.setStyleSheet("color: #2ecc71; font-weight: bold;")
        else:
            text = "Status: Disconnected"
            if scrcpy_running:
                text += " | Scrcpy running"
            self.status_label.setText(text)
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")

    def setup_status_timer(self):
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(8000)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start()
        self.refresh_status()

    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.log("System tray is not available on this system.", "warn")
            return

        icon = self.windowIcon()
        if icon.isNull():
            icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)

        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("Kira Mirror")

        menu = QMenu(self)
        show_action = QAction("Show/Hide", self)
        show_action.triggered.connect(self.toggle_window_visibility)
        connect_action = QAction("Connect", self)
        connect_action.triggered.connect(self.connect_device)
        start_action = QAction("Start Scrcpy", self)
        start_action.triggered.connect(self.start_scrcpy)
        stop_action = QAction("Stop Scrcpy", self)
        stop_action.triggered.connect(self.stop_scrcpy)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)

        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(connect_action)
        menu.addAction(start_action)
        menu.addAction(stop_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_window_visibility()

    def toggle_window_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def quit_app(self):
        self._really_quit = True
        self.close()

    def start_scrcpy(self):
        if not SCRCPY.exists():
            QMessageBox.warning(
                self, "Error",
                "scrcpy.exe not found inside tools folder."
            )
            return

        address = self.address(self.port)
        if not address:
            return

        args = [
            "-s", address,
            "--max-fps", self.fps.currentText(),
            "--video-bit-rate", self.bitrate.currentText()
        ]

        if self.screen_off.isChecked():
            args.append("--turn-screen-off")

        if self.stay_awake.isChecked():
            args.append("--stay-awake")

        if self.no_audio.isChecked():
            args.append("--no-audio")

        if self.fullscreen.isChecked():
            args.append("--fullscreen")

        self.stop_scrcpy()

        self.proc = QProcess(self)
        self.proc.setProgram(str(SCRCPY))
        self.proc.setArguments(args)
        self.proc.readyReadStandardOutput.connect(
            self.read_output
        )
        self.proc.readyReadStandardError.connect(
            self.read_error
        )
        self.proc.start()

        if self.proc.waitForStarted(3000):
            self.log("Scrcpy started successfully.")
        else:
            self.log("Could not start scrcpy.")
        self.refresh_status()

    def read_output(self):
        if self.proc:
            data = bytes(
                self.proc.readAllStandardOutput()
            ).decode(errors="replace").strip()
            if data:
                self.log(data)

    def read_error(self):
        if self.proc:
            data = bytes(
                self.proc.readAllStandardError()
            ).decode(errors="replace").strip()
            if data:
                self.log(data)

    def stop_scrcpy(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.terminate()
            if not self.proc.waitForFinished(2000):
                self.proc.kill()
            self.log("Scrcpy stopped.")

        self.proc = None
        self.refresh_status()

    def load_settings(self):
        for reg_key in (REGISTRY_KEY, OLD_REGISTRY_KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key) as key:
                    found = False
                    for field, widget in (("ip", self.ip), ("connect_port", self.port)):
                        try:
                            value, _ = winreg.QueryValueEx(key, field)
                        except FileNotFoundError:
                            continue
                        if isinstance(value, str):
                            widget.setText(value)
                            found = True
                    if found:
                        return
            except FileNotFoundError:
                continue
            except Exception as error:
                self.log(f"Could not load settings: {error}")
                return

    def save_settings(self):
        data = {
            "ip": self.ip.text().strip(),
            "connect_port": self.port.text().strip(),
        }
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY) as key:
                for name, value in data.items():
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        except Exception as error:
            self.log(f"Could not save settings: {error}")

    def closeEvent(self, event):
        self.save_settings()
        if self.tray and self.tray.isVisible() and not self._really_quit:
            self.hide()
            self.tray.showMessage(
                "Kira Mirror",
                "Application is still running in the system tray.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            event.ignore()
            return

        self.stop_scrcpy()
        if self.tray:
            self.tray.hide()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KiraMirror()
    window.show()
    sys.exit(app.exec())
