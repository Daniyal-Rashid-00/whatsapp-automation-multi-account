import json
from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QFileDialog, QMessageBox, QHeaderView, QWidget, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.widgets.toggle_switch import ToggleSwitch

class RuleRegistryWidget(QGroupBox):
    rule_selected = pyqtSignal(dict)
    rule_toggled = pyqtSignal(int, int) # (rule_id, is_enabled)
    rules_imported = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__("Rule Book", parent)
        self.rules: List[Dict[str, Any]] = []
        self.filtered_rules: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(10)

        # Top Bar: Search Bar & Import/Export Buttons
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search rules by name or keyword...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self._filter_table)
        top_bar.addWidget(self.txt_search, stretch=2)

        btn_import = QPushButton("📂 Import Rules (JSON)")
        btn_import.setObjectName("btnSecondary")
        btn_import.clicked.connect(self._import_rules_action)
        top_bar.addWidget(btn_import)

        btn_export = QPushButton("💾 Export Rules Backup")
        btn_export.setObjectName("btnSecondary")
        btn_export.clicked.connect(self._export_rules_action)
        top_bar.addWidget(btn_export)

        layout.addLayout(top_bar)

        # Table Grid
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["STATUS", "ID", "RULE NAME", "OPERATOR", "KEYWORD MATCH", "ATTACHMENTS", "ACTIONS"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 76)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 56)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 105)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 110)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 88)
        
        # Row height generous enough for the edit button without any clipping
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(260)

        layout.addWidget(self.table)

    def display_rules(self, rules: List[Dict[str, Any]]):
        self.rules = rules
        self._filter_table()

    def _filter_table(self):
        search_term = self.txt_search.text().strip().lower()
        if not search_term:
            self.filtered_rules = list(self.rules)
        else:
            self.filtered_rules = [
                r for r in self.rules
                if search_term in r.get("rule_name", "").lower() or search_term in r.get("keyword_payload", "").lower()
            ]

        self.table.blockSignals(True)
        self.table.setRowCount(len(self.filtered_rules))

        for row, r in enumerate(self.filtered_rules):
            is_enabled = r.get("is_enabled", 1) == 1
            rule_id = r["id"]

            # Real Sliding Knob Toggle Switch Widget
            toggle = ToggleSwitch(checked=is_enabled)

            def make_toggle_handler(rid, t_widget):
                def handler(checked: bool):
                    new_state = 1 if checked else 0
                    for rule in self.rules:
                        if rule["id"] == rid:
                            rule["is_enabled"] = new_state
                    self.rule_toggled.emit(rid, new_state)
                return handler

            toggle.stateChanged.connect(make_toggle_handler(rule_id, toggle))

            toggle_container = QWidget()
            toggle_container.setStyleSheet("background: transparent;")
            l = QHBoxLayout(toggle_container)
            l.addWidget(toggle)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, toggle_container)

            item_id = QTableWidgetItem(str(r["id"]))
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, item_id)

            item_name = QTableWidgetItem(r["rule_name"])
            self.table.setItem(row, 2, item_name)

            item_op = QTableWidgetItem(r["matching_operator"])
            item_op.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, item_op)

            item_kw = QTableWidgetItem(r["keyword_payload"])
            self.table.setItem(row, 4, item_kw)
            
            att_count = len(r.get("attachments", []))
            att_str = f"📎 {att_count} Bound" if att_count > 0 else "0 Files"
            item_att = QTableWidgetItem(att_str)
            item_att.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if att_count > 0:
                item_att.setForeground(Qt.GlobalColor.cyan)
            self.table.setItem(row, 5, item_att)

            # Explicit Edit Button — centered inside container with fixed height
            btn_edit = QPushButton("✏️ Edit")
            btn_edit.setFixedSize(76, 26)
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.setStyleSheet("""
                QPushButton {
                    background: #1E3A5F;
                    color: #7DD3FC;
                    border: 1px solid #38BDF8;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: #0369A1;
                    color: #FFFFFF;
                }
                QPushButton:pressed {
                    background: #075985;
                }
            """)
            
            def make_edit_handler(rule_obj):
                return lambda: self.rule_selected.emit(rule_obj)

            btn_edit.clicked.connect(make_edit_handler(r))

            btn_container = QWidget()
            btn_container.setStyleSheet("background: transparent;")
            bl = QHBoxLayout(btn_container)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(0)
            bl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bl.addWidget(btn_edit)
            self.table.setCellWidget(row, 6, btn_container)

        self.table.blockSignals(False)

    def _on_selection_changed(self):
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if 0 <= row < len(self.filtered_rules):
            self.rule_selected.emit(self.filtered_rules[row])

    def _import_rules_action(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Rules JSON", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    imported_data = json.load(f)
                    if isinstance(imported_data, list):
                        self.rules_imported.emit(imported_data)
                        QMessageBox.information(self, "Import Success", f"Successfully imported {len(imported_data)} rules!")
                    else:
                        QMessageBox.warning(self, "Import Error", "JSON root must be a list of rule objects.")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to read JSON file: {e}")

    def _export_rules_action(self):
        if not self.rules:
            QMessageBox.warning(self, "Export Warning", "No rules available to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Rules Backup", "nexus_rules_backup.json", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.rules, f, indent=2)
                QMessageBox.information(self, "Export Success", f"Rules configuration backup exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to write backup file: {e}")
