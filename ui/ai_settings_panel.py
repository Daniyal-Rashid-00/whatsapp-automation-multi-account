from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QComboBox,
    QLineEdit, QTextEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import pyqtSignal
from database import get_setting, set_setting
from vault import store_secret, retrieve_secret

class AISettingsWidget(QGroupBox):
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("🤖 AI ENGINE & DEEP CONTEXT INTEGRATION (FALLBACK INTERCEPT)", parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(10)

        # AI Fallback Toggle Checkbox
        self.chk_ai_enabled = QCheckBox("Enable Generative AI Fallback Engine (Intercepts unmatched messages)")
        self.chk_ai_enabled.setStyleSheet("font-weight: 700; color: #00F0FF;")
        self.chk_ai_enabled.stateChanged.connect(self._save_settings)
        layout.addWidget(self.chk_ai_enabled)

        # Provider & Model ID Row
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        v1 = QVBoxLayout()
        v1.setSpacing(4)
        lbl_prov = QLabel("AI PROVIDER:")
        lbl_prov.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        v1.addWidget(lbl_prov)
        self.cmb_provider = QComboBox()
        self.cmb_provider.addItems(["Gemini", "OpenRouter"])
        self.cmb_provider.currentTextChanged.connect(self._save_settings)
        v1.addWidget(self.cmb_provider)
        row1.addLayout(v1, stretch=1)

        v2 = QVBoxLayout()
        v2.setSpacing(4)
        lbl_mod = QLabel("MODEL ID OVERRIDE:")
        lbl_mod.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        v2.addWidget(lbl_mod)
        self.txt_model_id = QLineEdit()
        self.txt_model_id.setPlaceholderText("e.g. gemini-3.5-flash — check deprecations")
        self.txt_model_id.editingFinished.connect(self._save_settings)
        v2.addWidget(self.txt_model_id)
        row1.addLayout(v2, stretch=2)

        layout.addLayout(row1)

        # API Key Input & Keyring Vault Handle
        v_key = QVBoxLayout()
        v_key.setSpacing(4)
        lbl_key = QLabel("ACCESS AUTHENTICATION TOKEN (Encrypted in OS Keychain Vault):")
        lbl_key.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        v_key.addWidget(lbl_key)
        
        key_input_layout = QHBoxLayout()
        key_input_layout.setSpacing(8)
        
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setPlaceholderText("Paste API key here...")
        key_input_layout.addWidget(self.txt_api_key, stretch=3)

        btn_save_key = QPushButton("🔐 Save to Keyring")
        btn_save_key.setObjectName("btnSecondary")
        btn_save_key.clicked.connect(self._save_key_to_vault)
        key_input_layout.addWidget(btn_save_key, stretch=1)

        v_key.addLayout(key_input_layout)
        layout.addLayout(v_key)

        # Knowledge Context Sandbox Text Editor
        lbl_ctx = QLabel("SYSTEM KNOWLEDGE CONTEXT SANDBOX (Pricing, SOPs, Return Policies):")
        lbl_ctx.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        layout.addWidget(lbl_ctx)
        
        self.txt_system_context = QTextEdit()
        self.txt_system_context.setPlaceholderText(
            "Store: VoltCom Apparel. Return Policy: 14 days post delivery.\nDomestic Shipping Rates: Flat 150 PKR across Pakistan via courier routes."
        )
        self.txt_system_context.setMaximumHeight(80)
        layout.addWidget(self.txt_system_context)

        # Save System Context Button
        btn_save_context = QPushButton("💾 SAVE AI CONFIGURATION & CONTEXT")
        btn_save_context.setObjectName("btnPrimary")
        btn_save_context.setMinimumHeight(36)
        btn_save_context.clicked.connect(self._save_all_ai_settings)
        layout.addWidget(btn_save_context)

        self.load_settings()

    def load_settings(self):
        ai_on = get_setting("ai_fallback_enabled", "0") == "1"
        self.chk_ai_enabled.setChecked(ai_on)

        provider = get_setting("ai_provider", "gemini").lower()
        for i in range(self.cmb_provider.count()):
            if self.cmb_provider.itemText(i).lower() == provider:
                self.cmb_provider.setCurrentIndex(i)
                break

        model = get_setting("ai_model_name", "gemini-3.5-flash")
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
            QMessageBox.information(self, "Vault Secured", "API Key stored securely in OS Keychain Vault!")
            self.settings_changed.emit()
        else:
            QMessageBox.critical(self, "Vault Error", "Failed to store API Key in credential vault.")

    def _save_settings(self):
        set_setting("ai_fallback_enabled", "1" if self.chk_ai_enabled.isChecked() else "0")
        set_setting("ai_provider", self.cmb_provider.currentText().lower())
        set_setting("ai_model_name", self.txt_model_id.text().strip() or "gemini-3.5-flash")

    def _save_all_ai_settings(self):
        self._save_settings()
        set_setting("ai_system_context", self.txt_system_context.toPlainText().strip())
        secret = self.txt_api_key.text().strip()
        if secret:
            key_ref = get_setting("ai_api_key_ref", "nexus_ai_key")
            store_secret(key_ref, secret)
        QMessageBox.information(self, "Settings Saved", "AI Fallback Configuration & System Context saved successfully!")
        self.settings_changed.emit()
