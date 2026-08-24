import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
import database as db


class MetricCard(QFrame):
    def __init__(self, title: str, value: str, subtext: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 11px; font-weight: 600; color: #8B949E; text-transform: uppercase;")
        layout.addWidget(lbl_t)

        self.lbl_v = QLabel(value)
        self.lbl_v.setStyleSheet("font-size: 22px; font-weight: 700; color: #F0F6FC;")
        layout.addWidget(self.lbl_v)

        self.lbl_sub = QLabel(subtext)
        self.lbl_sub.setStyleSheet("font-size: 11px; color: #8B949E;")
        layout.addWidget(self.lbl_sub)

    def set_value(self, val: str, sub: str = ""):
        self.lbl_v.setText(val)
        if sub:
            self.lbl_sub.setText(sub)


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Page Header
        hdr_layout = QHBoxLayout()
        title = QLabel("Dashboard Overview")
        title.setObjectName("pageTitle")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()

        self.btn_clear_log = QPushButton("🗑️ Clear Activity Log")
        self.btn_clear_log.setObjectName("btnSecondary")
        self.btn_clear_log.setMinimumHeight(34)
        self.btn_clear_log.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_log.clicked.connect(self._clear_activity_log_action)
        hdr_layout.addWidget(self.btn_clear_log)

        self.btn_refresh = QPushButton("🔄 Refresh Dashboard")
        self.btn_refresh.setObjectName("btnSecondary")
        self.btn_refresh.setMinimumHeight(34)
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self._manual_refresh_action)
        hdr_layout.addWidget(self.btn_refresh)

        layout.addLayout(hdr_layout)

        # Metric Cards Row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        self.card_rules = MetricCard("Active Rules", "0 Rules", "Configured static automation rules")
        cards_row.addWidget(self.card_rules)

        self.card_queue = MetricCard("Message Queue", "0 Pending", "Durable SQLite WAL queue")
        cards_row.addWidget(self.card_queue)

        self.card_sends = MetricCard("Today's Sends", "0 / 800", "Send-Rate Governor daily cap")
        cards_row.addWidget(self.card_sends)

        self.card_accounts = MetricCard("Connected Accounts", "0 Connected", "Baileys WhatsApp Sessions")
        cards_row.addWidget(self.card_accounts)

        layout.addLayout(cards_row)

        # Recent Activity Table
        lbl_act = QLabel("Recent Inbound Activity Log")
        lbl_act.setStyleSheet("font-size: 14px; font-weight: 700; color: #F0F6FC; margin-top: 10px;")
        layout.addWidget(lbl_act)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "MESSAGE ID", "CUSTOMER NUMBER", "ACCOUNT RECEIVED", "BODY SNIPPET", "STATUS", "RECEIVED AT"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table, stretch=1)

        self.refresh_metrics()

    def refresh_metrics(self):
        # Rules count
        rules = db.get_all_rules()
        active_count = sum(1 for r in rules if r.get("is_enabled", 1) == 1)
        self.card_rules.set_value(f"{active_count} Active", f"{len(rules)} Total Configured")

        # Queue metrics
        q = db.get_queue_metrics()
        pending = q.get("pending", 0)
        done = q.get("done", 0)
        self.card_queue.set_value(f"{pending} Pending", f"{done} Processed successfully")

        # Sends metrics
        today_sends = db.get_today_send_count()
        try:
            daily_cap = int(db.get_setting("send_daily_cap", "800"))
        except ValueError:
            daily_cap = 800
        self.card_sends.set_value(f"{today_sends} / {daily_cap}", "Messages sent today")

        # Dynamic Multi-Account Connected Accounts metric
        accounts = db.get_all_accounts()
        account_map = {a["session_name"]: f"{a['account_alias']} ({a.get('phone_number') or 'Unlinked'})" for a in accounts}

        working_accounts = [a for a in accounts if a.get("status", "").upper() in ("WORKING", "CONNECTED")]
        total_accounts = len(accounts)
        connected_count = len(working_accounts)

        if connected_count > 0:
            self.card_accounts.set_value(
                f"{connected_count} Connected",
                f"● {connected_count} of {total_accounts} accounts online"
            )
        else:
            self.card_accounts.set_value("0 Connected", "⭕ All accounts offline")

        # Refresh recent activity table from DB
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT message_id, chat_id, body, raw_payload, session_name, status, received_at FROM inbound_queue ORDER BY received_at DESC LIMIT 15;")
        rows = cursor.fetchall()
        conn.close()

        self.table.setRowCount(len(rows))
        for r_idx, r in enumerate(rows):
            msg_id = r['message_id'][:16] + "..."
            raw_payload_str = r['raw_payload'] or ""
            session_name = r['session_name'] or 'default'
            customer_num = r['chat_id'].split('@')[0]

            try:
                pdata = json.loads(raw_payload_str)
                payload = pdata.get('payload', {})
                phone = payload.get('phone') or payload.get('from', '').split('@')[0]
                push_name = payload.get('name')
                if phone and phone != 'unknown':
                    customer_num = f"+{phone}"
                    if push_name and push_name != phone:
                        customer_num = f"{push_name} (+{phone})"
                sess = pdata.get('session') or session_name
                session_name = sess
            except Exception:
                pass

            account_label = account_map.get(session_name, session_name)

            self.table.setItem(r_idx, 0, QTableWidgetItem(msg_id))
            self.table.setItem(r_idx, 1, QTableWidgetItem(customer_num))
            self.table.setItem(r_idx, 2, QTableWidgetItem(account_label))
            self.table.setItem(r_idx, 3, QTableWidgetItem(r['body'] or ""))
            self.table.setItem(r_idx, 4, QTableWidgetItem(r['status'].upper()))

            raw_ts = str(r['received_at'])
            formatted_ts = raw_ts
            try:
                clean_ts = raw_ts.split('.')[0]
                dt = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
                formatted_ts = dt.strftime("%Y-%m-%d %I:%M:%S %p")
            except Exception:
                pass

            self.table.setItem(r_idx, 5, QTableWidgetItem(formatted_ts))

    def _manual_refresh_action(self):
        self.refresh_metrics()
        win = self.window()
        if win and hasattr(win, "page_accounts"):
            win.page_accounts._last_session_names = []
            win.page_accounts.refresh_accounts_matrix()
        if win and hasattr(win, "refresh_rules_matrix"):
            win.refresh_rules_matrix()
        self.btn_refresh.setText("✅ All System Refreshed!")
        QTimer.singleShot(1500, lambda: self.btn_refresh.setText("🔄 Refresh Dashboard"))

    def _clear_activity_log_action(self):
        reply = QMessageBox.question(
            self, "Clear Activity Log",
            "Are you sure you want to clear all past activity logs?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.clear_activity_logs()
            self.refresh_metrics()
            QMessageBox.information(self, "Log Cleared", "Inbound activity logs have been cleared successfully.")
