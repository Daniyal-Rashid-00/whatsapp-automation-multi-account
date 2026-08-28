import threading
import httpx
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QProgressBar, QTextEdit,
    QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from database import get_setting, get_all_accounts

logger = logging.getLogger(__name__)

class ContactSaverPage(QWidget):
    progress_signal = pyqtSignal(int, int, str)
    finished_signal = pyqtSignal(bool, str)
    labels_loaded_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = False
        self._labels_cache = []
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        v_head = QVBoxLayout()
        v_head.setSpacing(4)
        lbl_title = QLabel("🏷️ WhatsApp Order Contact Saver")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #F0F6FC;")
        v_head.addWidget(lbl_title)

        lbl_subtitle = QLabel("Automatically number and save customer contacts from daily WhatsApp Lists with sequential Order IDs.")
        lbl_subtitle.setStyleSheet("font-size: 13px; color: #8B949E;")
        v_head.addWidget(lbl_subtitle)
        layout.addLayout(v_head)

        card = QFrame()
        card.setObjectName("cardFrame")
        card.setStyleSheet("""
            QFrame#cardFrame {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        row1 = QHBoxLayout()
        row1.setSpacing(16)

        v_acc = QVBoxLayout()
        v_acc.setSpacing(6)
        lbl_acc = QLabel("SELECT WHATSAPP ACCOUNT:")
        lbl_acc.setStyleSheet("font-size: 11px; font-weight: 700; color: #8B949E;")
        v_acc.addWidget(lbl_acc)

        self.cmb_accounts = QComboBox()
        self.cmb_accounts.setStyleSheet("""
            QComboBox {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                color: #F0F6FC;
                font-size: 13px;
            }
        """)
        self.cmb_accounts.currentIndexChanged.connect(self._on_account_changed)
        v_acc.addWidget(self.cmb_accounts)
        row1.addLayout(v_acc, stretch=1)

        v_label = QVBoxLayout()
        v_label.setSpacing(6)
        lbl_list = QLabel("SELECT WHATSAPP LIST / LABEL:")
        lbl_list.setStyleSheet("font-size: 11px; font-weight: 700; color: #8B949E;")
        v_label.addWidget(lbl_list)

        h_list_row = QHBoxLayout()
        h_list_row.setSpacing(8)
        self.cmb_labels = QComboBox()
        self.cmb_labels.setStyleSheet("""
            QComboBox {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                color: #F0F6FC;
                font-size: 13px;
            }
        """)
        h_list_row.addWidget(self.cmb_labels, stretch=1)

        self.btn_refresh_labels = QPushButton("🔄 Refresh Lists")
        self.btn_refresh_labels.setStyleSheet("""
            QPushButton {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #30363D; }
        """)
        self.btn_refresh_labels.clicked.connect(self.load_labels_for_selected_account)
        h_list_row.addWidget(self.btn_refresh_labels)
        v_label.addLayout(h_list_row)
        row1.addLayout(v_label, stretch=2)

        card_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(16)

        v_order = QVBoxLayout()
        v_order.setSpacing(6)
        lbl_order = QLabel("STARTING ORDER ID NUMBER:")
        lbl_order.setStyleSheet("font-size: 11px; font-weight: 700; color: #8B949E;")
        v_order.addWidget(lbl_order)

        self.txt_start_id = QLineEdit()
        self.txt_start_id.setPlaceholderText("e.g. 12012")
        self.txt_start_id.setStyleSheet("""
            QLineEdit {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                color: #F0F6FC;
                font-size: 13px;
                font-weight: 600;
            }
        """)
        v_order.addWidget(self.txt_start_id)
        row2.addLayout(v_order, stretch=1)

        v_opts = QVBoxLayout()
        v_opts.setSpacing(6)
        lbl_opt = QLabel("SAVE OPTIONS:")
        lbl_opt.setStyleSheet("font-size: 11px; font-weight: 700; color: #8B949E;")
        v_opts.addWidget(lbl_opt)

        self.chk_overwrite = QCheckBox("Overwrite already-saved contacts in list")
        self.chk_overwrite.setStyleSheet("color: #8B949E; font-size: 12px;")
        v_opts.addWidget(self.chk_overwrite)
        row2.addLayout(v_opts, stretch=1)

        card_layout.addLayout(row2)

        row_actions = QHBoxLayout()
        row_actions.setSpacing(12)

        self.btn_start = QPushButton("▶ Start Auto-Saving Contacts")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                font-weight: 700;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #2EA043; }
            QPushButton:disabled { background-color: #21262D; color: #6E7681; }
        """)
        self.btn_start.clicked.connect(self._start_saving_contacts)
        row_actions.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #DA3633;
                color: white;
                font-weight: 700;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #F85149; }
            QPushButton:disabled { background-color: #21262D; color: #6E7681; }
        """)
        self.btn_stop.clicked.connect(self._stop_saving)
        row_actions.addWidget(self.btn_stop)
        row_actions.addStretch()

        card_layout.addLayout(row_actions)
        layout.addWidget(card)

        card_log = QFrame()
        card_log.setObjectName("logFrame")
        card_log.setStyleSheet("""
            QFrame#logFrame {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 8px;
            }
        """)
        v_log = QVBoxLayout(card_log)
        v_log.setContentsMargins(20, 20, 20, 20)
        v_log.setSpacing(10)

        self.lbl_progress_status = QLabel("Ready. Select a list and enter starting Order ID to begin.")
        self.lbl_progress_status.setStyleSheet("font-size: 13px; font-weight: 600; color: #8B949E;")
        v_log.addWidget(self.lbl_progress_status)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setFixedHeight(12)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #238636;
                border-radius: 5px;
            }
        """)
        v_log.addWidget(self.prog_bar)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("""
            QTextEdit {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                color: #C9D1D9;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                padding: 10px;
            }
        """)
        v_log.addWidget(self.txt_log, stretch=1)

        layout.addWidget(card_log, stretch=1)

    def _connect_signals(self):
        self.progress_signal.connect(self._on_progress_update)
        self.finished_signal.connect(self._on_finished)
        self.labels_loaded_signal.connect(self._on_labels_loaded)

    def _get_waha_url(self) -> str:
        url = get_setting("waha_url", "http://localhost:3000").rstrip("/")
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"http://{url}"
        return url

    def refresh_accounts(self):
        accounts = get_all_accounts()
        self.cmb_accounts.blockSignals(True)
        self.cmb_accounts.clear()
        for acc in accounts:
            s_name = acc["session_name"]
            phone = acc.get("phone_number") or "Unlinked"
            self.cmb_accounts.addItem(f"{s_name} ({phone})", s_name)
        self.cmb_accounts.blockSignals(False)
        self.load_labels_for_selected_account()

    def _on_account_changed(self):
        self.load_labels_for_selected_account()

    def load_labels_for_selected_account(self):
        session_name = self.cmb_accounts.currentData()
        if not session_name:
            return

        self.cmb_labels.clear()
        self.cmb_labels.addItem("⏳ Loading lists from WhatsApp...", "")
        self.btn_refresh_labels.setEnabled(False)

        def worker():
            base_url = self._get_waha_url()
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.get(f"{base_url}/api/labels?session={session_name}")
                    if resp.status_code == 200:
                        labels = resp.json()
                        self.labels_loaded_signal.emit(labels)
                    else:
                        self.labels_loaded_signal.emit([])
            except Exception as e:
                logger.error(f"Failed to fetch labels: {e}")
                self.labels_loaded_signal.emit([])

        threading.Thread(target=worker, daemon=True).start()

    def _on_labels_loaded(self, labels: list):
        self.btn_refresh_labels.setEnabled(True)
        self.cmb_labels.clear()
        self._labels_cache = labels

        if not labels:
            self.cmb_labels.addItem("⚠️ No Lists / Labels found in account", "")
            return

        # Separate custom date lists vs default system filter chips
        system_names = {"unread", "favourites", "groups", "unassigned"}
        custom_lists = [l for l in labels if l.get("name", "").strip().lower() not in system_names]
        system_lists = [l for l in labels if l.get("name", "").strip().lower() in system_names]

        # Prioritize lists with active chats (> 0)
        custom_lists.sort(key=lambda x: (x.get("count", 0) == 0, x.get("name", "")))

        for l in custom_lists:
            l_id = l.get("id")
            name = l.get("name")
            count = l.get("count", 0)
            self.cmb_labels.addItem(f"📁 {name}  ({count} chats)", l_id)

        for l in system_lists:
            l_id = l.get("id")
            name = l.get("name")
            count = l.get("count", 0)
            self.cmb_labels.addItem(f"🏷️ {name}  ({count} chats)", l_id)

    def _start_saving_contacts(self):
        session_name = self.cmb_accounts.currentData()
        label_id = self.cmb_labels.currentData()
        start_id_str = self.txt_start_id.text().strip()
        overwrite = self.chk_overwrite.isChecked()

        if not session_name:
            QMessageBox.warning(self, "Missing Account", "Please select a connected WhatsApp account.")
            return

        if not label_id:
            QMessageBox.warning(self, "Missing List", "Please select a WhatsApp List / Label.")
            return

        if not start_id_str or not start_id_str.isdigit():
            QMessageBox.warning(self, "Invalid ID", "Please enter a valid starting Order ID number (e.g. 12012).")
            return

        start_id = int(start_id_str)
        list_display = self.cmb_labels.currentText()

        self._is_running = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.cmb_accounts.setEnabled(False)
        self.cmb_labels.setEnabled(False)
        self.txt_start_id.setEnabled(False)

        self.txt_log.clear()
        self._append_log(f"🚀 Starting Auto-Numbering for List: '{list_display}' starting at ID {start_id}...")
        self.prog_bar.setValue(0)
        self.lbl_progress_status.setText(f"Processing '{list_display}'...")

        def worker():
            base_url = self._get_waha_url()
            payload = {
                "session": session_name,
                "labelId": label_id,
                "startOrderId": start_id,
                "overwriteExisting": overwrite
            }

            try:
                with httpx.Client(timeout=300.0) as client:
                    resp = client.post(f"{base_url}/api/labels/save-contacts", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        saved = data.get("savedCount", 0)
                        skipped = data.get("skippedCount", 0)
                        total = data.get("totalChats", 0)
                        details = data.get("details", [])

                        for idx, item in enumerate(details, start=1):
                            action = item.get("action")
                            phone = item.get("phone")
                            if action == "saved":
                                msg = f"✅ [{idx}/{total}] Saved contact {phone} as '{item.get('assignedName')}'"
                            else:
                                msg = f"⏩ [{idx}/{total}] Skipped {phone} ({item.get('reason')}: {item.get('name')})"
                            self.progress_signal.emit(idx, total, msg)

                        summary = f"🎉 Done! {saved} contacts saved, {skipped} skipped out of {total} chats."
                        self.finished_signal.emit(True, summary)
                    else:
                        err_msg = f"Server returned status {resp.status_code}: {resp.text}"
                        self.finished_signal.emit(False, err_msg)
            except Exception as e:
                self.finished_signal.emit(False, f"Exception during save: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _stop_saving(self):
        self._is_running = False
        self._append_log("🛑 Save operation stopped by user.")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.cmb_accounts.setEnabled(True)
        self.cmb_labels.setEnabled(True)
        self.txt_start_id.setEnabled(True)

    def _on_progress_update(self, current: int, total: int, log_msg: str):
        if total > 0:
            pct = int((current / total) * 100)
            self.prog_bar.setValue(pct)
            self.lbl_progress_status.setText(f"Progress: {current} / {total} ({pct}%)")
        self._append_log(log_msg)

    def _on_finished(self, success: bool, msg: str):
        self._is_running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.cmb_accounts.setEnabled(True)
        self.cmb_labels.setEnabled(True)
        self.txt_start_id.setEnabled(True)

        self._append_log(f"\n{msg}")
        if success:
            self.lbl_progress_status.setText(msg)
            self.lbl_progress_status.setStyleSheet("font-size: 13px; font-weight: 700; color: #22C55E;")
            self.prog_bar.setValue(100)
            QMessageBox.information(self, "Auto-Numbering Complete", msg)
        else:
            self.lbl_progress_status.setText(f"❌ Failed: {msg}")
            self.lbl_progress_status.setStyleSheet("font-size: 13px; font-weight: 700; color: #EF4444;")
            QMessageBox.critical(self, "Error", f"Failed to save contacts: {msg}")

    def _append_log(self, text: str):
        import time
        t_str = time.strftime("%H:%M:%S")
        self.txt_log.append(f"[{t_str}] {text}")
