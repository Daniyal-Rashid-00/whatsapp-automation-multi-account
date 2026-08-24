from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt
from ui.rule_editor import RuleEditorWidget
from ui.rule_table import RuleRegistryWidget
from ui.widgets.toggle_switch import ToggleSwitch
from ui.theme import COLOR_DARK_BG
import database as db

class RuleStudioPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # QScrollArea to prevent squishing any UI elements
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {COLOR_DARK_BG}; border: none; }}")

        content_widget = QWidget()
        content_widget.setStyleSheet(f"background-color: {COLOR_DARK_BG};")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(16)

        # Page Header
        hdr_layout = QHBoxLayout()
        title = QLabel("Rule Studio")
        title.setObjectName("pageTitle")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        content_layout.addLayout(hdr_layout)

        # Master Auto Rule System Toggle Card
        master_card = QFrame()
        master_card.setObjectName("cardFrame")
        master_card_layout = QHBoxLayout(master_card)
        master_card_layout.setContentsMargins(18, 14, 18, 14)
        master_card_layout.setSpacing(14)

        is_rules_enabled = db.get_setting("rules_master_enabled", "1") == "1"
        self.tog_rules_master = ToggleSwitch(checked=is_rules_enabled)
        self.tog_rules_master.stateChanged.connect(self._on_master_toggle_changed)
        master_card_layout.addWidget(self.tog_rules_master)

        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        status_text = "ACTIVE (ON)" if is_rules_enabled else "PAUSED (OFF)"
        status_color = "#22C55E" if is_rules_enabled else "#EF4444"
        self.lbl_master_title = QLabel(f"Auto Rule Reply System: {status_text}")
        self.lbl_master_title.setStyleSheet(f"font-weight: 700; font-size: 14px; color: {status_color};")
        v_title.addWidget(self.lbl_master_title)

        lbl_sub = QLabel("Master switch to globally enable or pause all keyword-based automated rule replies across your WhatsApp accounts.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #8B949E;")
        v_title.addWidget(lbl_sub)
        master_card_layout.addLayout(v_title)
        master_card_layout.addStretch()

        content_layout.addWidget(master_card)

        # 1. Rule Book (Table & Search)
        self.rule_registry = RuleRegistryWidget()
        content_layout.addWidget(self.rule_registry)

        # 2. Rule Creator & Editor Console Form
        self.rule_editor = RuleEditorWidget()
        content_layout.addWidget(self.rule_editor)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # Connect selection signal
        self.rule_registry.rule_selected.connect(self.rule_editor.load_rule_for_edit)

    def _on_master_toggle_changed(self, checked: bool):
        db.set_setting("rules_master_enabled", "1" if checked else "0")
        if checked:
            self.lbl_master_title.setText("Auto Rule Reply System: ACTIVE (ON)")
            self.lbl_master_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #22C55E;")
        else:
            self.lbl_master_title.setText("Auto Rule Reply System: PAUSED (OFF)")
            self.lbl_master_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #EF4444;")
