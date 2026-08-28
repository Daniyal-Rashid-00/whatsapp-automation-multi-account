import json
import asyncio
import threading
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QMessageBox, QComboBox,
    QCheckBox, QProgressBar, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor
import database as db
from waha_client import WAHAClient


class UnreadCatchUpPage(QWidget):
    scan_finished_signal = pyqtSignal(list, str)
    item_status_updated_signal = pyqtSignal(int, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.scan_finished_signal.connect(self._on_scan_finished)
        self.item_status_updated_signal.connect(self._on_item_status_updated)

        self._messages = []
        self._selected_indices = set()
        self._is_processing = False

        # Root layout with 0 margins for clean scroll
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #0D1117;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #30363D;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover { background: #58A6FF; }
        """)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Page Header
        v_head = QVBoxLayout()
        v_head.setSpacing(3)
        lbl_title = QLabel("📥 Overnight & Unread Inquiries Catch-Up Studio")
        lbl_title.setObjectName("pageTitle")
        v_head.addWidget(lbl_title)

        lbl_subtitle = QLabel("Safely scan, review, and auto-reply to customer messages that arrived while the software was offline.")
        lbl_subtitle.setStyleSheet("font-size: 12px; color: #8B949E;")
        v_head.addWidget(lbl_subtitle)
        layout.addLayout(v_head)

        # 2. Controls & Filter Card
        card_controls = QFrame()
        card_controls.setObjectName("cardFrame")
        card_controls.setStyleSheet("""
            QFrame#cardFrame {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 8px;
            }
        """)
        c_layout = QVBoxLayout(card_controls)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(12)

        row_filters = QHBoxLayout()
        row_filters.setSpacing(14)

        # Account Filter
        v_acc = QVBoxLayout()
        v_acc.setSpacing(3)
        lbl_acc = QLabel("SELECT WHATSAPP ACCOUNT:")
        lbl_acc.setStyleSheet("font-size: 10px; font-weight: 700; color: #8B949E;")
        v_acc.addWidget(lbl_acc)

        self.cmb_account = QComboBox()
        self.cmb_account.addItem("All Connected Accounts", "all")
        self.cmb_account.setFixedHeight(32)
        v_acc.addWidget(self.cmb_account)
        row_filters.addLayout(v_acc, stretch=1)

        # Time Window Filter
        v_time = QVBoxLayout()
        v_time.setSpacing(3)
        lbl_time = QLabel("TIME HORIZON / FILTER:")
        lbl_time.setStyleSheet("font-size: 10px; font-weight: 700; color: #8B949E;")
        v_time.addWidget(lbl_time)

        self.cmb_time = QComboBox()
        self.cmb_time.addItems([
            "All Unread (No Time Limit)",
            "Last 12 Hours (Overnight)",
            "Last 24 Hours (Full Day)",
            "Last 6 Hours (Recent)",
            "Last 48 Hours (2 Days)"
        ])
        self.cmb_time.setFixedHeight(32)
        v_time.addWidget(self.cmb_time)
        row_filters.addLayout(v_time, stretch=1)

        # Scan Button
        self.btn_scan = QPushButton("🔍 Scan WhatsApp for Unread Chats")
        self.btn_scan.setObjectName("btnPrimary")
        self.btn_scan.setFixedHeight(34)
        self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.clicked.connect(self._scan_unread_clicked)
        row_filters.addWidget(self.btn_scan)

        c_layout.addLayout(row_filters)

        # Actions & Selection Sub-bar
        row_sel = QHBoxLayout()
        row_sel.setSpacing(10)

        self.btn_sel_all = QPushButton("Select All")
        self.btn_sel_all.setObjectName("btnSecondary")
        self.btn_sel_all.setFixedHeight(28)
        self.btn_sel_all.clicked.connect(self._select_all)
        row_sel.addWidget(self.btn_sel_all)

        self.btn_desel_all = QPushButton("Deselect All")
        self.btn_desel_all.setObjectName("btnSecondary")
        self.btn_desel_all.setFixedHeight(28)
        self.btn_desel_all.clicked.connect(self._deselect_all)
        row_sel.addWidget(self.btn_desel_all)

        self.lbl_sel_count = QLabel("● 0 Inquiries Selected")
        self.lbl_sel_count.setStyleSheet("font-size: 11px; font-weight: 700; color: #58A6FF; margin-left: 6px;")
        row_sel.addWidget(self.lbl_sel_count)

        row_sel.addStretch()

        self.btn_start = QPushButton("⚡ Start Safe Catch-Up Replies (0 Selected)")
        self.btn_start.setObjectName("btnPrimary")
        self.btn_start.setFixedHeight(34)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._start_processing_clicked)
        row_sel.addWidget(self.btn_start)

        c_layout.addLayout(row_sel)

        layout.addWidget(card_controls)

        # 3. Governor Safety & Progress Banner
        self.card_progress = QFrame()
        self.card_progress.setStyleSheet("""
            QFrame {
                background-color: #0D1117;
                border: 1px solid #21262D;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        v_prog = QVBoxLayout(self.card_progress)
        v_prog.setContentsMargins(12, 10, 12, 10)
        v_prog.setSpacing(6)

        row_gov_text = QHBoxLayout()
        lbl_shield = QLabel("⚡ Fast Reply Mode: Inquiries are queued and processed with your configured 0.5s speed.")
        lbl_shield.setStyleSheet("font-size: 11px; color: #8B949E;")
        row_gov_text.addWidget(lbl_shield)
        row_gov_text.addStretch()

        self.lbl_prog_status = QLabel("● Ready")
        self.lbl_prog_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #22C55E;")
        row_gov_text.addWidget(self.lbl_prog_status)
        v_prog.addLayout(row_gov_text)

        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(8)
        self.pbar.setTextVisible(False)
        self.pbar.setStyleSheet("""
            QProgressBar { background-color: #21262D; border-radius: 4px; }
            QProgressBar::chunk { background-color: #2563EB; border-radius: 4px; }
        """)
        self.pbar.setVisible(False)
        v_prog.addWidget(self.pbar)

        layout.addWidget(self.card_progress)

        # 4. Inquiries Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "SELECT", "ACCOUNT", "CUSTOMER", "INQUIRY / MESSAGE", "UNREAD", "TIME", "STATUS"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMinimumHeight(380)

        layout.addWidget(self.table)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        self._refresh_accounts_dropdown()

    def _refresh_accounts_dropdown(self):
        self.cmb_account.clear()
        self.cmb_account.addItem("All Connected Accounts", "all")
        accounts = db.get_all_accounts()
        for a in accounts:
            alias = a.get("account_alias") or a["session_name"]
            phone = a.get("phone_number") or ""
            label = f"{alias} ({phone})" if phone else alias
            self.cmb_account.addItem(label, a["session_name"])

    def _scan_unread_clicked(self):
        target_session = self.cmb_account.currentData() or "all"
        combo_text = self.cmb_time.currentText()
        if "6 Hours" in combo_text:
            max_hours = 6.0
        elif "12 Hours" in combo_text:
            max_hours = 12.0
        elif "24 Hours" in combo_text:
            max_hours = 24.0
        elif "48 Hours" in combo_text:
            max_hours = 48.0
        else:
            max_hours = 0.0

        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("⏳ Scanning WhatsApp...")
        self.lbl_prog_status.setText("⏳ Scanning WhatsApp sessions...")
        self.lbl_prog_status.setStyleSheet("color: #F59E0B; font-weight: 700;")

        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                client = WAHAClient()
                messages = loop.run_until_complete(client.get_unread_messages(session=target_session, max_hours=max_hours))
                loop.close()
                self.scan_finished_signal.emit(messages, "")
            except Exception as e:
                loop.close()
                self.scan_finished_signal.emit([], str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_finished(self, messages: list, error_msg: str):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("🔍 Scan WhatsApp for Unread Chats")

        if error_msg:
            self.lbl_prog_status.setText(f"❌ Scan Error: {error_msg}")
            self.lbl_prog_status.setStyleSheet("color: #EF4444; font-weight: 700;")
            QMessageBox.warning(self, "Scan Error", f"Could not scan WhatsApp chats: {error_msg}")
            return

        self._messages = messages
        self._selected_indices = set(range(len(messages)))
        self._checkboxes = []

        self.table.setRowCount(len(messages))

        if not messages:
            self.lbl_prog_status.setText("● No unread chats found")
            self.lbl_prog_status.setStyleSheet("color: #8B949E; font-weight: 700;")
            combo_text = self.cmb_time.currentText()
            QMessageBox.information(
                self, "No Unread Chats",
                f"🎉 No unread customer inquiries found in the {combo_text}!\n\nAll customer messages across all connected WhatsApp sessions have already been read and replied to."
            )
            self._update_counts()
            return

        self.lbl_prog_status.setText(f"● Found {len(messages)} unread customer inquiries ready for catch-up")
        self.lbl_prog_status.setStyleSheet("color: #22C55E; font-weight: 700;")

        for idx, m in enumerate(messages):
            chk = QCheckBox()
            chk.setChecked(True)
            chk.setStyleSheet("margin-left: 10px;")
            chk.stateChanged.connect(lambda state, i=idx: self._on_row_check_changed(i, state))
            self._checkboxes.append(chk)
            self.table.setCellWidget(idx, 0, chk)

            item_acc = QTableWidgetItem(m.get("session", "default"))
            item_acc.setForeground(QColor("#8B949E"))
            self.table.setItem(idx, 1, item_acc)

            c_name = m.get("customerName", "")
            c_num = m.get("chatId", "").split("@")[0]
            display_cust = f"{c_name} (+{c_num})" if c_name and c_name != c_num else f"+{c_num}"
            self.table.setItem(idx, 2, QTableWidgetItem(display_cust))

            body_text = m.get("body", "")
            if m.get("isVoice"):
                body_text = f"🎤 [Voice Note] {body_text}".strip()
            self.table.setItem(idx, 3, QTableWidgetItem(body_text))

            item_cnt = QTableWidgetItem(f"{m.get('unreadCount', 1)} msg")
            item_cnt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_cnt.setForeground(QColor("#58A6FF"))
            self.table.setItem(idx, 4, item_cnt)

            item_time = QTableWidgetItem(m.get("timeFormatted", ""))
            item_time.setForeground(QColor("#8B949E"))
            item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(idx, 5, item_time)

            item_st = QTableWidgetItem("⏳ Ready")
            item_st.setForeground(QColor("#60A5FA"))
            item_st.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(idx, 6, item_st)

        self._update_counts()

    def _on_row_check_changed(self, idx: int, state: int):
        if state == 2:
            self._selected_indices.add(idx)
        else:
            self._selected_indices.discard(idx)
        self._update_counts()

    def _select_all(self):
        if hasattr(self, "_checkboxes"):
            for chk in self._checkboxes:
                chk.setChecked(True)
        self._selected_indices = set(range(len(self._messages)))
        self._update_counts()

    def _deselect_all(self):
        if hasattr(self, "_checkboxes"):
            for chk in self._checkboxes:
                chk.setChecked(False)
        self._selected_indices.clear()
        self._update_counts()

    def _update_counts(self):
        cnt = len(self._selected_indices)
        tot = len(self._messages)
        self.lbl_sel_count.setText(f"● {cnt} of {tot} Inquiries Selected")
        self.btn_start.setText(f"⚡ Start Safe Catch-Up Replies ({cnt} Selected)")
        self.btn_start.setEnabled(cnt > 0 and not self._is_processing)

    def _start_processing_clicked(self):
        selected_msgs = [self._messages[i] for i in sorted(self._selected_indices)]
        if not selected_msgs:
            return

        reply = QMessageBox.question(
            self, "Confirm Catch-Up Auto-Replies",
            f"Are you sure you want to start automated catch-up replies for {len(selected_msgs)} unread customer inquiries?\n\n"
            "⚡ Inquiries will be processed at your configured 0.5s speed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._is_processing = True
        self.btn_start.setEnabled(False)
        self.btn_scan.setEnabled(False)
        self.pbar.setVisible(True)
        self.pbar.setRange(0, len(selected_msgs))
        self.pbar.setValue(0)
        self.lbl_prog_status.setText(f"🚀 Processing {len(selected_msgs)} catch-up replies safely through Send-Rate Governor...")

        enqueued_count = 0
        for i, m in enumerate(selected_msgs):
            msg_id = m.get("messageId") or f"CATCHUP_{int(datetime.now().timestamp())}_{i}"
            chat_id = m.get("chatId", "")
            body = m.get("body", "")
            session_name = m.get("session", "default")
            is_voice = m.get("isVoice", False)

            if not chat_id:
                continue

            raw_payload = json.dumps({
                "event": "message",
                "session": session_name,
                "payload": {
                    "id": msg_id,
                    "from": chat_id,
                    "body": body,
                    "isVoice": is_voice,
                    "fromMe": False,
                    "mediaData": m.get("mediaData"),
                    "name": m.get("customerName", ""),
                    "timestamp": m.get("timestamp")
                }
            })

            # Check duplicate / already processed
            if not db.is_message_duplicate(msg_id):
                db.enqueue_inbound_message(
                    message_id=msg_id,
                    chat_id=chat_id,
                    body=body,
                    raw_payload=raw_payload,
                    session_name=session_name
                )
                enqueued_count += 1

        # Notify Durable Queue Processor
        win = self.window()
        if win and hasattr(win, "queue_processor") and win.queue_processor:
            win.queue_processor.notify_new_message()

        QMessageBox.information(
            self, "Catch-Up Enqueued Successfully",
            f"🚀 Successfully enqueued {enqueued_count} unread inquiries into the Durable Queue!\n\n"
            "🛡️ The Send-Rate Governor is now sending replies safely in the background.\n"
            "You can watch live progress on the Dashboard Activity Log."
        )

        self._is_processing = False
        self.btn_scan.setEnabled(True)
        self._update_counts()
        self.pbar.setVisible(False)
        self.lbl_prog_status.setText(f"● {enqueued_count} Inquiries enqueued and being processed safely")
        self.lbl_prog_status.setStyleSheet("color: #22C55E; font-weight: 700;")

    def _on_item_status_updated(self, row: int, status_text: str, color_hex: str):
        if 0 <= row < self.table.rowCount():
            item = QTableWidgetItem(status_text)
            item.setForeground(QColor(color_hex))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, item)
