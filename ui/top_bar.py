from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.theme import (
    COLOR_ELECTRIC_CYAN, COLOR_CYBER_GREEN, COLOR_NEON_CRIMSON,
    COLOR_AMBER_ALERT, COLOR_SLATE_OFFWHITE, COLOR_MUTED_STEEL,
    COLOR_SLATE_SURFACE, COLOR_BORDER_BLUE
)

class TopBarWidget(QFrame):
    global_toggle_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self._is_global_on = True

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # Row 1: Header Brand & Cyber Toggle Button
        row1 = QHBoxLayout()
        
        # Logo Badge + Title
        logo_layout = QHBoxLayout()
        logo_layout.setSpacing(8)
        
        self.title_label = QLabel("⚡ NEXUSAUTOMATA  |  ENTERPRISE WHATSAPP SUPPORT STUDIO")
        self.title_label.setObjectName("headerTitle")
        logo_layout.addWidget(self.title_label)
        
        row1.addLayout(logo_layout)
        row1.addStretch()

        # Global Cyber Switch Button
        self.btn_global_toggle = QPushButton("🟢 ENGINE ACTIVE")
        self.btn_global_toggle.setObjectName("btnPrimary")
        self.btn_global_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_global_toggle.setMinimumWidth(160)
        self.btn_global_toggle.clicked.connect(self._toggle_global)
        row1.addWidget(self.btn_global_toggle)

        main_layout.addLayout(row1)

        # Row 2: Status Pill Badges & Today's Cap Metric Widget
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        # Session Badge
        self.session_badge = QLabel("SESSION: WORKING")
        self._apply_pill_style(self.session_badge, COLOR_CYBER_GREEN, "rgba(16, 185, 129, 0.12)")
        row2.addWidget(self.session_badge)

        # Queue Badge
        self.queue_badge = QLabel("QUEUE: 0 PENDING")
        self._apply_pill_style(self.queue_badge, COLOR_ELECTRIC_CYAN, "rgba(0, 240, 255, 0.12)")
        row2.addWidget(self.queue_badge)

        # Send Rate Badge
        self.rate_badge = QLabel("GOVERNOR RATE: OK")
        self._apply_pill_style(self.rate_badge, COLOR_CYBER_GREEN, "rgba(16, 185, 129, 0.12)")
        row2.addWidget(self.rate_badge)

        row2.addStretch()

        # Today's Sends Metric
        self.sends_badge = QLabel("📊 TODAY'S SENDS: 0 / 800 cap")
        self._apply_pill_style(self.sends_badge, COLOR_SLATE_OFFWHITE, "rgba(148, 163, 184, 0.12)")
        row2.addWidget(self.sends_badge)

        main_layout.addLayout(row2)

    def _apply_pill_style(self, label: QLabel, text_color: str, bg_color: str):
        label.setStyleSheet(
            f"color: {text_color}; background-color: {bg_color}; "
            f"border: 1px solid {text_color}; border-radius: 12px; "
            f"padding: 4px 14px; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;"
        )

    def update_session_status(self, status: str):
        st = status.upper()
        if st in ("WORKING", "CONNECTED"):
            self.session_badge.setText(f"● SESSION: {st}")
            self._apply_pill_style(self.session_badge, COLOR_CYBER_GREEN, "rgba(16, 185, 129, 0.15)")
        elif st in ("SCAN_QR_CODE", "STARTING"):
            self.session_badge.setText(f"⏳ SESSION: {st}")
            self._apply_pill_style(self.session_badge, COLOR_AMBER_ALERT, "rgba(245, 158, 11, 0.15)")
        else:
            self.session_badge.setText(f"⚠ SESSION: {st}")
            self._apply_pill_style(self.session_badge, COLOR_NEON_CRIMSON, "rgba(239, 68, 68, 0.15)")

    def update_queue_metrics(self, pending_count: int):
        self.queue_badge.setText(f"📥 QUEUE: {pending_count} PENDING")
        if pending_count > 0:
            self._apply_pill_style(self.queue_badge, COLOR_ELECTRIC_CYAN, "rgba(0, 240, 255, 0.2)")
        else:
            self._apply_pill_style(self.queue_badge, COLOR_MUTED_STEEL, "rgba(148, 163, 184, 0.1)")

    def update_send_metrics(self, today_sends: int, daily_cap: int):
        self.sends_badge.setText(f"📊 TODAY'S SENDS: {today_sends} / {daily_cap} cap")
        if today_sends >= daily_cap:
            self.rate_badge.setText("⛔ RATE: CAP REACHED")
            self._apply_pill_style(self.rate_badge, COLOR_NEON_CRIMSON, "rgba(239, 68, 68, 0.2)")
        else:
            self.rate_badge.setText("⚡ RATE: GOVERNOR OK")
            self._apply_pill_style(self.rate_badge, COLOR_CYBER_GREEN, "rgba(16, 185, 129, 0.15)")

    def _toggle_global(self):
        self._is_global_on = not self._is_global_on
        if self._is_global_on:
            self.btn_global_toggle.setText("🟢 ENGINE ACTIVE")
            self.btn_global_toggle.setStyleSheet(
                f"background-color: {COLOR_ELECTRIC_CYAN}; color: {COLOR_SLATE_SURFACE}; "
                f"font-weight: 800; border: none; border-radius: 6px;"
            )
        else:
            self.btn_global_toggle.setText("🔴 ENGINE PAUSED")
            self.btn_global_toggle.setStyleSheet(
                f"background-color: {COLOR_NEON_CRIMSON}; color: white; "
                f"font-weight: 800; border: none; border-radius: 6px;"
            )
        self.global_toggle_changed.emit(self._is_global_on)
