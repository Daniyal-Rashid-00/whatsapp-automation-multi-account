import os
import mimetypes
from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QComboBox, QTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal

class RuleEditorWidget(QGroupBox):
    rule_added = pyqtSignal(dict)
    rule_modified = pyqtSignal(int, dict)
    rule_deleted = pyqtSignal(int)
    form_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("⚡ RULE CREATOR & ENGINE CONSOLE", parent)
        self.editing_rule_id: Optional[int] = None
        self.attachments: List[Dict[str, str]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(14)

        # Rule Name & Operator / Keyword Row
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        v1 = QVBoxLayout()
        v1.setSpacing(4)
        lbl_name = QLabel("RULE NAME:")
        lbl_name.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        v1.addWidget(lbl_name)
        self.txt_rule_name = QLineEdit()
        self.txt_rule_name.setPlaceholderText("e.g. Product Pricing Inquiry")
        v1.addWidget(self.txt_rule_name)
        row1.addLayout(v1, stretch=2)

        v2 = QVBoxLayout()
        v2.setSpacing(4)
        lbl_op = QLabel("OPERATOR:")
        lbl_op.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        v2.addWidget(lbl_op)
        self.cmb_operator = QComboBox()
        self.cmb_operator.addItems(["Contains", "=", "Like", "Start with", "End with"])
        v2.addWidget(self.cmb_operator)
        row1.addLayout(v2, stretch=1)

        v3 = QVBoxLayout()
        v3.setSpacing(4)
        lbl_kw = QLabel("KEYWORD(S):")
        lbl_kw.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        v3.addWidget(lbl_kw)
        self.txt_keyword = QLineEdit()
        self.txt_keyword.setPlaceholderText("price, cost, catalog")
        v3.addWidget(self.txt_keyword)
        row1.addLayout(v3, stretch=2)

        layout.addLayout(row1)

        # Response Message Editor & Toolbar
        lbl_resp = QLabel("RESPONSE MESSAGE TEMPLATE (Supports Emojis & Bold Format):")
        lbl_resp.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        layout.addWidget(lbl_resp)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        btn_bold = QPushButton("Bold")
        btn_bold.setObjectName("btnSecondary")
        btn_bold.setToolTip("Wrap selection in *Bold*")
        btn_bold.clicked.connect(lambda: self._insert_format("*", "*"))
        toolbar.addWidget(btn_bold)

        btn_italic = QPushButton("Italic")
        btn_italic.setObjectName("btnSecondary")
        btn_italic.setToolTip("Wrap selection in _Italic_")
        btn_italic.clicked.connect(lambda: self._insert_format("_", "_"))
        toolbar.addWidget(btn_italic)

        btn_strike = QPushButton("Strikethrough")
        btn_strike.setObjectName("btnSecondary")
        btn_strike.setToolTip("Wrap selection in ~Strikethrough~")
        btn_strike.clicked.connect(lambda: self._insert_format("~", "~"))
        toolbar.addWidget(btn_strike)

        btn_emoji = QPushButton("🔥 Coupon Emoji")
        btn_emoji.setObjectName("btnSecondary")
        btn_emoji.clicked.connect(lambda: self.txt_response.insertPlainText("🔥 "))
        toolbar.addWidget(btn_emoji)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.txt_response = QTextEdit()
        self.txt_response.setPlaceholderText("Here is our latest product catalog! Let us know if you need assistance. 🔥")
        self.txt_response.setMaximumHeight(90)
        layout.addWidget(self.txt_response)

        # File Attachments Table (Scrollable & Unsquished layout)
        lbl_att = QLabel("FILE ATTACHMENTS (Linked Media):")
        lbl_att.setStyleSheet("font-weight: 700; font-size: 11px; color: #94A3B8;")
        layout.addWidget(lbl_att)

        self.tbl_attachments = QTableWidget(0, 3)
        self.tbl_attachments.setHorizontalHeaderLabels(["FILE NAME", "TYPE", "OPTIONAL CAPTION"])
        self.tbl_attachments.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_attachments.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_attachments.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_attachments.verticalHeader().setDefaultSectionSize(36)
        self.tbl_attachments.setMinimumHeight(130)
        self.tbl_attachments.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.tbl_attachments)

        att_bar = QHBoxLayout()
        btn_add_att = QPushButton("+ Add Attachment")
        btn_add_att.setObjectName("btnSecondary")
        btn_add_att.clicked.connect(self._add_attachment_dialog)
        att_bar.addWidget(btn_add_att)

        btn_clear_att = QPushButton("Clear Attachments")
        btn_clear_att.setObjectName("btnSecondary")
        btn_clear_att.clicked.connect(self._clear_attachments)
        att_bar.addWidget(btn_clear_att)

        att_bar.addStretch()
        layout.addLayout(att_bar)

        layout.addSpacing(6)

        # Bottom Action Bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_save = QPushButton("Add Rule Configuration")
        self.btn_save.setObjectName("btnPrimary")
        self.btn_save.setMinimumHeight(38)
        self.btn_save.clicked.connect(self._save_rule_action)
        btn_bar.addWidget(self.btn_save, stretch=2)

        self.btn_cancel = QPushButton("➕ New Rule Mode")
        self.btn_cancel.setObjectName("btnSecondary")
        self.btn_cancel.setMinimumHeight(38)
        self.btn_cancel.setToolTip("Cancel editing and clear form to create a new rule")
        self.btn_cancel.clicked.connect(self.clear_form)
        btn_bar.addWidget(self.btn_cancel, stretch=1)

        self.btn_delete = QPushButton("Delete Rule")
        self.btn_delete.setObjectName("btnDanger")
        self.btn_delete.setMinimumHeight(38)
        self.btn_delete.clicked.connect(self._delete_rule_action)
        btn_bar.addWidget(self.btn_delete, stretch=1)

        layout.addLayout(btn_bar)

    def _insert_format(self, prefix: str, suffix: str):
        cursor = self.txt_response.textCursor()
        selected = cursor.selectedText()
        if selected:
            cursor.insertText(f"{prefix}{selected}{suffix}")
        else:
            cursor.insertText(f"{prefix}text{suffix}")

    def _add_attachment_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Attachment File", "", "All Files (*.*)")
        if file_path:
            filename = os.path.basename(file_path)
            mime_type, _ = mimetypes.guess_type(file_path)
            mime_type = mime_type or "application/octet-stream"
            # Default media_caption is empty string so media sends cleanly without default text!
            att = {
                "file_name": filename,
                "local_file_path": file_path,
                "mime_type": mime_type,
                "media_caption": ""
            }
            self.attachments.append(att)
            self._refresh_attachments_table()

    def _clear_attachments(self):
        self.attachments.clear()
        self._refresh_attachments_table()

    def _refresh_attachments_table(self):
        self.tbl_attachments.setRowCount(len(self.attachments))
        for row, att in enumerate(self.attachments):
            self.tbl_attachments.setItem(row, 0, QTableWidgetItem(att["file_name"]))
            self.tbl_attachments.setItem(row, 1, QTableWidgetItem(att["mime_type"]))
            self.tbl_attachments.setItem(row, 2, QTableWidgetItem(att.get("media_caption", "")))

    def load_rule_for_edit(self, rule: dict):
        self.editing_rule_id = rule["id"]
        self.txt_rule_name.setText(rule["rule_name"])
        self.cmb_operator.setCurrentText(rule["matching_operator"])
        self.txt_keyword.setText(rule["keyword_payload"])
        self.txt_response.setText(rule["response_message"])
        self.attachments = list(rule.get("attachments", []))
        self._refresh_attachments_table()

        self.setTitle(f"⚡ EDITING RULE #{rule['id']} — {rule['rule_name']}")
        self.btn_save.setText(f"💾 Save Modifications (Rule #{rule['id']})")
        self.btn_save.setStyleSheet("border: 2px solid #2563EB; background-color: #1E293B; color: #60A5FA; font-weight: 700;")
        self.btn_cancel.setText("❌ Cancel Edit (New Rule)")
        self.btn_cancel.setStyleSheet("border: 1px solid #E11D48; color: #FDA4AF; font-weight: 600;")

    def clear_form(self):
        self.editing_rule_id = None
        self.setTitle("⚡ RULE CREATOR & ENGINE CONSOLE")
        self.txt_rule_name.clear()
        self.txt_keyword.clear()
        self.txt_response.clear()
        self.attachments.clear()
        self._refresh_attachments_table()
        self.btn_save.setText("Add Rule Configuration")
        self.btn_save.setObjectName("btnPrimary")
        self.btn_save.setStyleSheet("")
        self.btn_cancel.setText("➕ New Rule Mode")
        self.btn_cancel.setStyleSheet("")
        self.form_cleared.emit()

    def _save_rule_action(self):
        name = self.txt_rule_name.text().strip()
        operator = self.cmb_operator.currentText()
        keyword = self.txt_keyword.text().strip()
        response = self.txt_response.toPlainText().strip()

        if not name or not keyword or not response:
            QMessageBox.warning(self, "Validation Error", "Rule Name, Keyword, and Response Message are required!")
            return

        rule_data = {
            "rule_name": name,
            "matching_operator": operator,
            "keyword_payload": keyword,
            "response_message": response,
            "is_enabled": 1,
            "attachments": self.attachments
        }

        if self.editing_rule_id is not None:
            self.rule_modified.emit(self.editing_rule_id, rule_data)
        else:
            self.rule_added.emit(rule_data)

        self.clear_form()

    def _delete_rule_action(self):
        if self.editing_rule_id is None:
            QMessageBox.warning(self, "Delete Error", "Please select a rule from the matrix to delete.")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete rule #{self.editing_rule_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.rule_deleted.emit(self.editing_rule_id)
            self.clear_form()
