from urllib.parse import urlparse
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QPushButton, QMessageBox, QFrame, QLineEdit, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox
)
from PyQt6.QtCore import Qt
from database import (
    get_setting, set_setting, get_all_accounts,
    add_excluded_number, remove_excluded_number, get_all_excluded_numbers
)
from vault import store_secret, retrieve_secret
from ui.theme import COLOR_AMBER_ALERT, COLOR_DARK_BG
from ui.widgets.toggle_switch import ToggleSwitch
from waha_launcher import WAHALauncher


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Root layout holding the responsive scroll area
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Smooth Scroll Area ensuring 100% responsiveness on any resolution
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {COLOR_DARK_BG};
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #21262D;
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #30363D;
            }}
        """)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        scroll.setWidget(container)
        root_layout.addWidget(scroll)

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

        # 4. Ignored Numbers / Do Not Automate Frame
        card_ignored = QFrame()
        card_ignored.setObjectName("cardFrame")
        ign_layout = QVBoxLayout(card_ignored)
        ign_layout.setContentsMargins(18, 18, 18, 18)
        ign_layout.setSpacing(14)

        # Header with Title and Master Toggle
        ign_hdr = QHBoxLayout()
        ign_hdr.setSpacing(14)

        v_ign_title = QVBoxLayout()
        v_ign_title.setSpacing(2)
        lbl_ign_title = QLabel("🛡️ Ignored Numbers / Do Not Automate")
        lbl_ign_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F0F6FC;")
        v_ign_title.addWidget(lbl_ign_title)

        lbl_ign_sub = QLabel("Inbound messages from these phone numbers will be completely ignored (no auto-replies or AI responses). Perfect for employers, personal numbers, staff, or suppliers.")
        lbl_ign_sub.setStyleSheet("font-size: 11px; color: #8B949E;")
        lbl_ign_sub.setWordWrap(True)
        v_ign_title.addWidget(lbl_ign_sub)
        ign_hdr.addLayout(v_ign_title, stretch=1)

        v_tog = QVBoxLayout()
        v_tog.setSpacing(4)
        lbl_tog_state = QLabel("FILTER STATUS:")
        lbl_tog_state.setStyleSheet("font-weight: 600; font-size: 10px; color: #8B949E;")
        v_tog.addWidget(lbl_tog_state, alignment=Qt.AlignmentFlag.AlignRight)
        self.tog_ignored_numbers = ToggleSwitch(checked=True)
        self.tog_ignored_numbers.stateChanged.connect(self._on_ignored_toggle_changed)
        v_tog.addWidget(self.tog_ignored_numbers, alignment=Qt.AlignmentFlag.AlignRight)
        ign_hdr.addLayout(v_tog)

        ign_layout.addLayout(ign_hdr)

        # Divider line
        div_ign = QFrame()
        div_ign.setFixedHeight(1)
        div_ign.setStyleSheet("background-color: #21262D; border: none;")
        ign_layout.addWidget(div_ign)

        # Input Form Row
        form_row = QHBoxLayout()
        form_row.setSpacing(10)

        # 1. Phone Number Input
        v_inp_phone = QVBoxLayout()
        v_inp_phone.setSpacing(4)
        lbl_f_phone = QLabel("PHONE NUMBER:")
        lbl_f_phone.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v_inp_phone.addWidget(lbl_f_phone)
        self.txt_ign_phone = QLineEdit()
        self.txt_ign_phone.setPlaceholderText("e.g. 0300 1234567 or +923001234567")
        self.txt_ign_phone.setStyleSheet("""
            QLineEdit {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 7px 10px;
                color: #F0F6FC;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #3B82F6;
            }
        """)
        v_inp_phone.addWidget(self.txt_ign_phone)
        form_row.addLayout(v_inp_phone, stretch=3)

        # 2. Label / Note Input
        v_inp_lbl = QVBoxLayout()
        v_inp_lbl.setSpacing(4)
        lbl_f_tag = QLabel("LABEL / NOTE:")
        lbl_f_tag.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v_inp_lbl.addWidget(lbl_f_tag)
        self.txt_ign_label = QLineEdit()
        self.txt_ign_label.setPlaceholderText("e.g. Boss / Personal Phone")
        self.txt_ign_label.setStyleSheet("""
            QLineEdit {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 7px 10px;
                color: #F0F6FC;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #3B82F6;
            }
        """)
        v_inp_lbl.addWidget(self.txt_ign_label)
        form_row.addLayout(v_inp_lbl, stretch=3)

        # 3. Applies To Dropdown
        v_inp_tgt = QVBoxLayout()
        v_inp_tgt.setSpacing(4)
        lbl_f_tgt = QLabel("APPLIES TO:")
        lbl_f_tgt.setStyleSheet("font-weight: 600; font-size: 11px; color: #8B949E;")
        v_inp_tgt.addWidget(lbl_f_tgt)
        self.cmb_ign_target = QComboBox()
        self.cmb_ign_target.setStyleSheet("""
            QComboBox {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 10px;
                color: #F0F6FC;
                font-size: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #161B22;
                color: #F0F6FC;
                selection-background-color: #1F6FEB;
            }
        """)
        self._refresh_account_dropdown()
        v_inp_tgt.addWidget(self.cmb_ign_target)
        form_row.addLayout(v_inp_tgt, stretch=2)

        # 4. Add Button
        btn_add_num = QPushButton("+ Add Number")
        btn_add_num.setObjectName("btnPrimary")
        btn_add_num.setFixedHeight(34)
        btn_add_num.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_num.clicked.connect(self._add_excluded_number_clicked)
        form_row.addWidget(btn_add_num, alignment=Qt.AlignmentFlag.AlignBottom)

        ign_layout.addLayout(form_row)

        # Excluded Numbers Interactive Table
        self.tbl_ignored = QTableWidget()
        self.tbl_ignored.setColumnCount(5)
        self.tbl_ignored.setHorizontalHeaderLabels([
            "PHONE NUMBER", "LABEL / NOTE", "APPLIES TO", "ADDED DATE", "ACTION"
        ])
        self.tbl_ignored.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_ignored.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_ignored.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tbl_ignored.setColumnWidth(2, 140)
        self.tbl_ignored.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tbl_ignored.setColumnWidth(3, 140)
        self.tbl_ignored.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.tbl_ignored.setColumnWidth(4, 95)
        self.tbl_ignored.verticalHeader().setVisible(False)
        self.tbl_ignored.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.tbl_ignored.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tbl_ignored.setMinimumHeight(140)
        self.tbl_ignored.setMaximumHeight(260)
        self.tbl_ignored.setStyleSheet("""
            QTableWidget {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                gridline-color: #21262D;
                color: #F0F6FC;
            }
            QHeaderView::section {
                background-color: #161B22;
                color: #8B949E;
                font-weight: 700;
                font-size: 10px;
                border: none;
                border-bottom: 1px solid #30363D;
                padding: 6px;
            }
        """)
        ign_layout.addWidget(self.tbl_ignored)

        # Empty State Label
        self.lbl_ign_empty = QLabel("No numbers currently excluded. All inbound customer chats are eligible for automation.")
        self.lbl_ign_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_ign_empty.setStyleSheet("color: #8B949E; font-size: 12px; font-style: italic; padding: 12px;")
        ign_layout.addWidget(self.lbl_ign_empty)

        layout.addWidget(card_ignored)

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
        self._load_excluded_numbers()

    def _refresh_account_dropdown(self):
        """Populates the target account dropdown dynamically from database accounts."""
        self.cmb_ign_target.clear()
        self.cmb_ign_target.addItem("All Accounts (Global)", "ALL")
        try:
            accounts = get_all_accounts()
            for acc in accounts:
                s_name = acc.get("session_name", "")
                alias = acc.get("account_alias") or s_name
                if s_name:
                    self.cmb_ign_target.addItem(f"{alias} ({s_name})", s_name)
        except Exception:
            pass

    def _load_excluded_numbers(self):
        """Loads excluded numbers from database and renders them into the table."""
        try:
            records = get_all_excluded_numbers()
        except Exception:
            records = []

        self.tbl_ignored.setRowCount(len(records))

        if not records:
            self.tbl_ignored.setVisible(False)
            self.lbl_ign_empty.setVisible(True)
            return

        self.tbl_ignored.setVisible(True)
        self.lbl_ign_empty.setVisible(False)

        for row_idx, rec in enumerate(records):
            num_id = rec.get("id")
            phone = rec.get("phone_number", "")
            raw = rec.get("raw_input") or phone
            label_txt = rec.get("label") or "—"
            target = rec.get("account_target") or "ALL"
            created_at = str(rec.get("created_at") or "")[:16]

            # 0. Phone Item
            item_phone = QTableWidgetItem(f"+{phone}" if not phone.startswith("+") else phone)
            item_phone.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            item_phone.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item_phone.setToolTip(f"Raw Input: {raw}")
            self.tbl_ignored.setItem(row_idx, 0, item_phone)

            # 1. Label Item
            item_lbl = QTableWidgetItem(label_txt)
            item_lbl.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            item_lbl.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if label_txt != "—":
                item_lbl.setForeground(Qt.GlobalColor.white)
            else:
                item_lbl.setForeground(Qt.GlobalColor.gray)
            self.tbl_ignored.setItem(row_idx, 1, item_lbl)

            # 2. Applies To Item
            target_display = "🌐 All Accounts" if target == "ALL" else f"📱 {target}"
            item_tgt = QTableWidgetItem(target_display)
            item_tgt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_tgt.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tbl_ignored.setItem(row_idx, 2, item_tgt)

            # 3. Added Date Item
            item_date = QTableWidgetItem(created_at)
            item_date.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_date.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item_date.setForeground(Qt.GlobalColor.gray)
            self.tbl_ignored.setItem(row_idx, 3, item_date)

            # 4. Action (Delete Button)
            btn_delete = QPushButton("🗑️ Remove")
            btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_delete.setStyleSheet("""
                QPushButton {
                    background-color: #21262D;
                    color: #F85149;
                    border: 1px solid #30363D;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #4C0519;
                    color: #FECDD3;
                    border: 1px solid #F43F5E;
                }
            """)
            btn_delete.clicked.connect(lambda _, nid=num_id, r=raw: self._remove_excluded_number_clicked(nid, r))
            self.tbl_ignored.setCellWidget(row_idx, 4, btn_delete)
            self.tbl_ignored.setRowHeight(row_idx, 34)

    def _add_excluded_number_clicked(self):
        raw_phone = self.txt_ign_phone.text().strip()
        if not raw_phone:
            QMessageBox.warning(self, "Missing Phone Number", "Please enter a phone number to exclude.")
            self.txt_ign_phone.setFocus()
            return

        label = self.txt_ign_label.text().strip()
        target = self.cmb_ign_target.currentData() or "ALL"

        success, msg = add_excluded_number(raw_phone, label=label, account_target=target)
        if success:
            self.txt_ign_phone.clear()
            self.txt_ign_label.clear()
            self._load_excluded_numbers()
        else:
            QMessageBox.warning(self, "Cannot Add Number", msg)

    def _remove_excluded_number_clicked(self, number_id: int, raw_num: str):
        reply = QMessageBox.question(
            self,
            "Remove Excluded Number",
            f"Are you sure you want to remove '{raw_num}' from the exclusion list?\nAutomated replies will resume for this number.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            success = remove_excluded_number(number_id)
            if success:
                self._load_excluded_numbers()
            else:
                QMessageBox.warning(self, "Error", "Could not remove number from database.")

    def _on_ignored_toggle_changed(self, checked: bool):
        set_setting("ignored_numbers_enabled", "1" if checked else "0")

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

        self.tog_ignored_numbers.setChecked(get_setting("ignored_numbers_enabled", "1") == "1")
        self._refresh_account_dropdown()

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
        set_setting("ignored_numbers_enabled", "1" if self.tog_ignored_numbers.isChecked() else "0")
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
