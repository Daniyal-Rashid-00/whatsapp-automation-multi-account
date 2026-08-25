import threading
import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QTextEdit, QPushButton, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from database import get_setting, set_setting
from vault import store_secret, retrieve_secret, delete_secret
from ui.widgets.toggle_switch import ToggleSwitch
from ai_key_pool import key_pool
from ai_engine import test_ai_connection


class AIPage(QWidget):
    # Cross-thread signal for test results
    test_result_signal = pyqtSignal(bool, str, float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.test_result_signal.connect(self._on_test_result)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Page Header
        hdr_layout = QHBoxLayout()
        title = QLabel("AI Assistant Configuration")
        title.setObjectName("pageTitle")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        layout.addLayout(hdr_layout)

        # Main Card Container
        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(14)

        # 1. AI Engine Master Switch & Mode Control Row
        row_master = QHBoxLayout()
        row_master.setSpacing(14)

        is_ai_on = get_setting("ai_master_enabled", get_setting("ai_fallback_enabled", "0")) == "1"
        self.tog_ai_master = ToggleSwitch(checked=is_ai_on)
        self.tog_ai_master.stateChanged.connect(self._on_ai_master_toggled)
        row_master.addWidget(self.tog_ai_master)

        v_m_title = QVBoxLayout()
        v_m_title.setSpacing(2)
        status_text = "ACTIVE (ON)" if is_ai_on else "PAUSED (OFF)"
        status_color = "#22C55E" if is_ai_on else "#EF4444"
        self.lbl_m_title = QLabel(f"AI Engine Master Switch: {status_text}")
        self.lbl_m_title.setStyleSheet(f"font-weight: 700; font-size: 14px; color: {status_color};")
        v_m_title.addWidget(self.lbl_m_title)
        lbl_m_sub = QLabel("Master toggle to activate or deactivate Generative AI automated responses.")
        lbl_m_sub.setStyleSheet("font-size: 11px; color: #8B949E;")
        v_m_title.addWidget(lbl_m_sub)
        row_master.addLayout(v_m_title)
        row_master.addStretch()

        card_layout.addLayout(row_master)

        # Divider
        div_ai = QFrame()
        div_ai.setFixedHeight(1)
        div_ai.setStyleSheet("background-color: #21262D; border: none;")
        card_layout.addWidget(div_ai)

        # 2. AI Operating Mode Selector
        row_mode = QHBoxLayout()
        row_mode.setSpacing(14)

        v_mode = QVBoxLayout()
        v_mode.setSpacing(4)
        lbl_mode = QLabel("AI OPERATING MODE:")
        lbl_mode.setStyleSheet("font-weight: 700; font-size: 11px; color: #8B949E;")
        v_mode.addWidget(lbl_mode)

        self.cmb_operating_mode = QComboBox()
        self.cmb_operating_mode.addItems([
            "Hybrid Mode (Rules First, AI Fallback)",
            "Exclusive AI Mode (AI Only, Rules Bypassed)"
        ])
        self.cmb_operating_mode.currentIndexChanged.connect(self._save_settings)
        v_mode.addWidget(self.cmb_operating_mode)
        row_mode.addLayout(v_mode, stretch=2)

        lbl_mode_desc = QLabel(
            "• Hybrid: Rule Book executes first. AI responds ONLY if no static rule matches.\n"
            "• Exclusive AI: Bypasses static rules and generates all replies via AI."
        )
        lbl_mode_desc.setStyleSheet("font-size: 11px; color: #8B949E;")
        row_mode.addWidget(lbl_mode_desc, stretch=3)

        card_layout.addLayout(row_mode)

        # 3. Provider & Model Row
        row1 = QHBoxLayout()
        row1.setSpacing(14)

        v1 = QVBoxLayout()
        v1.setSpacing(4)
        lbl_prov = QLabel("AI PROVIDER SERVICE:")
        lbl_prov.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v1.addWidget(lbl_prov)
        self.cmb_provider = QComboBox()
        self.cmb_provider.addItems(["Gemini", "OpenRouter"])
        self.cmb_provider.currentTextChanged.connect(self._save_settings)
        v1.addWidget(self.cmb_provider)
        row1.addLayout(v1, stretch=1)

        v2 = QVBoxLayout()
        v2.setSpacing(4)
        lbl_mod = QLabel("MODEL ID OVERRIDE:")
        lbl_mod.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v2.addWidget(lbl_mod)
        self.txt_model_id = QLineEdit()
        self.txt_model_id.setPlaceholderText("e.g. gemini-3.5-flash-lite (Recommended for speed & free tier)")
        self.txt_model_id.editingFinished.connect(self._save_settings)
        v2.addWidget(self.txt_model_id)
        row1.addLayout(v2, stretch=2)

        card_layout.addLayout(row1)

        # 4. Multi-Key Pool Section
        v_key_pool = QVBoxLayout()
        v_key_pool.setSpacing(6)

        hdr_keys = QHBoxLayout()
        lbl_key_title = QLabel("AI API KEY ROTATION POOL (Keychain Vault):")
        lbl_key_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #8B949E; letter-spacing: 0.5px;")
        hdr_keys.addWidget(lbl_key_title)

        self.lbl_pool_status = QLabel("● 0 Keys Configured")
        self.lbl_pool_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #EF4444;")
        hdr_keys.addWidget(self.lbl_pool_status)
        hdr_keys.addStretch()

        self.btn_test_conn = QPushButton("⚡ Test Connection")
        self.btn_test_conn.setObjectName("btnSecondary")
        self.btn_test_conn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test_conn.setFixedHeight(28)
        self.btn_test_conn.clicked.connect(self._test_connection_clicked)
        hdr_keys.addWidget(self.btn_test_conn)

        v_key_pool.addLayout(hdr_keys)

        # Key Slot 1 (Primary)
        self.txt_api_key_1 = QLineEdit()
        self.txt_api_key_1.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key_1.setPlaceholderText("Primary API Key (Required, e.g. AIzaSy...)")
        row_k1 = self._build_key_row(self.txt_api_key_1, "nexus_ai_key", "Key 1 (Primary)")
        v_key_pool.addLayout(row_k1)

        # Key Slot 2 (Secondary)
        self.txt_api_key_2 = QLineEdit()
        self.txt_api_key_2.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key_2.setPlaceholderText("Secondary API Key (Optional — for high-throughput round robin)")
        row_k2 = self._build_key_row(self.txt_api_key_2, "nexus_ai_key_2", "Key 2 (Optional)")
        v_key_pool.addLayout(row_k2)

        # Key Slot 3 (Tertiary)
        self.txt_api_key_3 = QLineEdit()
        self.txt_api_key_3.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key_3.setPlaceholderText("Tertiary API Key (Optional — for maximum concurrency)")
        row_k3 = self._build_key_row(self.txt_api_key_3, "nexus_ai_key_3", "Key 3 (Optional)")
        v_key_pool.addLayout(row_k3)

        self.lbl_test_result = QLabel("")
        self.lbl_test_result.setStyleSheet("font-size: 11px; padding: 2px;")
        v_key_pool.addWidget(self.lbl_test_result)

        card_layout.addLayout(v_key_pool)

        # 5. System Knowledge Base Sandbox
        v_ctx = QVBoxLayout()
        v_ctx.setSpacing(4)
        lbl_ctx = QLabel("SYSTEM KNOWLEDGE BASE SANDBOX (SOPs, Pricing, Returns, Policies):")
        lbl_ctx.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v_ctx.addWidget(lbl_ctx)

        self.txt_system_context = QTextEdit()
        self.txt_system_context.setPlaceholderText(
            "STORE NAME: CyberCraft Store Pakistan\n"
            "LOCATION: Lahore, Pakistan\n"
            "BUSINESS HOURS: 10:00 AM to 10:00 PM PKT\n\n"
            "DELIVERY & SHIPPING SOPs:\n"
            "• Shipping Charges: Flat Rs. 200 across all cities in Pakistan.\n"
            "• Delivery Time: 2 to 4 working days.\n"
            "• Payment Method: Cash on Delivery (COD) available for all non-customized items.\n"
        )
        self.txt_system_context.setMinimumHeight(180)
        v_ctx.addWidget(self.txt_system_context)

        card_layout.addLayout(v_ctx)

        # Save Button
        btn_save_all = QPushButton("Save AI Configuration & Knowledge Base")
        btn_save_all.setObjectName("btnPrimary")
        btn_save_all.setMinimumHeight(38)
        btn_save_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_all.clicked.connect(self._save_all_ai_settings)
        card_layout.addWidget(btn_save_all)

        layout.addWidget(card)
        layout.addStretch()

        self.load_settings()

    def _build_key_row(self, line_edit: QLineEdit, ref_key: str, label_text: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        lbl = QLabel(label_text + ":")
        lbl.setFixedWidth(100)
        lbl.setStyleSheet("font-size: 11px; color: #8B949E; font-weight: 600;")
        row.addWidget(lbl)

        row.addWidget(line_edit, stretch=4)

        btn_save = QPushButton("Save")
        btn_save.setObjectName("btnSecondary")
        btn_save.setFixedSize(60, 30)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(lambda _, le=line_edit, ref=ref_key: self._save_single_key(le, ref))
        row.addWidget(btn_save)

        btn_clear = QPushButton("Clear")
        btn_clear.setFixedSize(55, 30)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet("background: #2D1414; color: #F87171; border: 1px solid #EF4444; border-radius: 5px; font-size: 11px;")
        btn_clear.clicked.connect(lambda _, le=line_edit, ref=ref_key: self._clear_single_key(le, ref))
        row.addWidget(btn_clear)

        return row

    def _save_single_key(self, line_edit: QLineEdit, ref_key: str):
        secret = line_edit.text().strip()
        if not secret:
            QMessageBox.warning(self, "Empty Key", "Please paste an API key before saving.")
            return
        if store_secret(ref_key, secret):
            self._update_pool_status_badge()
            QMessageBox.information(self, "Vault Saved", f"Key saved securely in vault as [{ref_key}]!")
        else:
            QMessageBox.critical(self, "Vault Error", "Failed to store API Key in credential vault.")

    def _clear_single_key(self, line_edit: QLineEdit, ref_key: str):
        delete_secret(ref_key)
        line_edit.clear()
        self._update_pool_status_badge()
        QMessageBox.information(self, "Key Cleared", f"Key [{ref_key}] cleared from vault.")

    def _update_pool_status_badge(self):
        active_count = key_pool.get_active_count()
        if active_count >= 2:
            self.lbl_pool_status.setText(f"🟢 {active_count} Keys Active (Multi-Key Round-Robin Enabled)")
            self.lbl_pool_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #22C55E;")
        elif active_count == 1:
            self.lbl_pool_status.setText("🟢 1 Key Active (Single Key Mode)")
            self.lbl_pool_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #38BDF8;")
        else:
            self.lbl_pool_status.setText("🔴 0 Keys Configured (AI Disabled)")
            self.lbl_pool_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #EF4444;")

    def _on_ai_master_toggled(self, checked: bool):
        is_master = "1" if checked else "0"
        set_setting("ai_master_enabled", is_master)
        set_setting("ai_fallback_enabled", is_master)
        if checked:
            self.lbl_m_title.setText("AI Engine Master Switch: ACTIVE (ON)")
            self.lbl_m_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #22C55E;")
        else:
            self.lbl_m_title.setText("AI Engine Master Switch: PAUSED (OFF)")
            self.lbl_m_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #EF4444;")

    def load_settings(self):
        master_on = get_setting("ai_master_enabled", get_setting("ai_fallback_enabled", "0")) == "1"
        self.tog_ai_master.blockSignals(True)
        self.tog_ai_master.setChecked(master_on)
        self.tog_ai_master.blockSignals(False)

        status_text = "ACTIVE (ON)" if master_on else "PAUSED (OFF)"
        status_color = "#22C55E" if master_on else "#EF4444"
        self.lbl_m_title.setText(f"AI Engine Master Switch: {status_text}")
        self.lbl_m_title.setStyleSheet(f"font-weight: 700; font-size: 14px; color: {status_color};")

        op_mode = get_setting("ai_operating_mode", "hybrid")
        self.cmb_operating_mode.blockSignals(True)
        if op_mode == "ai_only":
            self.cmb_operating_mode.setCurrentIndex(1)
        else:
            self.cmb_operating_mode.setCurrentIndex(0)
        self.cmb_operating_mode.blockSignals(False)

        provider = get_setting("ai_provider", "gemini").lower()
        self.cmb_provider.blockSignals(True)
        for i in range(self.cmb_provider.count()):
            if self.cmb_provider.itemText(i).lower() == provider:
                self.cmb_provider.setCurrentIndex(i)
                break
        self.cmb_provider.blockSignals(False)

        model = get_setting("ai_model_name", "gemini-3.5-flash-lite")
        if model in ("gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"):
            model = "gemini-3.5-flash-lite"
        self.txt_model_id.setText(model)

        context = get_setting("ai_system_context", "")
        self.txt_system_context.setText(context)

        # Load Keys
        k1 = retrieve_secret("nexus_ai_key") or ""
        self.txt_api_key_1.setText(k1)

        k2 = retrieve_secret("nexus_ai_key_2") or ""
        self.txt_api_key_2.setText(k2)

        k3 = retrieve_secret("nexus_ai_key_3") or ""
        self.txt_api_key_3.setText(k3)

        self._update_pool_status_badge()

    def _test_connection_clicked(self):
        primary_key = self.txt_api_key_1.text().strip() or retrieve_secret("nexus_ai_key") or ""
        if not primary_key:
            QMessageBox.warning(self, "No Key", "Please enter at least Primary Key (Key 1) to test connection.")
            return

        model = self.txt_model_id.text().strip() or "gemini-3.5-flash-lite"
        provider = self.cmb_provider.currentText().lower()

        self.btn_test_conn.setEnabled(False)
        self.lbl_test_result.setText("⏳ Testing AI connection...")
        self.lbl_test_result.setStyleSheet("color: #F59E0B; font-weight: 600;")

        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success, msg, latency = loop.run_until_complete(
                test_ai_connection(primary_key, model, provider)
            )
            loop.close()
            self.test_result_signal.emit(success, msg, latency)

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_result(self, success: bool, msg: str, latency: float):
        self.btn_test_conn.setEnabled(True)
        if success:
            self.lbl_test_result.setText(f"✅ Connection verified ({latency:.2f}s latency)")
            self.lbl_test_result.setStyleSheet("color: #22C55E; font-weight: 600;")
        else:
            self.lbl_test_result.setText(f"❌ Connection failed: {msg}")
            self.lbl_test_result.setStyleSheet("color: #EF4444; font-weight: 600;")

    def _save_settings(self):
        is_master = "1" if self.tog_ai_master.isChecked() else "0"
        set_setting("ai_master_enabled", is_master)
        set_setting("ai_fallback_enabled", is_master)

        selected_mode = "ai_only" if self.cmb_operating_mode.currentIndex() == 1 else "hybrid"
        set_setting("ai_operating_mode", selected_mode)
        set_setting("ai_provider", self.cmb_provider.currentText().lower())
        set_setting("ai_model_name", self.txt_model_id.text().strip() or "gemini-3.5-flash-lite")

    def _save_all_ai_settings(self):
        self._save_settings()
        set_setting("ai_system_context", self.txt_system_context.toPlainText().strip())

        # Save any keys typed into fields
        k1 = self.txt_api_key_1.text().strip()
        if k1:
            store_secret("nexus_ai_key", k1)

        k2 = self.txt_api_key_2.text().strip()
        if k2:
            store_secret("nexus_ai_key_2", k2)

        k3 = self.txt_api_key_3.text().strip()
        if k3:
            store_secret("nexus_ai_key_3", k3)

        self._update_pool_status_badge()
        QMessageBox.information(self, "Settings Saved", "AI Assistant configuration and Key Pool saved successfully!")
