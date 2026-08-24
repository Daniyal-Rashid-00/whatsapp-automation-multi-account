import threading
import httpx
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QInputDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
import database as db
from ui.widgets.toggle_switch import ToggleSwitch
from waha_launcher import WAHALauncher


class AccountsPage(QWidget):
    qr_requested = pyqtSignal(str, str, bool)  # (session_name, qr_data_url, is_new_account)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._last_session_names: list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 1. Responsive Page Header Bar
        hdr_layout = QHBoxLayout()
        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        title = QLabel("WhatsApp Account Manager")
        title.setObjectName("pageTitle")
        v_title.addWidget(title)

        sub = QLabel("Manage connected phone numbers, multi-session instances, and individual automation toggles.")
        sub.setObjectName("subduedLabel")
        v_title.addWidget(sub)
        hdr_layout.addLayout(v_title, stretch=1)

        # Compact & responsive button bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_start_all = QPushButton("🚀 Start All")
        btn_start_all.setObjectName("btnPrimary")
        btn_start_all.setToolTip("Initialize engine and connect all enabled WhatsApp accounts")
        btn_start_all.setFixedHeight(34)
        btn_start_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_start_all.clicked.connect(self._initialize_all_accounts)
        btn_layout.addWidget(btn_start_all)

        btn_add_acc = QPushButton("➕ Add Account")
        btn_add_acc.setObjectName("btnSecondary")
        btn_add_acc.setToolTip("Connect a new WhatsApp account")
        btn_add_acc.setFixedHeight(34)
        btn_add_acc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_acc.clicked.connect(self._add_account_dialog)
        btn_layout.addWidget(btn_add_acc)

        btn_refresh_matrix = QPushButton("🔄 Refresh")
        btn_refresh_matrix.setObjectName("btnSecondary")
        btn_refresh_matrix.setToolTip("Manually refresh accounts matrix")
        btn_refresh_matrix.setFixedHeight(34)
        btn_refresh_matrix.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh_matrix.clicked.connect(self._manual_refresh_matrix)
        btn_layout.addWidget(btn_refresh_matrix)

        hdr_layout.addLayout(btn_layout)
        layout.addLayout(hdr_layout)

        # 2. Managed Accounts Matrix Table
        card_matrix = QFrame()
        card_matrix.setObjectName("cardFrame")
        m_layout = QVBoxLayout(card_matrix)
        m_layout.setContentsMargins(14, 14, 14, 14)
        m_layout.setSpacing(10)

        lbl_m_title = QLabel("CONNECTED WHATSAPP ACCOUNTS MATRIX")
        lbl_m_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #8B949E; letter-spacing: 0.5px;")
        m_layout.addWidget(lbl_m_title)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "AUTOMATION", "ACCOUNT ALIAS", "PHONE / JID", "STATUS", "HEALTH DIAGNOSTICS", "ACTIONS"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)

        # Responsive Column Sizing:
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 90)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 115)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 265)

        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        m_layout.addWidget(self.table)

        layout.addWidget(card_matrix, stretch=1)

        # Smart refresh timer — updates live status every 4 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(4000)
        self.refresh_timer.timeout.connect(self.refresh_accounts_matrix)
        self.refresh_timer.start()

        self.refresh_accounts_matrix()

    def refresh_accounts_matrix(self):
        """
        Efficient 2-tier refresh:
        - Full rebuild only when account list structure changes
        - Fast text-only update for status/phone/diagnostics every 4s
        """
        accounts = db.get_all_accounts()
        session_names = [a["session_name"] for a in accounts]

        if session_names != self._last_session_names or self.table.rowCount() != len(accounts):
            self._last_session_names = session_names
            self._full_rebuild(accounts)
            return

        # Fast text-only in-place update
        self.table.blockSignals(True)
        for row, acc in enumerate(accounts):
            status = acc.get("status", "STOPPED").upper()
            phone = acc.get("phone_number") or "Unlinked"

            # Col 2: Phone
            if self.table.item(row, 2):
                self.table.item(row, 2).setText(phone)
            else:
                self.table.setItem(row, 2, QTableWidgetItem(phone))

            # Col 3: Status
            status_text = f"● {status}" if status in ("WORKING", "CONNECTED") else (f"⏳ {status}" if status in ("SCAN_QR_CODE", "STARTING") else f"○ {status}")
            if self.table.item(row, 3):
                item_status = self.table.item(row, 3)
                item_status.setText(status_text)
            else:
                item_status = QTableWidgetItem(status_text)
                self.table.setItem(row, 3, item_status)

            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if status in ("WORKING", "CONNECTED"):
                item_status.setForeground(Qt.GlobalColor.green)
            elif status in ("SCAN_QR_CODE", "STARTING"):
                item_status.setForeground(Qt.GlobalColor.yellow)
            else:
                item_status.setForeground(Qt.GlobalColor.red)

            # Col 4: Diagnostics
            last_err = acc.get("last_error") or ""
            diag_text = last_err if last_err else ("● Operational" if status in ("WORKING", "CONNECTED") else "Idle / Offline")
            if self.table.item(row, 4):
                self.table.item(row, 4).setText(diag_text)
            else:
                self.table.setItem(row, 4, QTableWidgetItem(diag_text))

        self.table.blockSignals(False)

    def _full_rebuild(self, accounts: list):
        """Full widget rebuild with spacious, non-overlapping action buttons and centered toggles."""
        self.table.blockSignals(True)
        self.table.setRowCount(len(accounts))

        for row, acc in enumerate(accounts):
            session_name = acc["session_name"]
            is_enabled = acc.get("is_enabled", 1) == 1
            status = acc.get("status", "STOPPED").upper()

            # Col 0: Automation Toggle Switch (Centered)
            toggle = ToggleSwitch(checked=is_enabled)

            def make_toggle_handler(sname):
                def handler(checked: bool):
                    db.toggle_account(sname, 1 if checked else 0)
                return handler

            toggle.stateChanged.connect(make_toggle_handler(session_name))
            toggle_container = QWidget()
            toggle_container.setStyleSheet("background: transparent;")
            tc_layout = QHBoxLayout(toggle_container)
            tc_layout.addWidget(toggle)
            tc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tc_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, toggle_container)

            # Col 1: Alias
            self.table.setItem(row, 1, QTableWidgetItem(acc["account_alias"]))

            # Col 2: Phone
            phone = acc.get("phone_number") or "Unlinked"
            self.table.setItem(row, 2, QTableWidgetItem(phone))

            # Col 3: Status
            status_text = f"● {status}" if status in ("WORKING", "CONNECTED") else (f"⏳ {status}" if status in ("SCAN_QR_CODE", "STARTING") else f"○ {status}")
            item_status = QTableWidgetItem(status_text)
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if status in ("WORKING", "CONNECTED"):
                item_status.setForeground(Qt.GlobalColor.green)
            elif status in ("SCAN_QR_CODE", "STARTING"):
                item_status.setForeground(Qt.GlobalColor.yellow)
            else:
                item_status.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 3, item_status)

            # Col 4: Diagnostics
            last_err = acc.get("last_error") or ""
            diag_text = last_err if last_err else ("● Operational" if status in ("WORKING", "CONNECTED") else "Idle / Offline")
            self.table.setItem(row, 4, QTableWidgetItem(diag_text))

            # Col 5: Action Buttons (Well-spaced, non-overlapping)
            act_widget = QWidget()
            act_widget.setStyleSheet("background: transparent;")
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(4, 8, 4, 8)
            act_layout.setSpacing(8)
            act_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            btn_open = QPushButton("Open Web")
            btn_open.setFixedSize(78, 28)
            btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_open.setStyleSheet("""
                QPushButton {
                    background: #1E3A5F;
                    color: #7DD3FC;
                    border: 1px solid #38BDF8;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: #0369A1;
                    color: #FFFFFF;
                }
            """)
            btn_open.setToolTip("Open visible WhatsApp Web browser tab for this account")
            btn_open.clicked.connect(lambda _, s=session_name: self._start_session_action(s))
            act_layout.addWidget(btn_open)

            btn_logout = QPushButton("Logout")
            btn_logout.setFixedSize(70, 28)
            btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_logout.setStyleSheet("""
                QPushButton {
                    background: #2D2214;
                    color: #FCD34D;
                    border: 1px solid #F59E0B;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: #B45309;
                    color: #FFFFFF;
                }
            """)
            btn_logout.setToolTip("Unlink device from WhatsApp")
            btn_logout.clicked.connect(lambda _, s=session_name: self._logout_session_action(s))
            act_layout.addWidget(btn_logout)

            btn_del = QPushButton("Delete")
            btn_del.setFixedSize(68, 28)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setStyleSheet("""
                QPushButton {
                    background: #3B1818;
                    color: #FCA5A5;
                    border: 1px solid #EF4444;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: #DC2626;
                    color: #FFFFFF;
                }
            """)
            btn_del.setToolTip("Permanently remove this account and session files")
            btn_del.clicked.connect(lambda _, s=session_name: self._delete_session_action(s))
            act_layout.addWidget(btn_del)

            self.table.setCellWidget(row, 5, act_widget)

        self.table.blockSignals(False)

    def _initialize_all_accounts(self):
        threading.Thread(target=self._start_all_accounts_bg, daemon=True).start()
        QMessageBox.information(self, "Engine Initialized", "Initializing engine and starting all active WhatsApp sessions...")

    def _start_all_accounts_bg(self):
        w_url = db.get_setting("waha_url", "http://localhost:3000").rstrip("/")
        try:
            port = int(w_url.split(":")[-1])
        except Exception:
            port = 3000

        WAHALauncher.start_waha_engine(port=port)

        accounts = db.get_all_accounts()
        for acc in accounts:
            if acc.get("is_enabled", 1) == 1:
                try:
                    httpx.post(f"{w_url}/api/sessions/start", json={"session": acc["session_name"]}, timeout=5.0)
                except Exception:
                    pass

    def _manual_refresh_matrix(self):
        self._last_session_names = []  # Force full table matrix rebuild
        self.refresh_accounts_matrix()

    def _add_account_dialog(self):
        alias, ok = QInputDialog.getText(
            self, "Connect New Account",
            "Enter Account Alias (e.g. VA Support Line 2, Business Phone):"
        )
        if ok and alias.strip():
            clean_alias = alias.strip()
            session_name = f"account_{clean_alias.lower().replace(' ', '_')}"
            try:
                db.add_account(session_name=session_name, account_alias=clean_alias)
                self._last_session_names = []  # Force table rebuild
                self.refresh_accounts_matrix()
                self._start_session_action(session_name)
            except Exception as e:
                QMessageBox.warning(self, "Account Error", f"Could not add account: {e}")

    def _start_session_action(self, session_name: str):
        """Starts/opens the visible Chromium WhatsApp Web tab for this account."""
        db.update_account_status(session_name, "STARTING", last_error=None)
        self.refresh_accounts_matrix()
        threading.Thread(
            target=self._start_session_background,
            args=(session_name,),
            daemon=True
        ).start()

    def _start_session_background(self, session_name: str):
        try:
            w_url = db.get_setting("waha_url", "http://localhost:3000").rstrip("/")
            try:
                port = int(w_url.split(":")[-1])
            except Exception:
                port = 3000
            WAHALauncher.start_waha_engine(port=port)
            httpx.post(f"{w_url}/api/sessions/start", json={"session": session_name}, timeout=8.0)
        except Exception:
            pass

    def _logout_session_action(self, session_name: str):
        reply = QMessageBox.question(
            self, "Confirm Logout",
            f"Log out [{session_name}]?\n\nThis will unlink the device on your phone.\n"
            "You will need to scan a QR code to reconnect.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            threading.Thread(
                target=self._logout_background,
                args=(session_name,),
                daemon=True
            ).start()
            db.update_account_status(session_name, "STOPPED", last_error="Logged Out by User")
            self.refresh_accounts_matrix()

    def _logout_background(self, session_name: str):
        try:
            w_url = db.get_setting("waha_url", "http://localhost:3000").rstrip("/")
            httpx.post(f"{w_url}/api/sessions/logout", json={"session": session_name}, timeout=8.0)
        except Exception:
            pass

    def _delete_session_action(self, session_name: str):
        reply = QMessageBox.question(
            self, "Confirm Delete Account",
            f"Permanently delete account [{session_name}]?\n\nThis removes all session keys and cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.refresh_timer.stop()
            db.delete_account(session_name)
            self._last_session_names = []
            self.refresh_accounts_matrix()

            threading.Thread(
                target=self._delete_background,
                args=(session_name,),
                daemon=True
            ).start()

            QTimer.singleShot(6000, self.refresh_timer.start)

    def _delete_background(self, session_name: str):
        try:
            w_url = db.get_setting("waha_url", "http://localhost:3000").rstrip("/")
            httpx.post(f"{w_url}/api/sessions/logout", json={"session": session_name}, timeout=4.0)
            httpx.delete(f"{w_url}/api/sessions/{session_name}", timeout=8.0)
        except Exception:
            pass

    def _repair_session_action(self, session_name: str):
        reply = QMessageBox.question(
            self, "Repair Session Encryption Keys",
            f"Repair session keys for [{session_name}]?\n\nThis re-syncs Signal encryption keys in-place.\nZero QR code scan needed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.repair_session_keys_in_place(session_name)
                QMessageBox.information(
                    self, "Repair Complete",
                    f"Session [{session_name}] Signal encryption keys repaired in-place!\n\nNo QR scan required. Please restart CyberSolu Auto."
                )
                self.refresh_accounts_matrix()
            except Exception as e:
                QMessageBox.warning(self, "Repair Failed", f"Could not repair session: {e}")
