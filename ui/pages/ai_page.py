from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QLineEdit, QTextEdit, QPushButton, QMessageBox, QFrame
)
from database import get_setting, set_setting
from vault import store_secret, retrieve_secret
from ui.widgets.toggle_switch import ToggleSwitch

class AIPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

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

        self.tog_ai_master = ToggleSwitch(checked=False)
        row_master.addWidget(self.tog_ai_master)

        v_m_title = QVBoxLayout()
        v_m_title.setSpacing(2)
        lbl_m_title = QLabel("AI Engine Master Switch")
        lbl_m_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #F0F6FC;")
        v_m_title.addWidget(lbl_m_title)
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
        v_mode.addWidget(self.cmb_operating_mode)
        row_mode.addLayout(v_mode, stretch=2)

        lbl_mode_desc = QLabel(
            "• Hybrid: Rule Book executes first. AI responds ONLY if no static rule matches.\n"
            "• Exclusive AI: Bypasses static rules and generates all replies via AI."
        )
        lbl_mode_desc.setStyleSheet("font-size: 11px; color: #8B949E;")
        row_mode.addWidget(lbl_mode_desc, stretch=3)

        card_layout.addLayout(row_mode)

        # Provider & Model Row
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

        # API Key Vault Input
        v_key = QVBoxLayout()
        v_key.setSpacing(4)
        lbl_key = QLabel("ACCESS API KEY TOKEN (Stored in OS Keychain Vault):")
        lbl_key.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v_key.addWidget(lbl_key)

        key_layout = QHBoxLayout()
        key_layout.setSpacing(10)

        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setPlaceholderText("Paste secret API key here...")
        key_layout.addWidget(self.txt_api_key, stretch=3)

        btn_save_key = QPushButton("Save Key to Vault")
        btn_save_key.setObjectName("btnSecondary")
        btn_save_key.clicked.connect(self._save_key_to_vault)
        key_layout.addWidget(btn_save_key, stretch=1)

        v_key.addLayout(key_layout)
        card_layout.addLayout(v_key)

        # System Knowledge Base Sandbox
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
            "• Shipping Charges: Flat Rs. 200 across all cities in Pakistan (Lahore, Karachi, Islamabad, Faisalabad, etc.).\n"
            "• Delivery Time: 2 to 4 working days via Leopards / TCS Courier.\n"
            "• Payment Method: Cash on Delivery (COD) available for all non-customized items.\n\n"
            "CUSTOMIZED PRODUCTS (Photo Watches / Custom Hoodies):\n"
            "• Customized items require Rs. 500 advance payment via JazzCash or EasyPaisa to prevent fake orders.\n"
            "• Remaining balance Cash on Delivery pe pay hoga.\n\n"
            "RETURN & EXCHANGE POLICY:\n"
            "• 7 Days Return & Replacement Guarantee in case of size issues or damaged product.\n"
            "• Customer must send unboxing video on WhatsApp for instant exchange."
        )
        self.txt_system_context.setMinimumHeight(200)
        v_ctx.addWidget(self.txt_system_context)

        card_layout.addLayout(v_ctx)

        # Save Button
        btn_save_all = QPushButton("Save AI Configuration & Knowledge Base")
        btn_save_all.setObjectName("btnPrimary")
        btn_save_all.setMinimumHeight(38)
        btn_save_all.clicked.connect(self._save_all_ai_settings)
        card_layout.addWidget(btn_save_all)

        layout.addWidget(card)
        layout.addStretch()

        self.load_settings()

    def load_settings(self):
        master_on = get_setting("ai_master_enabled", get_setting("ai_fallback_enabled", "0")) == "1"
        self.tog_ai_master.setChecked(master_on)

        op_mode = get_setting("ai_operating_mode", "hybrid")
        if op_mode == "ai_only":
            self.cmb_operating_mode.setCurrentIndex(1)
        else:
            self.cmb_operating_mode.setCurrentIndex(0)

        provider = get_setting("ai_provider", "gemini").lower()
        for i in range(self.cmb_provider.count()):
            if self.cmb_provider.itemText(i).lower() == provider:
                self.cmb_provider.setCurrentIndex(i)
                break

        model = get_setting("ai_model_name", "gemini-3.5-flash-lite")
        # Normalize deprecated/dead model names
        if model in ("gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"):
            model = "gemini-3.5-flash-lite"
        self.txt_model_id.setText(model)

        context = get_setting("ai_system_context", "")
        self.txt_system_context.setText(context)

        key_ref = get_setting("ai_api_key_ref", "nexus_ai_key")
        existing_key = retrieve_secret(key_ref)
        if existing_key:
            self.txt_api_key.setText(existing_key)

    def _save_key_to_vault(self):
        secret = self.txt_api_key.text().strip()
        key_ref = get_setting("ai_api_key_ref", "nexus_ai_key")
        if store_secret(key_ref, secret):
            QMessageBox.information(self, "Vault Saved", "API Key stored securely in OS Keychain Vault!")
        else:
            QMessageBox.critical(self, "Vault Error", "Failed to store API Key in credential vault.")

    def _save_settings(self):
        is_master = "1" if self.tog_ai_master.isChecked() else "0"
        set_setting("ai_master_enabled", is_master)
        set_setting("ai_fallback_enabled", is_master) # backwards compatibility

        selected_mode = "ai_only" if self.cmb_operating_mode.currentIndex() == 1 else "hybrid"
        set_setting("ai_operating_mode", selected_mode)
        set_setting("ai_provider", self.cmb_provider.currentText().lower())
        set_setting("ai_model_name", self.txt_model_id.text().strip() or "gemini-3.5-flash-lite")

    def _save_all_ai_settings(self):
        self._save_settings()
        set_setting("ai_system_context", self.txt_system_context.toPlainText().strip())
        secret = self.txt_api_key.text().strip()
        if secret:
            key_ref = get_setting("ai_api_key_ref", "nexus_ai_key")
            store_secret(key_ref, secret)
        QMessageBox.information(self, "Settings Saved", "AI Assistant configuration saved successfully!")
