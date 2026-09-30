import threading
import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QTextEdit, QPushButton, QMessageBox, QFrame, QScrollArea
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

        # Root layout holding the responsive scroll area
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Smooth Scroll Area to ensure 100% screen responsiveness on any resolution
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
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
            QScrollBar::handle:vertical:hover {
                background: #58A6FF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(14)

        # Page Header
        hdr_layout = QHBoxLayout()
        title = QLabel("AI Assistant Configuration")
        title.setObjectName("pageTitle")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        content_layout.addLayout(hdr_layout)

        # Main Card Container
        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        # 1. AI Engine Master Switch & Mode Control Row
        row_master = QHBoxLayout()
        row_master.setSpacing(14)

        is_ai_on = get_setting("ai_master_enabled", get_setting("ai_fallback_enabled", "0")) == "1"
        self.tog_ai_master = ToggleSwitch(checked=is_ai_on)
        self.tog_ai_master.stateChanged.connect(self._on_ai_master_toggled)
        row_master.addWidget(self.tog_ai_master, alignment=Qt.AlignmentFlag.AlignVCenter)

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

        # 1b. Voice Note AI Auto-Reply Switch
        row_voice = QHBoxLayout()
        row_voice.setSpacing(14)

        is_voice_on = get_setting("ai_voice_enabled", "1") == "1"
        self.tog_voice = ToggleSwitch(checked=is_voice_on)
        self.tog_voice.stateChanged.connect(self._on_voice_toggled)
        row_voice.addWidget(self.tog_voice, alignment=Qt.AlignmentFlag.AlignVCenter)

        v_v_title = QVBoxLayout()
        v_v_title.setSpacing(2)
        v_status = "ENABLED (ON)" if is_voice_on else "DISABLED (OFF)"
        v_color = "#22C55E" if is_voice_on else "#EF4444"
        self.lbl_v_title = QLabel(f"Voice Note AI Auto-Replies: {v_status}")
        self.lbl_v_title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {v_color};")
        v_v_title.addWidget(self.lbl_v_title)
        lbl_v_sub = QLabel("Automatically listen to customer voice messages (.ogg) and send instant text replies.")
        lbl_v_sub.setStyleSheet("font-size: 11px; color: #8B949E;")
        v_v_title.addWidget(lbl_v_sub)
        row_voice.addLayout(v_v_title)
        row_voice.addStretch()

        card_layout.addLayout(row_voice)

        # 1c. Conversation Memory (Context Window) Switch
        row_context = QHBoxLayout()
        row_context.setSpacing(14)

        is_ctx_on = get_setting("ai_context_enabled", "1") == "1"
        self.tog_context = ToggleSwitch(checked=is_ctx_on)
        self.tog_context.stateChanged.connect(self._on_context_toggled)
        row_context.addWidget(self.tog_context, alignment=Qt.AlignmentFlag.AlignVCenter)

        v_c_title = QVBoxLayout()
        v_c_title.setSpacing(2)
        c_status = "ENABLED (ON)" if is_ctx_on else "DISABLED (OFF)"
        c_color = "#22C55E" if is_ctx_on else "#EF4444"
        self.lbl_c_title = QLabel(f"Conversation Memory (Context Window): {c_status}")
        self.lbl_c_title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {c_color};")
        v_c_title.addWidget(self.lbl_c_title)
        lbl_c_sub = QLabel("Remembers the last 3 message exchanges per customer so the AI can understand follow-up questions in context.")
        lbl_c_sub.setStyleSheet("font-size: 11px; color: #8B949E;")
        v_c_title.addWidget(lbl_c_sub)
        row_context.addLayout(v_c_title)
        row_context.addStretch()

        card_layout.addLayout(row_context)

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

        # 3. Model Configuration & Provider Overrides
        row1 = QVBoxLayout()
        row1.setSpacing(8)

        lbl_models_title = QLabel("AI MODEL CONFIGURATION (Per-Provider Overrides):")
        lbl_models_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #8B949E; letter-spacing: 0.5px;")
        row1.addWidget(lbl_models_title)

        row_models_grid = QHBoxLayout()
        row_models_grid.setSpacing(10)

        # Gemini Model
        v_m1 = QVBoxLayout()
        v_m1.setSpacing(3)
        lbl_m1 = QLabel("GEMINI MODEL (Slots 1-3):")
        lbl_m1.setStyleSheet("font-size: 10px; font-weight: 600; color: #8B949E;")
        v_m1.addWidget(lbl_m1)
        self.txt_model_id = QLineEdit()
        self.txt_model_id.setPlaceholderText("gemini-3.5-flash-lite")
        self.txt_model_id.editingFinished.connect(self._save_settings)
        v_m1.addWidget(self.txt_model_id)
        row_models_grid.addLayout(v_m1, stretch=1)

        # OpenRouter Model (Slot 4)
        v_m2 = QVBoxLayout()
        v_m2.setSpacing(3)
        lbl_m2 = QLabel("OPENROUTER MODEL (Slot 4):")
        lbl_m2.setStyleSheet("font-size: 10px; font-weight: 600; color: #8B949E;")
        v_m2.addWidget(lbl_m2)
        self.txt_model_openrouter = QLineEdit()
        self.txt_model_openrouter.setPlaceholderText("nvidia/nemotron-3-super-120b-a12b:free")
        self.txt_model_openrouter.editingFinished.connect(self._save_settings)
        v_m2.addWidget(self.txt_model_openrouter)
        row_models_grid.addLayout(v_m2, stretch=1)

        # Groq Model (Slot 5)
        v_m3 = QVBoxLayout()
        v_m3.setSpacing(3)
        lbl_m3 = QLabel("GROQ MODEL (Slot 5):")
        lbl_m3.setStyleSheet("font-size: 10px; font-weight: 600; color: #8B949E;")
        v_m3.addWidget(lbl_m3)
        self.txt_model_groq = QLineEdit()
        self.txt_model_groq.setPlaceholderText("openai/gpt-oss-20b")
        self.txt_model_groq.editingFinished.connect(self._save_settings)
        v_m3.addWidget(self.txt_model_groq)
        row_models_grid.addLayout(v_m3, stretch=1)

        row1.addLayout(row_models_grid)
        card_layout.addLayout(row1)

        # 4. Multi-Key Pool Section (5-Slot Smart Multi-Provider Keychain)
        v_key_pool = QVBoxLayout()
        v_key_pool.setSpacing(6)

        hdr_keys = QHBoxLayout()
        lbl_key_title = QLabel("AI MULTI-PROVIDER KEY VAULT (5-Slot Auto-Failover):")
        lbl_key_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #8B949E; letter-spacing: 0.5px;")
        hdr_keys.addWidget(lbl_key_title)

        self.lbl_pool_status = QLabel("● 0 Keys Configured")
        self.lbl_pool_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #EF4444;")
        hdr_keys.addWidget(self.lbl_pool_status)
        hdr_keys.addStretch()

        self.btn_test_conn = QPushButton("⚡ Test All Connections")
        self.btn_test_conn.setObjectName("btnSecondary")
        self.btn_test_conn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test_conn.setFixedHeight(28)
        self.btn_test_conn.clicked.connect(self._test_all_connections_clicked)
        hdr_keys.addWidget(self.btn_test_conn)

        v_key_pool.addLayout(hdr_keys)

        # Key Slot 1 (Gemini Primary)
        self.txt_api_key_1 = QLineEdit()
        self.txt_api_key_1.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key_1.setPlaceholderText("Gemini Key 1 (AIzaSy...) — Tier 1 Primary")
        row_k1, self.tog_slot_1 = self._build_key_row(self.txt_api_key_1, "nexus_ai_key", "Gemini Key 1", 1)
        v_key_pool.addLayout(row_k1)

        # Key Slot 2 (Gemini Secondary)
        self.txt_api_key_2 = QLineEdit()
        self.txt_api_key_2.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key_2.setPlaceholderText("Gemini Key 2 (AIzaSy...) — Tier 1 Round-Robin")
        row_k2, self.tog_slot_2 = self._build_key_row(self.txt_api_key_2, "nexus_ai_key_2", "Gemini Key 2", 2)
        v_key_pool.addLayout(row_k2)

        # Key Slot 3 (Gemini Tertiary)
        self.txt_api_key_3 = QLineEdit()
        self.txt_api_key_3.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key_3.setPlaceholderText("Gemini Key 3 (AIzaSy...) — Tier 1 Round-Robin")
        row_k3, self.tog_slot_3 = self._build_key_row(self.txt_api_key_3, "nexus_ai_key_3", "Gemini Key 3", 3)
        v_key_pool.addLayout(row_k3)

        # Key Slot 4 (OpenRouter Failover)
        self.txt_api_key_4 = QLineEdit()
        self.txt_api_key_4.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key_4.setPlaceholderText("OpenRouter Key (sk-or-v1-...) — Tier 2 Failover")
        row_k4, self.tog_slot_4 = self._build_key_row(self.txt_api_key_4, "nexus_openrouter_key", "OpenRouter", 4)
        v_key_pool.addLayout(row_k4)

        # Key Slot 5 (Groq Cloud Voice & Failover)
        self.txt_api_key_5 = QLineEdit()
        self.txt_api_key_5.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key_5.setPlaceholderText("Groq Key (gsk_...) — Free Whisper V3 Voice & Tier 3 Failover")
        row_k5, self.tog_slot_5 = self._build_key_row(self.txt_api_key_5, "nexus_groq_key", "Groq Cloud", 5)
        v_key_pool.addLayout(row_k5)

        self.lbl_test_result = QLabel("")
        self.lbl_test_result.setWordWrap(True)
        self.lbl_test_result.setStyleSheet("font-size: 11px; padding: 6px; border-radius: 4px; background: rgba(22, 27, 34, 0.7); line-height: 1.4;")
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
        self.txt_system_context.setMinimumHeight(130)
        self.txt_system_context.setMaximumHeight(220)
        v_ctx.addWidget(self.txt_system_context)

        card_layout.addLayout(v_ctx)

        # Save Button
        btn_save_all = QPushButton("Save AI Configuration & Key Vault")
        btn_save_all.setObjectName("btnPrimary")
        btn_save_all.setMinimumHeight(38)
        btn_save_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_all.clicked.connect(self._save_all_ai_settings)
        card_layout.addWidget(btn_save_all)

        content_layout.addWidget(card)
        content_layout.addStretch()

        scroll.setWidget(content_widget)
        root_layout.addWidget(scroll)

        self.load_settings()

    def _build_key_row(self, line_edit: QLineEdit, ref_key: str, label_text: str, slot_num: int):
        row = QHBoxLayout()
        row.setSpacing(8)

        # Slot ON/OFF Toggle Switch
        is_slot_on = get_setting(f"ai_slot_{slot_num}_enabled", "1") == "1"
        tog = ToggleSwitch(checked=is_slot_on)
        tog.setToolTip(f"Turn ON/OFF {label_text} in AI failover rotation")

        def on_slot_toggled(checked: bool, s_num=slot_num, le=line_edit):
            set_setting(f"ai_slot_{s_num}_enabled", "1" if checked else "0")
            self._update_pool_status_badge()
            if not checked:
                le.setStyleSheet("background-color: #161B22; color: #484F58; border: 1px dashed #30363D;")
            else:
                le.setStyleSheet("")

        tog.stateChanged.connect(on_slot_toggled)
        row.addWidget(tog)

        lbl = QLabel(label_text + ":")
        lbl.setFixedWidth(115)
        lbl.setStyleSheet("font-size: 11px; color: #8B949E; font-weight: 600;")
        row.addWidget(lbl)

        if not is_slot_on:
            line_edit.setStyleSheet("background-color: #161B22; color: #484F58; border: 1px dashed #30363D;")

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

        return row, tog

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
        active_keys = key_pool.get_configured_keys()
        enabled_active = [k for k in active_keys if k.get("is_active") and k.get("is_enabled")]
        active_count = len(enabled_active)
        total_configured = len([k for k in active_keys if k.get("is_active")])

        if active_count >= 2:
            self.lbl_pool_status.setText(f"🟢 {active_count} of 5 Slots Active & Enabled (Multi-Tier Auto-Failover Enabled)")
            self.lbl_pool_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #22C55E;")
        elif active_count == 1:
            self.lbl_pool_status.setText(f"🟢 1 Slot Enabled ({enabled_active[0]['name']})")
            self.lbl_pool_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #38BDF8;")
        elif total_configured > 0 and active_count == 0:
            self.lbl_pool_status.setText("⏸ All Active Keys Manually Paused (AI Inactive)")
            self.lbl_pool_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #F59E0B;")
        else:
            self.lbl_pool_status.setText("🔴 0 Keys Configured (AI Disabled)")
            self.lbl_pool_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #EF4444;")

    def _on_voice_toggled(self, checked: bool):
        is_on = "1" if checked else "0"
        set_setting("ai_voice_enabled", is_on)
        if checked:
            self.lbl_v_title.setText("Voice Note AI Auto-Replies: ENABLED (ON)")
            self.lbl_v_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #22C55E;")
        else:
            self.lbl_v_title.setText("Voice Note AI Auto-Replies: DISABLED (OFF)")
            self.lbl_v_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #EF4444;")

    def _on_context_toggled(self, checked: bool):
        is_on = "1" if checked else "0"
        set_setting("ai_context_enabled", is_on)
        if checked:
            self.lbl_c_title.setText("Conversation Memory (Context Window): ENABLED (ON)")
            self.lbl_c_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #22C55E;")
        else:
            self.lbl_c_title.setText("Conversation Memory (Context Window): DISABLED (OFF)")
            self.lbl_c_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #EF4444;")

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

        voice_on = get_setting("ai_voice_enabled", "1") == "1"
        self.tog_voice.blockSignals(True)
        self.tog_voice.setChecked(voice_on)
        self.tog_voice.blockSignals(False)
        v_status = "ENABLED (ON)" if voice_on else "DISABLED (OFF)"
        v_color = "#22C55E" if voice_on else "#EF4444"
        self.lbl_v_title.setText(f"Voice Note AI Auto-Replies: {v_status}")
        self.lbl_v_title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {v_color};")

        context_on = get_setting("ai_context_enabled", "1") == "1"
        self.tog_context.blockSignals(True)
        self.tog_context.setChecked(context_on)
        self.tog_context.blockSignals(False)
        c_status = "ENABLED (ON)" if context_on else "DISABLED (OFF)"
        c_color = "#22C55E" if context_on else "#EF4444"
        self.lbl_c_title.setText(f"Conversation Memory (Context Window): {c_status}")
        self.lbl_c_title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {c_color};")

        op_mode = get_setting("ai_operating_mode", "hybrid")
        self.cmb_operating_mode.blockSignals(True)
        if op_mode == "ai_only":
            self.cmb_operating_mode.setCurrentIndex(1)
        else:
            self.cmb_operating_mode.setCurrentIndex(0)
        self.cmb_operating_mode.blockSignals(False)

        model = get_setting("ai_model_name", "gemini-3.5-flash-lite")
        if model in ("gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"):
            model = "gemini-3.5-flash-lite"
        self.txt_model_id.setText(model)

        or_model = get_setting("openrouter_model_name", "nvidia/nemotron-3-super-120b-a12b:free")
        self.txt_model_openrouter.setText(or_model)

        groq_model = get_setting("groq_model_name", "openai/gpt-oss-20b")
        self.txt_model_groq.setText(groq_model)

        context = get_setting("ai_system_context", "")
        self.txt_system_context.setText(context)

        # Load Keys (5 Slots)
        k1 = retrieve_secret("nexus_ai_key") or ""
        self.txt_api_key_1.setText(k1)

        k2 = retrieve_secret("nexus_ai_key_2") or ""
        self.txt_api_key_2.setText(k2)

        k3 = retrieve_secret("nexus_ai_key_3") or ""
        self.txt_api_key_3.setText(k3)

        k4 = retrieve_secret("nexus_openrouter_key") or ""
        self.txt_api_key_4.setText(k4)

        k5 = retrieve_secret("nexus_groq_key") or ""
        self.txt_api_key_5.setText(k5)

        # Load Slot Toggles (Slots 1-5)
        for i, tog in enumerate([self.tog_slot_1, self.tog_slot_2, self.tog_slot_3, self.tog_slot_4, self.tog_slot_5], start=1):
            is_on = get_setting(f"ai_slot_{i}_enabled", "1") == "1"
            tog.blockSignals(True)
            tog.setChecked(is_on)
            tog.blockSignals(False)

        self._update_pool_status_badge()

    def _test_all_connections_clicked(self):
        gemini_model = self.txt_model_id.text().strip() or "gemini-3.5-flash-lite"
        or_model = self.txt_model_openrouter.text().strip() or "nvidia/nemotron-3-super-120b-a12b:free"
        groq_model = self.txt_model_groq.text().strip() or "openai/gpt-oss-20b"

        keys_to_test = [
            (1, "Slot 1 (Gemini 1)", self.txt_api_key_1.text().strip() or retrieve_secret("nexus_ai_key") or "", gemini_model, "gemini"),
            (2, "Slot 2 (Gemini 2)", self.txt_api_key_2.text().strip() or retrieve_secret("nexus_ai_key_2") or "", gemini_model, "gemini"),
            (3, "Slot 3 (Gemini 3)", self.txt_api_key_3.text().strip() or retrieve_secret("nexus_ai_key_3") or "", gemini_model, "gemini"),
            (4, "Slot 4 (OpenRouter)", self.txt_api_key_4.text().strip() or retrieve_secret("nexus_openrouter_key") or "", or_model, "openrouter"),
            (5, "Slot 5 (Groq Cloud)", self.txt_api_key_5.text().strip() or retrieve_secret("nexus_groq_key") or "", groq_model, "groq"),
        ]

        active_tests = [t for t in keys_to_test if t[2]]
        if not active_tests:
            QMessageBox.warning(self, "No Keys Configured", "Please enter at least one API key before testing.")
            return

        self.btn_test_conn.setEnabled(False)
        self.lbl_test_result.setText("⏳ Testing all configured API connections in parallel...")
        self.lbl_test_result.setStyleSheet("color: #F59E0B; font-weight: 600;")

        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = []
            for slot, name, key, model, prov in active_tests:
                slot_enabled = get_setting(f"ai_slot_{slot}_enabled", "1") == "1"
                if not slot_enabled:
                    results.append((name, None, "Disabled / Paused (Switch OFF)", 0.0))
                    continue
                ok, msg, lat = loop.run_until_complete(test_ai_connection(key, model, prov))
                results.append((name, ok, msg, lat))
            loop.close()

            # Format summary cleanly so it wraps nicely
            lines = []
            all_ok = True
            for name, ok, msg, lat in results:
                if ok is None:
                    lines.append(f"⚪ {name}: Disabled / Paused (Switch OFF)")
                elif ok:
                    lines.append(f"🟢 {name}: OK ({lat:.2f}s)")
                else:
                    all_ok = False
                    clean_err = msg.replace("\n", " ").strip()
                    if "401" in clean_err:
                        clean_err = "Project Suspended / Invalid Key (401)"
                    elif "429" in clean_err:
                        clean_err = "Rate Limited / Quota (429)"
                    elif "404" in clean_err:
                        clean_err = "Model Not Found (404)"
                    elif "ReadTimeout" in clean_err:
                        clean_err = "Timeout (>10s) — Turn Switch OFF to Skip"
                    elif len(clean_err) > 40:
                        clean_err = clean_err[:40] + "..."
                    lines.append(f"🔴 {name}: {clean_err}")
            
            summary_text = "\n".join(lines)
            self.test_result_signal.emit(all_ok, summary_text, 0.0)

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_result(self, success: bool, msg: str, latency: float):
        self.btn_test_conn.setEnabled(True)
        self.lbl_test_result.setText(msg)
        if success:
            self.lbl_test_result.setStyleSheet("color: #22C55E; font-weight: 600; font-size: 11px; padding: 6px; border-radius: 4px; background: rgba(22, 27, 34, 0.8); line-height: 1.5;")
        else:
            self.lbl_test_result.setStyleSheet("color: #F59E0B; font-weight: 600; font-size: 11px; padding: 6px; border-radius: 4px; background: rgba(22, 27, 34, 0.8); line-height: 1.5;")

    def _save_settings(self):
        is_master = "1" if self.tog_ai_master.isChecked() else "0"
        set_setting("ai_master_enabled", is_master)
        set_setting("ai_fallback_enabled", is_master)

        selected_mode = "ai_only" if self.cmb_operating_mode.currentIndex() == 1 else "hybrid"
        set_setting("ai_operating_mode", selected_mode)
        set_setting("ai_model_name", self.txt_model_id.text().strip() or "gemini-3.5-flash-lite")
        set_setting("openrouter_model_name", self.txt_model_openrouter.text().strip() or "nvidia/nemotron-3-super-120b-a12b:free")
        set_setting("groq_model_name", self.txt_model_groq.text().strip() or "openai/gpt-oss-20b")

    def _save_all_ai_settings(self):
        self._save_settings()
        set_setting("ai_system_context", self.txt_system_context.toPlainText().strip())

        # Save all 5 key slots
        k1 = self.txt_api_key_1.text().strip()
        if k1:
            store_secret("nexus_ai_key", k1)

        k2 = self.txt_api_key_2.text().strip()
        if k2:
            store_secret("nexus_ai_key_2", k2)

        k3 = self.txt_api_key_3.text().strip()
        if k3:
            store_secret("nexus_ai_key_3", k3)

        k4 = self.txt_api_key_4.text().strip()
        if k4:
            store_secret("nexus_openrouter_key", k4)

        k5 = self.txt_api_key_5.text().strip()
        if k5:
            store_secret("nexus_groq_key", k5)

        self._update_pool_status_badge()
        QMessageBox.information(self, "Vault Saved", "All 5 API key slots and AI configuration saved securely!")

