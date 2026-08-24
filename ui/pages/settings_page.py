from urllib.parse import urlparse
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QPushButton, QMessageBox, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt
from database import get_setting, set_setting
from vault import store_secret, retrieve_secret
from ui.theme import COLOR_AMBER_ALERT
from ui.widgets.toggle_switch import ToggleSwitch
from waha_launcher import WAHALauncher


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

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
        v_url.addWidget(QLabel("GATEWAY SERVER BASE URL:"))
        self.txt_waha_url = QLineEdit()
        self.txt_waha_url.setPlaceholderText("http://localhost:3000")
        v_url.addWidget(self.txt_waha_url)
        row_waha.addLayout(v_url, stretch=2)

        v_wkey = QVBoxLayout()
        v_wkey.setSpacing(4)
        v_wkey.addWidget(QLabel("GATEWAY API KEY (X-Api-Key):"))
        self.txt_waha_key = QLineEdit()
        self.txt_waha_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_waha_key.setPlaceholderText("Optional API Key...")
        v_wkey.addWidget(self.txt_waha_key)
        row_waha.addLayout(v_wkey, stretch=2)

        btn_save_waha = QPushButton("Save Gateway Configuration")
        btn_save_waha.setObjectName("btnSecondary")
        btn_save_waha.clicked.connect(self._save_waha_settings)
        row_waha.addWidget(btn_save_waha, stretch=1)

        waha_layout.addLayout(row_waha)

        btn_launch = QPushButton("Initialize WhatsApp Gateway Engine")
        btn_launch.setObjectName("btnPrimary")
        btn_launch.setMinimumHeight(38)
        btn_launch.clicked.connect(self._launch_waha_action)
        waha_layout.addWidget(btn_launch)

        layout.addWidget(card_waha)

        # 3. Enterprise Automation & Filter Controls Frame
        card_safety = QFrame()
        card_safety.setObjectName("cardFrame")
        safety_layout = QVBoxLayout(card_safety)
        safety_layout.setContentsMargins(18, 18, 18, 18)
        safety_layout.setSpacing(16)

        lbl_safety_title = QLabel("Enterprise Automation & Filter Controls")
        lbl_safety_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F0F6FC;")
        safety_layout.addWidget(lbl_safety_title)

        toggles_grid = QVBoxLayout()
        toggles_grid.setSpacing(14)

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
        lbl_grp_sub = QLabel("Automated replies only for 1-on-1 customer chats, not group messages.")
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

        # Toggle Row 2: Auto-Start Engine
        row_auto = QHBoxLayout()
        row_auto.setSpacing(14)
        self.tog_autostart = ToggleSwitch(checked=True)
        row_auto.addWidget(self.tog_autostart)
        v_auto = QVBoxLayout()
        v_auto.setSpacing(2)
        lbl_auto = QLabel("Auto-Start Gateway Engine on Launch")
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

        # Toggle Row 3: Per-Customer Reply Cooldown (Feature 1)
        row_cd = QHBoxLayout()
        row_cd.setSpacing(14)
        self.tog_cooldown = ToggleSwitch(checked=True)
        row_cd.addWidget(self.tog_cooldown)
        v_cd = QVBoxLayout()
        v_cd.setSpacing(2)
        lbl_cd = QLabel("Per-Customer Reply Cooldown (Feature 1)")
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

        # Toggle Row 4: Human VA Takeover Mode (Feature 2)
        row_ht = QHBoxLayout()
        row_ht.setSpacing(14)
        self.tog_takeover = ToggleSwitch(checked=True)
        row_ht.addWidget(self.tog_takeover)
        v_ht = QVBoxLayout()
        v_ht.setSpacing(2)
        lbl_ht = QLabel("Human VA Manual Takeover Mode (Feature 2)")
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

        # 4. Compliance & Risk Notice Frame
        warn_frame = QFrame()
        warn_frame.setStyleSheet(
            f"background-color: rgba(245, 158, 11, 0.08); border: 1px solid {COLOR_AMBER_ALERT}; border-radius: 8px; padding: 12px;"
        )
        wf_layout = QVBoxLayout(warn_frame)
        wf_layout.setSpacing(6)

        lbl_warn_title = QLabel("⚠️ Compliance & Safety Notice")
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
