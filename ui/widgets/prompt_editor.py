from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QFrame, QToolButton, QDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor, QTextDocument, QTextCharFormat, QColor, QFont
from database import get_setting, set_setting


class PromptSearchToolbar(QWidget):
    """
    Search toolbar for QTextEdit providing real-time text matching,
    dual-tier visual highlighting (all matches vs active match),
    match counters, next/prev navigation, and case-sensitivity toggle.
    """
    def __init__(self, editor: QTextEdit, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.current_match_index = -1
        self.matches = []
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 4)
        layout.setSpacing(6)

        # Search icon
        lbl_icon = QLabel("🔍")
        lbl_icon.setStyleSheet("font-size: 12px; color: #8B949E;")
        layout.addWidget(lbl_icon)

        # Search Input Field
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search words or characters in prompt... (Enter = Next, Shift+Enter = Prev)")
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 4px 10px;
                color: #C9D1D9;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #58A6FF;
            }
        """)
        self.txt_search.textChanged.connect(self.on_search_text_changed)
        self.txt_search.returnPressed.connect(self.find_next)
        layout.addWidget(self.txt_search, stretch=1)

        # Match Counter Label
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("font-size: 11px; color: #8B949E; min-width: 65px;")
        layout.addWidget(self.lbl_count)

        # Prev Button
        self.btn_prev = QToolButton()
        self.btn_prev.setText("▲ Prev")
        self.btn_prev.setToolTip("Previous match (Shift+Enter)")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setStyleSheet("""
            QToolButton {
                background-color: #21262D;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 4px 8px;
                color: #C9D1D9;
                font-size: 11px;
            }
            QToolButton:hover {
                background-color: #30363D;
                border-color: #58A6FF;
            }
        """)
        self.btn_prev.clicked.connect(self.find_prev)
        layout.addWidget(self.btn_prev)

        # Next Button
        self.btn_next = QToolButton()
        self.btn_next.setText("▼ Next")
        self.btn_next.setToolTip("Next match (Enter)")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setStyleSheet("""
            QToolButton {
                background-color: #21262D;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 4px 8px;
                color: #C9D1D9;
                font-size: 11px;
            }
            QToolButton:hover {
                background-color: #30363D;
                border-color: #58A6FF;
            }
        """)
        self.btn_next.clicked.connect(self.find_next)
        layout.addWidget(self.btn_next)

        # Case-Sensitive Toggle
        self.btn_case = QToolButton()
        self.btn_case.setText("Aa")
        self.btn_case.setCheckable(True)
        self.btn_case.setToolTip("Match Case (Case Sensitive)")
        self.btn_case.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_case.setStyleSheet("""
            QToolButton {
                background-color: #21262D;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 4px 8px;
                color: #8B949E;
                font-weight: 700;
                font-size: 11px;
            }
            QToolButton:checked {
                background-color: #1F6FEB;
                border-color: #58A6FF;
                color: #FFFFFF;
            }
            QToolButton:hover {
                border-color: #58A6FF;
            }
        """)
        self.btn_case.toggled.connect(self.on_search_text_changed)
        layout.addWidget(self.btn_case)

        # Clear Button
        self.btn_clear = QToolButton()
        self.btn_clear.setText("✕")
        self.btn_clear.setToolTip("Clear search")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                padding: 4px 6px;
                color: #8B949E;
                font-size: 12px;
            }
            QToolButton:hover {
                color: #F85149;
            }
        """)
        self.btn_clear.clicked.connect(self.clear_search)
        layout.addWidget(self.btn_clear)

    def on_search_text_changed(self):
        query = self.txt_search.text()
        if not query:
            self.clear_highlights()
            self.lbl_count.setText("")
            return

        doc = self.editor.document()
        flags = QTextDocument.FindFlag(0)
        if self.btn_case.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        self.matches = []
        cursor = QTextCursor(doc)
        while True:
            cursor = doc.find(query, cursor, flags)
            if cursor.isNull():
                break
            self.matches.append((cursor.selectionStart(), cursor.selectionEnd()))

        if self.matches:
            self.current_match_index = 0
            self.lbl_count.setText(f"1 of {len(self.matches)}")
            self.lbl_count.setStyleSheet("font-size: 11px; color: #58A6FF; min-width: 65px;")
            self._apply_highlights()
            self._scroll_to_current()
        else:
            self.current_match_index = -1
            self.lbl_count.setText("0 matches")
            self.lbl_count.setStyleSheet("font-size: 11px; color: #F85149; min-width: 65px;")
            self.clear_highlights()

    def find_next(self):
        if not self.matches:
            return
        self.current_match_index = (self.current_match_index + 1) % len(self.matches)
        self.lbl_count.setText(f"{self.current_match_index + 1} of {len(self.matches)}")
        self._apply_highlights()
        self._scroll_to_current()

    def find_prev(self):
        if not self.matches:
            return
        self.current_match_index = (self.current_match_index - 1) % len(self.matches)
        self.lbl_count.setText(f"{self.current_match_index + 1} of {len(self.matches)}")
        self._apply_highlights()
        self._scroll_to_current()

    def _scroll_to_current(self):
        if 0 <= self.current_match_index < len(self.matches):
            start, end = self.matches[self.current_match_index]
            cursor = self.editor.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()

    def _apply_highlights(self):
        selections = []
        doc = self.editor.document()

        # Amber highlight for all matches
        fmt_all = QTextCharFormat()
        fmt_all.setBackground(QColor("#725300"))
        fmt_all.setForeground(QColor("#FFFFFF"))

        # Bright gold highlight for current active match
        fmt_current = QTextCharFormat()
        fmt_current.setBackground(QColor("#F59E0B"))
        fmt_current.setForeground(QColor("#000000"))
        fmt_current.setFontWeight(QFont.Weight.Bold)

        for idx, (start, end) in enumerate(self.matches):
            sel = QTextEdit.ExtraSelection()
            c = QTextCursor(doc)
            c.setPosition(start)
            c.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = c
            sel.format = fmt_current if idx == self.current_match_index else fmt_all
            selections.append(sel)

        self.editor.setExtraSelections(selections)

    def clear_highlights(self):
        self.editor.setExtraSelections([])
        self.matches = []
        self.current_match_index = -1

    def clear_search(self):
        self.txt_search.clear()
        self.clear_highlights()
        self.lbl_count.setText("")


class ResizeHandleBar(QFrame):
    """
    Sleek drag-to-resize handle bar at the bottom of the editor,
    similar to web textarea resize handles, plus quick preset buttons.
    """
    def __init__(self, target_widget: QWidget, min_h: int = 150, max_h: int = 1200, on_popout=None, parent=None):
        super().__init__(parent)
        self.target_widget = target_widget
        self.min_h = min_h
        self.max_h = max_h
        self.on_popout = on_popout
        self._dragging = False
        self._start_y = 0
        self._start_h = 0

        self.setFixedHeight(26)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setStyleSheet("""
            ResizeHandleBar {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            ResizeHandleBar:hover {
                background-color: #1C2128;
                border-color: #58A6FF;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)

        # Drag hint with grip dots
        lbl_hint = QLabel("⠇⠇ Drag to resize height")
        lbl_hint.setStyleSheet("color: #6E7681; font-size: 10px; font-weight: 600;")
        layout.addWidget(lbl_hint)

        layout.addStretch()

        # Preset Height Pills
        presets = [("Compact", 180), ("Medium", 360), ("Tall", 550)]
        for label, h in presets:
            btn = QPushButton(label)
            btn.setFixedSize(56, 18)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #21262D;
                    color: #8B949E;
                    border: 1px solid #30363D;
                    border-radius: 3px;
                    font-size: 9px;
                    font-weight: 600;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #30363D;
                    color: #58A6FF;
                    border-color: #58A6FF;
                }
            """)
            btn.clicked.connect(lambda _, target_h=h: self.set_target_height(target_h))
            layout.addWidget(btn)

        # Fullscreen / Pop-out button
        if self.on_popout:
            btn_expand = QPushButton("⛶ Pop-out Editor")
            btn_expand.setFixedHeight(18)
            btn_expand.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_expand.setStyleSheet("""
                QPushButton {
                    background-color: #1F6FEB;
                    color: #FFFFFF;
                    border: 1px solid #388BFD;
                    border-radius: 3px;
                    font-size: 9px;
                    font-weight: 600;
                    padding: 0 6px;
                }
                QPushButton:hover {
                    background-color: #388BFD;
                }
            """)
            btn_expand.clicked.connect(self.on_popout)
            layout.addWidget(btn_expand)

    def set_target_height(self, h: int):
        clamped = max(self.min_h, min(self.max_h, h))
        self.target_widget.setFixedHeight(clamped)
        set_setting("ai_prompt_editor_height", str(clamped))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_y = event.globalPosition().y()
            self._start_h = self.target_widget.height()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.globalPosition().y() - self._start_y
            new_h = int(max(self.min_h, min(self.max_h, self._start_h + delta)))
            self.target_widget.setFixedHeight(new_h)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            set_setting("ai_prompt_editor_height", str(self.target_widget.height()))
            event.accept()


class FullscreenPromptDialog(QDialog):
    """
    Dedicated large modal dialog allowing expansive prompt viewing and editing
    with full search capabilities and word counter.
    """
    def __init__(self, initial_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Knowledge Base & Prompt Editor — Full View")
        self.resize(950, 720)
        self.setStyleSheet("background-color: #0D1117; color: #C9D1D9;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        lbl_title = QLabel("SYSTEM KNOWLEDGE BASE PROMPT (Full Editor)")
        lbl_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #58A6FF;")
        header.addWidget(lbl_title)
        header.addStretch()

        self.lbl_stats = QLabel("")
        self.lbl_stats.setStyleSheet("font-size: 11px; color: #8B949E;")
        header.addWidget(self.lbl_stats)
        layout.addLayout(header)

        # Editor
        self.editor = QTextEdit()
        self.editor.setPlainText(initial_text)
        self.editor.setStyleSheet("""
            QTextEdit {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 6px;
                color: #C9D1D9;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.4;
                padding: 10px;
            }
            QTextEdit:focus {
                border-color: #58A6FF;
            }
        """)
        self.editor.textChanged.connect(self._update_stats)

        # Search Bar
        self.search_toolbar = PromptSearchToolbar(self.editor)
        layout.addWidget(self.search_toolbar)
        layout.addWidget(self.editor, stretch=1)

        # Footer Actions
        footer = QHBoxLayout()
        footer.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedSize(90, 34)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #21262D;
                border: 1px solid #30363D;
                border-radius: 6px;
                color: #C9D1D9;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #30363D;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)

        btn_apply = QPushButton("Apply Changes")
        btn_apply.setFixedSize(130, 34)
        btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                border: 1px solid #2EA043;
                border-radius: 6px;
                color: #FFFFFF;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2EA043;
            }
        """)
        btn_apply.clicked.connect(self.accept)
        footer.addWidget(btn_apply)

        layout.addLayout(footer)
        self._update_stats()

    def _update_stats(self):
        text = self.editor.toPlainText()
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        lines = len(text.splitlines()) if text else 0
        self.lbl_stats.setText(f"Lines: {lines} | Words: {words} | Characters: {chars}")

    def get_text(self) -> str:
        return self.editor.toPlainText()
