# Refined Corporate Dark Theme Palette (Unified Dark Aesthetic)

COLOR_DARK_BG = "#0D1117"           # Unified main dark background
COLOR_SLATE_CARD = "#161B22"        # Card & container background
COLOR_SURFACE_HOVER = "#21262D"     # Hover surface
COLOR_ACCENT_BLUE = "#2563EB"       # Corporate primary accent blue
COLOR_ACCENT_HOVER = "#3B82F6"      # Hover blue
COLOR_CYBER_GREEN = "#10B981"       # Success green
COLOR_NEON_CRIMSON = "#EF4444"      # Danger red
COLOR_AMBER_ALERT = "#F59E0B"       # Warning amber
COLOR_TEXT_PRIMARY = "#F0F6FC"      # Clean off-white text
COLOR_TEXT_MUTED = "#8B949E"        # Muted text
COLOR_BORDER_SUBDUED = "#30363D"    # Subtle border color

CYBER_CORPORATE_QSS = f"""
QMainWindow, QDialog, QMessageBox {{
    background-color: {COLOR_DARK_BG};
    color: {COLOR_TEXT_PRIMARY};
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
}}

QWidget {{
    background-color: {COLOR_DARK_BG};
    color: {COLOR_TEXT_PRIMARY};
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
    font-size: 13px;
}}

/* Scroll Area Background Fix */
QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: {COLOR_DARK_BG};
    border: none;
}}

/* Card Frame containers */
QFrame#cardFrame, QGroupBox {{
    background-color: {COLOR_SLATE_CARD};
    border: 1px solid {COLOR_BORDER_SUBDUED};
    border-radius: 8px;
    margin-top: 6px;
    padding: 14px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {COLOR_TEXT_PRIMARY};
    font-weight: 600;
    font-size: 13px;
}}

QLabel {{
    background: transparent;
    color: {COLOR_TEXT_PRIMARY};
}}

QLabel#subduedLabel {{
    color: {COLOR_TEXT_MUTED};
    font-size: 12px;
}}

QLabel#pageTitle {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.5px;
}}

/* Input Fields */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLOR_DARK_BG};
    border: 1px solid {COLOR_BORDER_SUBDUED};
    border-radius: 6px;
    color: {COLOR_TEXT_PRIMARY};
    padding: 8px 12px;
    font-size: 13px;
}}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLOR_ACCENT_HOVER};
    background-color: #121824;
}}

/* QComboBox & Dropdown Popup Styling Fix */
QComboBox {{
    combobox-popup: 0;
    background-color: {COLOR_DARK_BG};
    border: 1px solid {COLOR_BORDER_SUBDUED};
    border-radius: 6px;
    color: {COLOR_TEXT_PRIMARY};
    padding: 8px 12px;
    font-size: 13px;
}}

QComboBox:focus, QComboBox:on {{
    border: 1px solid {COLOR_ACCENT_HOVER};
    background-color: #121824;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_SLATE_CARD};
    color: {COLOR_TEXT_PRIMARY};
    selection-background-color: {COLOR_ACCENT_BLUE};
    selection-color: white;
    border: 1px solid {COLOR_BORDER_SUBDUED};
    outline: 0px;
    padding: 0px;
    margin: 0px;
}}

QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 6px 10px;
    background-color: {COLOR_SLATE_CARD};
    color: {COLOR_TEXT_PRIMARY};
    border: none;
}}

QComboBox QAbstractItemView::item:hover, QComboBox QAbstractItemView::item:selected {{
    background-color: {COLOR_ACCENT_BLUE};
    color: white;
}}

/* Buttons */
QPushButton {{
    background-color: {COLOR_SLATE_CARD};
    border: 1px solid {COLOR_BORDER_SUBDUED};
    border-radius: 6px;
    color: {COLOR_TEXT_PRIMARY};
    font-weight: 600;
    padding: 8px 16px;
    font-size: 13px;
}}

QPushButton:hover {{
    background-color: {COLOR_SURFACE_HOVER};
    border-color: {COLOR_TEXT_MUTED};
}}

QPushButton:pressed {{
    background-color: {COLOR_BORDER_SUBDUED};
}}

QPushButton#btnPrimary {{
    background-color: {COLOR_ACCENT_BLUE};
    color: white;
    border: 1px solid {COLOR_ACCENT_BLUE};
    font-weight: 600;
}}

QPushButton#btnPrimary:hover {{
    background-color: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}

QPushButton#btnDanger {{
    background-color: rgba(239, 68, 68, 0.1);
    border: 1px solid {COLOR_NEON_CRIMSON};
    color: {COLOR_NEON_CRIMSON};
    font-weight: 600;
}}

QPushButton#btnDanger:hover {{
    background-color: {COLOR_NEON_CRIMSON};
    color: white;
}}

QPushButton#btnSecondary {{
    background-color: transparent;
    border: 1px solid {COLOR_BORDER_SUBDUED};
    color: {COLOR_TEXT_PRIMARY};
}}

QPushButton#btnSecondary:hover {{
    border-color: {COLOR_TEXT_MUTED};
    background-color: {COLOR_SLATE_CARD};
}}

/* Sidebar Navigation Items */
QPushButton#navItem {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: {COLOR_TEXT_MUTED};
    font-weight: 600;
    font-size: 13px;
    padding: 10px 14px;
    text-align: left;
}}

QPushButton#navItem:hover {{
    background-color: {COLOR_SURFACE_HOVER};
    color: {COLOR_TEXT_PRIMARY};
}}

QPushButton#navItem[active="true"] {{
    background-color: {COLOR_SURFACE_HOVER};
    color: {COLOR_TEXT_PRIMARY};
    border-left: 3px solid {COLOR_ACCENT_HOVER};
    font-weight: 700;
}}

/* Table Styling */
QTableWidget {{
    background-color: {COLOR_DARK_BG};
    border: 1px solid {COLOR_BORDER_SUBDUED};
    gridline-color: {COLOR_BORDER_SUBDUED};
    border-radius: 6px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
}}

QTableWidget::item {{
    padding: 8px 10px;
    border-bottom: 1px solid {COLOR_BORDER_SUBDUED};
}}

QTableWidget::item:selected {{
    background-color: rgba(37, 99, 235, 0.15);
    color: {COLOR_TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {COLOR_SLATE_CARD};
    color: {COLOR_TEXT_MUTED};
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {COLOR_BORDER_SUBDUED};
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* Dialog & QMessageBox Styling */
QMessageBox {{
    background-color: {COLOR_DARK_BG};
    color: {COLOR_TEXT_PRIMARY};
}}

QMessageBox QLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
}}

QMessageBox QPushButton {{
    min-width: 80px;
    padding: 6px 14px;
}}

QCheckBox {{
    color: {COLOR_TEXT_PRIMARY};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {COLOR_TEXT_MUTED};
    background-color: {COLOR_DARK_BG};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR_ACCENT_BLUE};
    border: 1px solid {COLOR_ACCENT_BLUE};
}}

QScrollBar:vertical {{
    background: {COLOR_DARK_BG};
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {COLOR_BORDER_SUBDUED};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_TEXT_MUTED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
