import asyncio
import threading
from urllib.parse import urlparse
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QPushButton, QMessageBox, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from database import get_setting, set_setting
from vault import store_secret, retrieve_secret
from ui.theme import COLOR_AMBER_ALERT
from ui.widgets.toggle_switch import ToggleSwitch
from waha_launcher import WAHALauncher
from postex_client import PostExClient


class SettingsPage(QWidget):
    postex_test_signal = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.postex_test_signal.connect(self._on_postex_test_result)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Page Header
        hdr_layout = QHBoxLayout()
        title = QLabel("Settings & Compliance")
        title.setObjectName("pageTitle")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        layout.addLayout(hdr_layout)

        # 1. Send-Rate Governor Settings Frame
        card_gov = QFrame()
        card_gov.setObjectName("cardFrame")
        gov_layout = QVBoxLayout(card_gov)
        gov_layout.setContentsMargins(18, 18, 18, 18)
        gov_layout.setSpacing(12)

        lbl_gov_title = QLabel("Send-Rate Governor Rules")
        lbl_gov_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F0F6FC;")
        gov_layout.addWidget(lbl_gov_title)

        row_gov = QHBoxLayout()
        row_gov.setSpacing(14)

        v1 = QVBoxLayout()
        v1.setSpacing(4)
        lbl1 = QLabel("MINIMUM DELAY (SEC):")
        lbl1.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v1.addWidget(lbl1)
        self.spn_min_delay = QDoubleSpinBox()
        self.spn_min_delay.setRange(0.0, 60.0)
        self.spn_min_delay.setSingleStep(0.5)
        self.spn_min_delay.setValue(2.5)
        v1.addWidget(self.spn_min_delay)
        row_gov.addLayout(v1)

        v2 = QVBoxLayout()
        v2.setSpacing(4)
        lbl2 = QLabel("RANDOM JITTER (±SEC):")
        lbl2.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v2.addWidget(lbl2)
        self.spn_jitter = QDoubleSpinBox()
        self.spn_jitter.setRange(0.0, 30.0)
        self.spn_jitter.setSingleStep(0.5)
        self.spn_jitter.setValue(1.5)
        v2.addWidget(self.spn_jitter)
        row_gov.addLayout(v2)

        v3 = QVBoxLayout()
        v3.setSpacing(4)
        lbl3 = QLabel("DAILY SEND CAP (MESSAGES):")
        lbl3.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v3.addWidget(lbl3)
        self.spn_daily_cap = QSpinBox()
        self.spn_daily_cap.setRange(1, 10000)
        self.spn_daily_cap.setValue(800)
        v3.addWidget(self.spn_daily_cap)
        row_gov.addLayout(v3)

        btn_save_gov = QPushButton("Save Governor Configuration")
        btn_save_gov.setObjectName("btnPrimary")
        btn_save_gov.clicked.connect(self._save_governor_settings)
        row_gov.addWidget(btn_save_gov)

        gov_layout.addLayout(row_gov)
        layout.addWidget(card_gov)

        # 2. Gateway Endpoint & Server Configuration Frame
        card_waha = QFrame()
        card_waha.setObjectName("cardFrame")
        waha_layout = QVBoxLayout(card_waha)
        waha_layout.setContentsMargins(18, 18, 18, 18)
        waha_layout.setSpacing(12)

        lbl_waha_title = QLabel("WhatsApp Gateway Server Configuration")
        lbl_waha_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F0F6FC;")
        waha_layout.addWidget(lbl_waha_title)

        row_waha = QHBoxLayout()
        row_waha.setSpacing(14)

        v_url = QVBoxLayout()
        v_url.setSpacing(4)
        lbl_url = QLabel("GATEWAY BASE URL:")
        lbl_url.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v_url.addWidget(lbl_url)
        self.txt_waha_url = QLineEdit("http://localhost:3000")
        v_url.addWidget(self.txt_waha_url)
        row_waha.addLayout(v_url, stretch=2)

        v_key = QVBoxLayout()
        v_key.setSpacing(4)
        lbl_key = QLabel("GATEWAY API KEY:")
        lbl_key.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v_key.addWidget(lbl_key)
        self.txt_waha_key = QLineEdit()
        self.txt_waha_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_waha_key.setPlaceholderText("Optional API key")
        v_key.addWidget(self.txt_waha_key)
        row_waha.addLayout(v_key, stretch=2)

        btn_save_waha = QPushButton("Save Endpoint")
        btn_save_waha.setObjectName("btnPrimary")
        btn_save_waha.clicked.connect(self._save_waha_settings)
        row_waha.addWidget(btn_save_waha)

        btn_launch = QPushButton("▶ Launch Engine Process")
        btn_launch.setObjectName("btnSecondary")
        btn_launch.clicked.connect(self._launch_waha_action)
        row_waha.addWidget(btn_launch)

        waha_layout.addLayout(row_waha)
        layout.addWidget(card_waha)

        # 3. Message & Audience Safety Controls
        card_safety = QFrame()
        card_safety.setObjectName("cardFrame")
        safety_layout = QVBoxLayout(card_safety)
        safety_layout.setContentsMargins(18, 18, 18, 18)
        safety_layout.setSpacing(14)

        lbl_safety_title = QLabel("Message & Audience Safety Controls")
        lbl_safety_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F0F6FC;")
        safety_layout.addWidget(lbl_safety_title)

        toggles_grid = QVBoxLayout()
        toggles_grid.setSpacing(12)

        # Toggle Row 1: Ignore Group Messages
        row_grp = QHBoxLayout()
        row_grp.setSpacing(14)
        self.tog_ignore_groups = ToggleSwitch(checked=True)
        row_grp.addWidget(self.tog_ignore_groups)
        v_grp = QVBoxLayout()
        v_grp.setSpacing(2)
        lbl_grp = QLabel("Ignore Group Messages")
        lbl_grp.setStyleSheet("font-weight: 700; font-size: 13px; color: #F0F6FC;")
        v_grp.addWidget(lbl_grp)
        lbl_grp_sub = QLabel("Do not trigger auto-replies or AI responses inside group chats.")
        lbl_grp_sub.setStyleSheet("font-size: 11px; color: #8B949E;")
        v_grp.addWidget(lbl_grp_sub)
        row_grp.addLayout(v_grp)
        row_grp.addStretch()
        toggles_grid.addLayout(row_grp)

        # Divider line
        div1 = QFrame()
        div1.setFixedHeight(1)
        div1.setStyleSheet("background-color: #21262D; border: none;")
        toggles_grid.addWidget(div1)

        # Toggle Row 2: Auto-Start Engine on App Launch
        row_auto = QHBoxLayout()
        row_auto.setSpacing(14)
        self.tog_autostart = ToggleSwitch(checked=True)
        row_auto.addWidget(self.tog_autostart)
        v_auto = QVBoxLayout()
        v_auto.setSpacing(2)
        lbl_auto = QLabel("Auto-Start WhatsApp Engine on Launch")
        lbl_auto.setStyleSheet("font-weight: 700; font-size: 13px; color: #F0F6FC;")
        v_auto.addWidget(lbl_auto)
        lbl_auto_sub = QLabel("Automatically launch the Baileys WhatsApp engine when CyberSolu Auto starts.")
        lbl_auto_sub.setStyleSheet("font-size: 11px; color: #8B949E;")
        v_auto.addWidget(lbl_auto_sub)
        row_auto.addLayout(v_auto)
        row_auto.addStretch()
        toggles_grid.addLayout(row_auto)

        # Divider line
        div2 = QFrame()
        div2.setFixedHeight(1)
        div2.setStyleSheet("background-color: #21262D; border: none;")
        toggles_grid.addWidget(div2)

        # Toggle Row 3: Per-Customer Reply Cooldown
        row_cd = QHBoxLayout()
        row_cd.setSpacing(14)
        self.tog_cooldown = ToggleSwitch(checked=True)
        row_cd.addWidget(self.tog_cooldown)
        v_cd = QVBoxLayout()
        v_cd.setSpacing(2)
        lbl_cd = QLabel("Per-Customer Reply Cooldown")
        lbl_cd.setStyleSheet("font-weight: 700; font-size: 13px; color: #F0F6FC;")
        v_cd.addWidget(lbl_cd)
        lbl_cd_sub = QLabel("Prevents sending the exact same auto-reply to a customer within the cooldown duration.")
        lbl_cd_sub.setStyleSheet("font-size: 11px; color: #8B949E;")
        v_cd.addWidget(lbl_cd_sub)
        row_cd.addLayout(v_cd)
        row_cd.addStretch()

        self.spn_cooldown_mins = QSpinBox()
        self.spn_cooldown_mins.setRange(1, 1440)
        self.spn_cooldown_mins.setSuffix(" Mins")
        self.spn_cooldown_mins.setValue(1)
        self.spn_cooldown_mins.setFixedWidth(90)
        row_cd.addWidget(self.spn_cooldown_mins)
        toggles_grid.addLayout(row_cd)

        # Divider line
        div3 = QFrame()
        div3.setFixedHeight(1)
        div3.setStyleSheet("background-color: #21262D; border: none;")
        toggles_grid.addWidget(div3)

        # Toggle Row 4: Human VA Takeover Mode
        row_ht = QHBoxLayout()
        row_ht.setSpacing(14)
        self.tog_takeover = ToggleSwitch(checked=True)
        row_ht.addWidget(self.tog_takeover)
        v_ht = QVBoxLayout()
        v_ht.setSpacing(2)
        lbl_ht = QLabel("Human VA Manual Takeover Mode")
        lbl_ht.setStyleSheet("font-weight: 700; font-size: 13px; color: #F0F6FC;")
        v_ht.addWidget(lbl_ht)
        lbl_ht_sub = QLabel("Automatically pauses bot auto-replies for a contact when a human VA manually replies.")
        lbl_ht_sub.setStyleSheet("font-size: 11px; color: #8B949E;")
        v_ht.addWidget(lbl_ht_sub)
        row_ht.addLayout(v_ht)
        row_ht.addStretch()

        self.spn_takeover_mins = QSpinBox()
        self.spn_takeover_mins.setRange(1, 1440)
        self.spn_takeover_mins.setSuffix(" Mins")
        self.spn_takeover_mins.setValue(5)
        self.spn_takeover_mins.setFixedWidth(90)
        row_ht.addWidget(self.spn_takeover_mins)
        toggles_grid.addLayout(row_ht)

        safety_layout.addLayout(toggles_grid)

        btn_save_safety = QPushButton("Save Automation Controls")
        btn_save_safety.setObjectName("btnSecondary")
        btn_save_safety.setMinimumHeight(36)
        btn_save_safety.clicked.connect(self._save_safety_settings)
        safety_layout.addWidget(btn_save_safety)

        layout.addWidget(card_safety)

        # =====================================================================
        # 4. PostEx Courier Automated Parcel Tracking Integration Card
        # =====================================================================
        card_postex = QFrame()
        card_postex.setObjectName("cardFrame")
        postex_layout = QVBoxLayout(card_postex)
        postex_layout.setContentsMargins(18, 18, 18, 18)
        postex_layout.setSpacing(12)

        # Title Row with Master Toggle
        row_p_title = QHBoxLayout()
        lbl_p_title = QLabel("📦 PostEx Courier Automated Parcel Tracking")
        lbl_p_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F0F6FC;")
        row_p_title.addWidget(lbl_p_title)
        row_p_title.addStretch()

        self.tog_postex = ToggleSwitch(checked=True)
        row_p_title.addWidget(self.tog_postex)
        postex_layout.addLayout(row_p_title)

        lbl_p_desc = QLabel(
            "Automatically queries PostEx APIs and replies to customer parcel inquiries on WhatsApp with live status.\n"
            "Recognizes Order IDs from saved contacts (e.g. '2250', '121012') and message text. Gracefully skips TCS and unbooked orders."
        )
        lbl_p_desc.setStyleSheet("font-size: 12px; color: #8B949E; line-height: 1.4;")
        postex_layout.addWidget(lbl_p_desc)

        # Token Input Row
        row_token = QHBoxLayout()
        row_token.setSpacing(10)

        v_tok = QVBoxLayout()
        v_tok.setSpacing(4)
        lbl_tok = QLabel("POSTEX MERCHANT API TOKEN:")
        lbl_tok.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v_tok.addWidget(lbl_tok)

        row_inp = QHBoxLayout()
        self.inp_postex_token = QLineEdit()
        self.inp_postex_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_postex_token.setPlaceholderText("Paste your PostEx API Token from merchant portal...")
        self.inp_postex_token.setStyleSheet("""
            QLineEdit {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                color: #F0F6FC;
                font-size: 12px;
            }
        """)
        row_inp.addWidget(self.inp_postex_token, stretch=1)

        self.btn_show_token = QPushButton("👁️")
        self.btn_show_token.setFixedWidth(36)
        self.btn_show_token.setFixedHeight(34)
        self.btn_show_token.setObjectName("btnSecondary")
        self.btn_show_token.clicked.connect(self._toggle_token_visibility)
        row_inp.addWidget(self.btn_show_token)

        v_tok.addLayout(row_inp)
        row_token.addLayout(v_tok, stretch=3)

        self.btn_test_postex = QPushButton("🔌 Test Connection")
        self.btn_test_postex.setObjectName("btnSecondary")
        self.btn_test_postex.setFixedHeight(34)
        self.btn_test_postex.clicked.connect(self._test_postex_connection)
        row_token.addWidget(self.btn_test_postex)

        self.btn_save_postex = QPushButton("Save PostEx Settings")
        self.btn_save_postex.setObjectName("btnPrimary")
        self.btn_save_postex.setFixedHeight(34)
        self.btn_save_postex.clicked.connect(self._save_postex_settings)
        row_token.addWidget(self.btn_save_postex)

        postex_layout.addLayout(row_token)

        self.lbl_postex_status = QLabel("")
        self.lbl_postex_status.setStyleSheet("font-size: 11px; font-weight: 600; padding: 2px;")
        postex_layout.addWidget(self.lbl_postex_status)

        layout.addWidget(card_postex)

        # 5. Compliance & Risk Notice Frame
        warn_frame = QFrame()
        warn_frame.setStyleSheet(
            f"background-color: rgba(245, 158, 11, 0.08); border: 1px solid {COLOR_AMBER_ALERT}; border-radius: 8px; padding: 12px;"
        )
        wf_layout = QVBoxLayout(warn_frame)
        wf_layout.setContentsMargins(14, 12, 14, 12)
        wf_layout.setSpacing(6)

        lbl_warn_title = QLabel("⚠️ Anti-Ban Safety Notice & Recommendations")
        lbl_warn_title.setStyleSheet(f"color: {COLOR_AMBER_ALERT}; font-weight: 700; font-size: 13px;")
        wf_layout.addWidget(lbl_warn_title)

        lbl_warn_text = QLabel(
            "WhatsApp enforces anti-automation algorithms to detect bot-like activity. To minimize the risk of account suspension:\n"
            "• Always use customer-initiated or opt-in messaging for business support.\n"
            "• Keep Send-Rate Governor delay rules active to maintain natural human-like dispatch intervals.\n"
            "• Ramp send volume gradually over 1–2 weeks for newly registered numbers."
        )
        lbl_warn_text.setWordWrap(True)
        lbl_warn_text.setStyleSheet("color: #F0F6FC; font-size: 12px;")
        wf_layout.addWidget(lbl_warn_text)

        layout.addWidget(warn_frame)
        layout.addStretch()

        self.load_settings()

    def load_settings(self):
        try:
            self.spn_min_delay.setValue(float(get_setting("send_min_delay_seconds", "2.5")))
        except ValueError:
            pass
        try:
            self.spn_jitter.setValue(float(get_setting("send_jitter_seconds", "1.5")))
        except ValueError:
            pass
        try:
            self.spn_daily_cap.setValue(int(get_setting("send_daily_cap", "800")))
        except ValueError:
            pass

        self.txt_waha_url.setText(get_setting("waha_url", "http://localhost:3000"))
        wkey_ref = get_setting("waha_api_key_ref", "nexus_waha_key")
        existing_wkey = retrieve_secret(wkey_ref)
        if existing_wkey:
            self.txt_waha_key.setText(existing_wkey)

        self.tog_ignore_groups.setChecked(get_setting("ignore_groups", "1") == "1")
        self.tog_autostart.setChecked(get_setting("autostart_engine", "1") == "1")
        self.tog_cooldown.setChecked(get_setting("cooldown_enabled", "1") == "1")
        try:
            self.spn_cooldown_mins.setValue(int(get_setting("cooldown_minutes", "1")))
        except ValueError:
            pass

        self.tog_takeover.setChecked(get_setting("human_takeover_enabled", "1") == "1")
        try:
            self.spn_takeover_mins.setValue(int(get_setting("human_takeover_minutes", "5")))
        except ValueError:
            pass

        # PostEx Settings
        self.tog_postex.setChecked(get_setting("postex_tracking_enabled", "1") == "1")
        postex_token = retrieve_secret("postex_api_token") or get_setting("postex_api_token", "")
        if postex_token:
            self.inp_postex_token.setText(postex_token)

    def _save_governor_settings(self):
        set_setting("send_min_delay_seconds", str(self.spn_min_delay.value()))
        set_setting("send_jitter_seconds", str(self.spn_jitter.value()))
        set_setting("send_daily_cap", str(self.spn_daily_cap.value()))
        QMessageBox.information(self, "Configuration Saved", "Send-Rate Governor parameters saved successfully!")

    def _save_waha_settings(self):
        w_url = self.txt_waha_url.text().strip() or "http://localhost:3000"
        if not w_url.startswith("http://") and not w_url.startswith("https://"):
            w_url = f"http://{w_url}"
        set_setting("waha_url", w_url)

        wkey = self.txt_waha_key.text().strip()
        wkey_ref = get_setting("waha_api_key_ref", "nexus_waha_key")
        if wkey:
            store_secret(wkey_ref, wkey)
        QMessageBox.information(self, "Configuration Saved", "Gateway connection settings saved successfully!")

    def _save_safety_settings(self):
        set_setting("ignore_groups", "1" if self.tog_ignore_groups.isChecked() else "0")
        set_setting("autostart_engine", "1" if self.tog_autostart.isChecked() else "0")
        set_setting("cooldown_enabled", "1" if self.tog_cooldown.isChecked() else "0")
        set_setting("cooldown_minutes", str(self.spn_cooldown_mins.value()))
        set_setting("human_takeover_enabled", "1" if self.tog_takeover.isChecked() else "0")
        set_setting("human_takeover_minutes", str(self.spn_takeover_mins.value()))
        QMessageBox.information(self, "Configuration Saved", "Automation & Filter controls saved successfully!")

    def _toggle_token_visibility(self):
        if self.inp_postex_token.echoMode() == QLineEdit.EchoMode.Password:
            self.inp_postex_token.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_show_token.setText("🔒")
        else:
            self.inp_postex_token.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_show_token.setText("👁️")

    def _save_postex_settings(self):
        token_str = self.inp_postex_token.text().strip()
        is_enabled = "1" if self.tog_postex.isChecked() else "0"
        
        set_setting("postex_tracking_enabled", is_enabled)
        if token_str:
            store_secret("postex_api_token", token_str)
            set_setting("postex_api_token", token_str)

        QMessageBox.information(
            self, "PostEx Settings Saved",
            "PostEx Courier automated tracking settings saved successfully!"
        )

    def _test_postex_connection(self):
        token_str = self.inp_postex_token.text().strip()
        if not token_str:
            QMessageBox.warning(self, "Missing Token", "Please paste your PostEx API Token first.")
            return

        self.btn_test_postex.setEnabled(False)
        self.btn_test_postex.setText("⏳ Testing...")
        self.lbl_postex_status.setText("Connecting to PostEx Merchant API...")
        self.lbl_postex_status.setStyleSheet("color: #F59E0B;")

        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                client = PostExClient(token=token_str)
                ok, msg = loop.run_until_complete(client.test_connection(token=token_str))
                loop.close()
                self.postex_test_signal.emit(ok, msg)
            except Exception as e:
                loop.close()
                self.postex_test_signal.emit(False, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_postex_test_result(self, ok: bool, msg: str):
        self.btn_test_postex.setEnabled(True)
        self.btn_test_postex.setText("🔌 Test Connection")

        if ok:
            self.lbl_postex_status.setText(f"● {msg}")
            self.lbl_postex_status.setStyleSheet("color: #22C55E; font-weight: 700;")
            QMessageBox.information(self, "PostEx API Connected", f"✅ {msg}")
        else:
            self.lbl_postex_status.setText(f"● {msg}")
            self.lbl_postex_status.setStyleSheet("color: #EF4444; font-weight: 700;")
            QMessageBox.warning(self, "PostEx Connection Failed", f"❌ {msg}")

    def _launch_waha_action(self):
        url_str = self.txt_waha_url.text().strip() or "http://localhost:3000"
        if not url_str.startswith("http://") and not url_str.startswith("https://"):
            url_str = f"http://{url_str}"
        set_setting("waha_url", url_str)

        try:
            parsed = urlparse(url_str)
            target_port = parsed.port or 3000
        except Exception:
            target_port = 3000

        success, message = WAHALauncher.start_waha_engine(port=target_port)
        if success:
            QMessageBox.information(self, "Gateway Manager", message)
        else:
            QMessageBox.warning(
                self, "Gateway Launch Error",
                f"{message}\n\nPlease ensure Node.js is installed on your Windows PC."
            )
