from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QPushButton, QMessageBox, QFrame
)
from PyQt6.QtCore import pyqtSignal
from database import get_setting, set_setting
from ui.theme import COLOR_AMBER_ALERT, COLOR_SLATE_SURFACE, COLOR_BORDER_BLUE

class GovernorWidget(QGroupBox):
    governor_settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("🛡️ SEND-RATE GOVERNOR — SAFETY & COMPLIANCE", parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(10)

        # Controls Row
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        v1 = QVBoxLayout()
        v1.setSpacing(4)
        lbl1 = QLabel("MIN DELAY (SEC):")
        lbl1.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        v1.addWidget(lbl1)
        self.spn_min_delay = QDoubleSpinBox()
        self.spn_min_delay.setRange(0.5, 60.0)
        self.spn_min_delay.setSingleStep(0.5)
        self.spn_min_delay.setValue(2.5)
        v1.addWidget(self.spn_min_delay)
        row1.addLayout(v1)

        v2 = QVBoxLayout()
        v2.setSpacing(4)
        lbl2 = QLabel("JITTER (±SEC):")
        lbl2.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        v2.addWidget(lbl2)
        self.spn_jitter = QDoubleSpinBox()
        self.spn_jitter.setRange(0.0, 30.0)
        self.spn_jitter.setSingleStep(0.5)
        self.spn_jitter.setValue(1.5)
        v2.addWidget(self.spn_jitter)
        row1.addLayout(v2)

        v3 = QVBoxLayout()
        v3.setSpacing(4)
        lbl3 = QLabel("DAILY CAP (SENDS):")
        lbl3.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        v3.addWidget(lbl3)
        self.spn_daily_cap = QSpinBox()
        self.spn_daily_cap.setRange(1, 10000)
        self.spn_daily_cap.setValue(800)
        v3.addWidget(self.spn_daily_cap)
        row1.addLayout(v3)

        btn_save = QPushButton("💾 Save Governor Rules")
        btn_save.setObjectName("btnSecondary")
        btn_save.setMinimumHeight(34)
        btn_save.clicked.connect(self._save_governor_settings)
        row1.addWidget(btn_save)

        layout.addLayout(row1)

        # Ban Risk Compliance Warning Banner
        warning_frame = QFrame()
        warning_frame.setStyleSheet(
            f"background-color: rgba(245, 158, 11, 0.08); border: 1px solid {COLOR_AMBER_ALERT}; border-radius: 6px; padding: 6px;"
        )
        wf_layout = QHBoxLayout(warning_frame)
        wf_layout.setContentsMargins(10, 6, 10, 6)
        lbl_warn = QLabel("⚠️ COMPLIANCE NOTICE: WhatsApp automation carries ban risk. Use a dedicated secondary number and warm up send volume gradually.")
        lbl_warn.setStyleSheet(f"color: {COLOR_AMBER_ALERT}; font-weight: 600; font-size: 11px;")
        wf_layout.addWidget(lbl_warn)

        layout.addWidget(warning_frame)

        self.load_settings()

    def load_settings(self):
        try:
            min_delay = float(get_setting("send_min_delay_seconds", "2.5"))
            self.spn_min_delay.setValue(min_delay)
        except ValueError:
            pass

        try:
            jitter = float(get_setting("send_jitter_seconds", "1.5"))
            self.spn_jitter.setValue(jitter)
        except ValueError:
            pass

        try:
            daily_cap = int(get_setting("send_daily_cap", "800"))
            self.spn_daily_cap.setValue(daily_cap)
        except ValueError:
            pass

    def _save_governor_settings(self):
        set_setting("send_min_delay_seconds", str(self.spn_min_delay.value()))
        set_setting("send_jitter_seconds", str(self.spn_jitter.value()))
        set_setting("send_daily_cap", str(self.spn_daily_cap.value()))
        QMessageBox.information(self, "Governor Updated", "Send-Rate Governor parameters saved successfully!")
        self.governor_settings_changed.emit()
