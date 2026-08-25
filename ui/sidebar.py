from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.theme import COLOR_DARK_BG, COLOR_BORDER_SUBDUED
import database as db


class SidebarNavWidget(QFrame):
    page_changed = pyqtSignal(int)
    global_toggle_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QFrame {{ background-color: {COLOR_DARK_BG}; border-right: 1px solid {COLOR_BORDER_SUBDUED}; }}")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(6)

        # Brand Logo Header
        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(2)
        lbl_title = QLabel("CyberSolu Auto")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #F0F6FC; letter-spacing: 1px;")
        brand_layout.addWidget(lbl_title)

        lbl_subtitle = QLabel("WhatsApp Support Studio")
        lbl_subtitle.setStyleSheet("font-size: 11px; font-weight: 500; color: #8B949E;")
        brand_layout.addWidget(lbl_subtitle)

        layout.addLayout(brand_layout)
        layout.addSpacing(20)

        # Nav Buttons (Index 0: Dash, Index 1: Rules, Index 2: AI, Index 3: Accounts, Index 4: Settings)
        self.nav_buttons = []

        btn_dash = self._create_nav_btn("📊 Dashboard", 0)
        btn_rules = self._create_nav_btn("⚡ Rule Studio", 1)
        btn_ai = self._create_nav_btn("🤖 AI Assistant", 2)
        btn_accounts = self._create_nav_btn("📱 Accounts", 3)
        btn_settings = self._create_nav_btn("⚙️ Settings && Safety", 4)

        self.nav_buttons = [btn_dash, btn_rules, btn_ai, btn_accounts, btn_settings]

        for btn in self.nav_buttons:
            layout.addWidget(btn)

        layout.addStretch()

        # Session Status Widget
        self.session_label = QLabel("● Session: Offline")
        self.session_label.setStyleSheet("color: #EF4444; font-weight: 600; font-size: 11px; padding: 4px;")
        layout.addWidget(self.session_label)

        # Global Engine Switch
        self._is_global_on = True
        self.btn_global = QPushButton("Engine: ACTIVE")
        self.btn_global.setObjectName("btnPrimary")
        self.btn_global.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_global.clicked.connect(self._toggle_global)
        layout.addWidget(self.btn_global)

        # Main Exit / Shutdown Button
        self.btn_exit = QPushButton("⚡ Exit Studio")
        self.btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #111827;
                color: #94A3B8;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #4C0519;
                color: #FECDD3;
                border: 1px solid #F43F5E;
            }
        """)
        self.btn_exit.clicked.connect(self._exit_app)
        layout.addWidget(self.btn_exit)

        # Set default active page
        self.set_active_page(0)
        self.update_session_status()

    def _create_nav_btn(self, text: str, page_index: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("navItem")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self._on_nav_clicked(page_index))
        return btn

    def _on_nav_clicked(self, page_index: int):
        self.set_active_page(page_index)
        self.page_changed.emit(page_index)

    def set_active_page(self, page_index: int):
        for i, btn in enumerate(self.nav_buttons):
            if i == page_index:
                btn.setProperty("active", "true")
            else:
                btn.setProperty("active", "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def update_session_status(self, status: str = None):
        """Multi-account system status checker: green if AT LEAST ONE account is WORKING."""
        accounts = db.get_all_accounts()
        working = [a for a in accounts if a.get("status", "").upper() in ("WORKING", "CONNECTED")]
        starting = [a for a in accounts if a.get("status", "").upper() in ("STARTING", "SCAN_QR_CODE")]

        if len(working) > 0:
            count_str = f"{len(working)} Account{'s' if len(working) > 1 else ''} Online"
            self.session_label.setText(f"● {count_str}")
            self.session_label.setStyleSheet("color: #10B981; font-weight: 600; font-size: 11px; padding: 4px;")
        elif len(starting) > 0:
            self.session_label.setText(f"⏳ Connecting ({len(starting)})...")
            self.session_label.setStyleSheet("color: #F59E0B; font-weight: 600; font-size: 11px; padding: 4px;")
        else:
            self.session_label.setText("⚠ Session: STOPPED")
            self.session_label.setStyleSheet("color: #EF4444; font-weight: 600; font-size: 11px; padding: 4px;")

    def _toggle_global(self):
        self._is_global_on = not self._is_global_on
        if self._is_global_on:
            self.btn_global.setText("Engine: ACTIVE")
            self.btn_global.setObjectName("btnPrimary")
            self.btn_global.setStyleSheet("background-color: #2563EB; color: white; font-weight: 600;")
        else:
            self.btn_global.setText("Engine: PAUSED")
            self.btn_global.setStyleSheet("background-color: #EF4444; color: white; font-weight: 600;")
        self.global_toggle_changed.emit(self._is_global_on)

    def _exit_app(self):
        import os
        import sys
        from PyQt6.QtWidgets import QApplication
        from waha_launcher import WAHALauncher
        import database as db

        try:
            db.clear_activity_logs()
        except Exception:
            pass

        w_url = db.get_setting("waha_url", "http://localhost:3000").rstrip("/")
        try:
            port = int(w_url.split(":")[-1])
        except Exception:
            port = 3000

        WAHALauncher.stop_waha_engine(port=port)
        QApplication.quit()
        os._exit(0)
