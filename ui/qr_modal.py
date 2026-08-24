import base64
import threading
import httpx
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea
)
from PyQt6.QtGui import QFont, QColor, QPixmap, QPainter, QPen, QBrush
from PyQt6.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt6.QtSvg import QSvgRenderer
from database import get_setting, delete_account, get_all_accounts, update_account_status
from waha_launcher import WAHALauncher

# ── WhatsApp Exact Brand Palette ──────────────────────────────────────────────
_BG        = "#FCF5EB"   # Clean warm ivory/cream background
_WHITE     = "#FFFFFF"
_BORDER    = "#202C33"   # Thin dark border matching original WhatsApp Web card
_GREEN_BTN = "#00D757"   # WhatsApp bright green (Download button)
_GREEN_LNK = "#00A884"   # WhatsApp teal-green for links
_DARK      = "#111B21"   # Deep charcoal primary text
_SUBTEXT   = "#54656F"   # Secondary subtitle text
_MUTED     = "#667781"   # Footer text
_LINE      = "#8696A0"   # Stepper connecting vertical line

# ── SVG Vector Assets ────────────────────────────────────────────────────────
LAPTOP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 68 56" width="68" height="56">
  <!-- Laptop Screen -->
  <rect x="6" y="10" width="38" height="26" rx="4" fill="#E8F9EB" stroke="#111B21" stroke-width="2"/>
  <!-- Laptop Base -->
  <path d="M2 38 L48 38 C50 38 51 39 49.5 41 L46 44 C44.5 45 43 45.5 40 45.5 L10 45.5 C7 45.5 5.5 45 4 44 L0.5 41 C-1 39 0 38 2 38 Z" fill="#E8F9EB" stroke="#111B21" stroke-width="2"/>
  <line x1="20" y1="38" x2="30" y2="38" stroke="#111B21" stroke-width="2" stroke-linecap="round"/>
  <!-- Phone Badge Overlay -->
  <rect x="24" y="4" width="34" height="28" rx="6" fill="#FFFFFF" stroke="#111B21" stroke-width="2"/>
  <!-- Green Phone Receiver inside badge -->
  <path d="M34 11 C34.8 9.5 36.2 9.8 37.2 10.6 L39 12 C39.8 12.7 39.8 13.5 39 14.3 L38 15.3 C38.5 16.5 39.5 17.5 40.7 18 L41.7 17 C42.5 16.2 43.3 16.2 44 17 L45.4 18.8 C46.2 19.8 46.5 21 44.8 22 C43.5 22.8 42 23 40.5 22.2 C36.8 20.5 33.5 17.2 31.8 13.5 C31 12 31.2 10.5 32 9.5 C32.8 8.5 33.5 9.5 34 11 Z" fill="#25D366"/>
</svg>"""

WA_APP_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20">
  <rect width="24" height="24" rx="6" fill="#25D366"/>
  <path fill="#FFFFFF" d="M12 3.5C7.3 3.5 3.5 7.3 3.5 12c0 1.6.4 3.1 1.2 4.4L3.5 20.5l4.2-1.1c1.3.7 2.7 1.1 4.3 1.1 4.7 0 8.5-3.8 8.5-8.5S16.7 3.5 12 3.5zm4.9 11.2c-.2.6-1.2 1.1-1.7 1.2-.5.1-1.1.1-3.2-.8-2.6-1.1-4.2-3.7-4.4-3.9-.1-.2-1-1.4-1-2.6s.6-1.8.9-2.1c.2-.2.5-.3.8-.3.1 0 .2 0 .3.0.2 0 .4 0 .6.4.2.5.7 1.7.8 1.8.1.2.1.3 0 .5s-.2.3-.3.5c-.1.1-.3.3-.4.4-.1.1-.3.3-.1.6.2.3.8 1.4 1.8 2.2 1.2 1.1 2.2 1.4 2.5 1.6.3.1.5.1.7-.1.2-.2.8-.9 1-1.2.2-.3.4-.3.7-.2.3.1 1.8.8 2.1 1 .3.1.5.2.6.4.1.2.1.8-.1 1.4z"/>
</svg>"""

WA_OFFICIAL_QR_EMBLEM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <!-- Solid White Circular Buffer -->
  <circle cx="50" cy="50" r="49" fill="#FFFFFF"/>
  <!-- Speech Bubble with Dark Border -->
  <path d="M50 10 C27.9 10 10 27.9 10 50 C10 57.3 12 64.1 15.4 70 L11 87 L28.8 82.8 C35.1 87.3 42.3 90 50 90 C72.1 90 90 72.1 90 50 C90 27.9 72.1 10 50 10 Z" 
        fill="#FFFFFF" stroke="#111B21" stroke-width="5.5" stroke-linejoin="round" stroke-linecap="round"/>
  <!-- Classic Phone Handset Receiver -->
  <path d="M66.5 60.5 C65.5 60.0 59.8 57.2 58.8 56.8 C57.8 56.4 57.1 56.2 56.4 57.3 C55.7 58.3 53.6 60.9 53.0 61.6 C52.3 62.3 51.7 62.4 50.7 61.9 C49.7 61.4 46.5 60.3 42.7 56.9 C39.8 54.3 37.8 51.0 37.2 50.0 C36.7 49.0 37.1 48.4 37.6 47.9 C38.1 47.4 38.6 46.8 39.1 46.2 C39.6 45.6 39.8 45.1 40.2 44.5 C40.5 43.8 40.4 43.2 40.1 42.7 C39.9 42.2 37.7 36.8 36.8 34.6 C35.9 32.4 35.0 32.7 34.4 32.7 C33.8 32.7 33.1 32.7 32.4 32.7 C31.7 32.7 30.7 32.9 29.8 33.9 C28.9 34.9 26.3 37.4 26.3 42.4 C26.3 47.4 29.9 52.2 30.5 52.9 C31.0 53.6 37.7 63.9 47.9 68.3 C50.3 69.4 52.2 70.0 53.7 70.5 C56.1 71.3 58.4 71.2 60.1 70.9 C62.0 70.6 65.9 68.5 66.8 66.0 C67.6 63.5 67.6 61.3 67.4 60.9 C67.2 60.5 66.5 60.5 66.5 60.5 Z" 
        fill="#111B21"/>
</svg>"""

LOCK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="14" height="14">
  <rect x="2.5" y="6.5" width="11" height="8.5" rx="2" fill="none" stroke="#667781" stroke-width="1.3"/>
  <path d="M5 6.5 V4.5 C5 2.8 6.3 1.5 8 1.5 C9.7 1.5 11 2.8 11 4.5 V6.5" fill="none" stroke="#667781" stroke-width="1.3"/>
  <circle cx="8" cy="10.5" r="1" fill="#667781"/>
</svg>"""

CHECK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width="20" height="20">
  <rect width="20" height="20" rx="4" fill="#00A884"/>
  <path d="M5.5 10.5 L8.5 13.5 L14.5 6.5" fill="none" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def add_whatsapp_center_logo(pixmap: QPixmap) -> QPixmap:
    """Overlays the official WhatsApp emblem (white bubble + dark border + phone) on QR center."""
    if pixmap.isNull():
        return pixmap
    result = QPixmap(pixmap)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    size = result.width()
    logo_size = int(size * 0.22)
    center_pos = (size - logo_size) // 2

    # Solid white circular quiet zone buffer
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor("white")))
    painter.drawEllipse(QRectF(center_pos - 3, center_pos - 3, logo_size + 6, logo_size + 6))

    # Render official emblem
    svg_renderer = QSvgRenderer(WA_OFFICIAL_QR_EMBLEM_SVG.encode('utf-8'))
    logo_rect = QRectF(center_pos, center_pos, logo_size, logo_size)
    svg_renderer.render(painter, logo_rect)
    painter.end()
    return result


class UnderlineLinkWidget(QLabel):
    """Renders text with authentic WhatsApp solid green underline and non-underlined arrow."""
    def __init__(self, text: str, arrow: str = ">", parent=None):
        super().__init__(parent)
        self.link_text = text
        self.arrow = arrow
        font = QFont("Segoe UI", 10, QFont.Weight.Medium)
        self.setFont(font)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(24)

        fm = self.fontMetrics()
        w = fm.horizontalAdvance(self.link_text) + (fm.horizontalAdvance(self.arrow) + 8 if self.arrow else 0)
        self.setFixedWidth(w + 6)
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self.font())
        fm = p.fontMetrics()
        txt_w = fm.horizontalAdvance(self.link_text)

        # Draw dark text
        p.setPen(QColor(_DARK))
        p.drawText(0, fm.ascent(), self.link_text)

        # Draw green underline under text only
        p.setPen(QPen(QColor(_GREEN_LNK), 1.8))
        line_y = fm.ascent() + 3
        p.drawLine(0, line_y, txt_w, line_y)

        # Draw arrow without underline
        if self.arrow:
            p.setPen(QColor(_DARK))
            p.drawText(txt_w + 4, fm.ascent(), self.arrow)
        p.end()


class StepperWidget(QWidget):
    """Numbered 1-2-3 stepper widget with connecting vertical line and WhatsApp badge."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(130)
        self.setMinimumWidth(480)
        self.setStyleSheet("background: transparent;")

        wa_b64 = base64.b64encode(WA_APP_ICON_SVG.encode('utf-8')).decode()
        self.steps = [
            "Scan the QR code with your phone's camera",
            f"Tap the link to open <b>WhatsApp</b> <img src='data:image/svg+xml;base64,{wa_b64}' width='18' height='18' style='vertical-align: middle;'>",
            "Scan the QR code again to link to your account"
        ]

        self._CYS = [18, 65, 112]
        for html, cy in zip(self.steps, self._CYS):
            lbl = QLabel(html, self)
            lbl.setFont(QFont("Segoe UI", 10))
            lbl.setStyleSheet(f"color: {_DARK}; background: transparent; border: none;")
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.move(40, cy - 12)
            lbl.resize(440, 24)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = 14
        cr = 11
        # Connecting lines
        p.setPen(QPen(QColor(_LINE), 1.2))
        for i in range(len(self._CYS) - 1):
            p.drawLine(cx, self._CYS[i] + cr + 2, cx, self._CYS[i + 1] - cr - 2)

        # Numbered circles
        for idx, cy in enumerate(self._CYS, start=1):
            rect = QRectF(cx - cr, cy - cr, cr * 2, cr * 2)
            p.setPen(QPen(QColor(_DARK), 1.1))
            p.setBrush(QBrush(QColor(_WHITE)))
            p.drawEllipse(rect)
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(idx))
        p.end()


class TopBannerWidget(QFrame):
    """Top Banner: 'Download WhatsApp for Windows'."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {_WHITE};
                border: 1px solid {_BORDER};
                border-radius: 18px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 12, 22, 12)
        layout.setSpacing(16)

        # Device Icon
        icon_lbl = QLabel()
        icon_pix = QPixmap(52, 42)
        icon_pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(icon_pix)
        QSvgRenderer(LAPTOP_SVG.encode('utf-8')).render(p)
        p.end()
        icon_lbl.setPixmap(icon_pix)
        icon_lbl.setFixedSize(52, 42)

        # Text Layout
        txt = QVBoxLayout()
        txt.setSpacing(2)
        txt.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Download WhatsApp for Windows")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {_DARK};")

        sub = QLabel("Get extra features like voice and video calling, screen sharing and more.")
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet(f"color: {_SUBTEXT};")

        txt.addWidget(title)
        txt.addWidget(sub)

        # Download Button
        btn = QPushButton("Download  ⤓")
        btn.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        btn.setFixedHeight(36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_GREEN_BTN};
                color: #FFFFFF;
                border-radius: 18px;
                padding: 0 22px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #00C24E; }}
        """)

        layout.addWidget(icon_lbl)
        layout.addLayout(txt, stretch=1)
        layout.addWidget(btn)


class QRAuthModal(QDialog):
    """
    WhatsApp Web Official Replica QR Authentication Modal.
    - Pixel-for-pixel match to WhatsApp Web login page
    - Authentic warm cream palette (#FCF5EB), exact typography and stepper
    - Accurate WhatsApp QR center emblem & green-underlined links
    """
    qr_ready = pyqtSignal(str)

    def __init__(self, parent=None, qr_data_url: str = None, session_name: str = "default", is_new_account: bool = False):
        super().__init__(parent)
        self.session_name = session_name
        self.is_new_account = is_new_account
        self._stopped = False

        self.setWindowTitle("WhatsApp Web")
        self.setFixedSize(940, 720)
        self.setModal(True)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {_BG}; }}")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet(f"background-color: {_BG};")

        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(40, 20, 40, 18)
        outer_layout.setSpacing(14)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # 1. Top Banner
        self.banner = TopBannerWidget()
        self.banner.setFixedWidth(860)
        outer_layout.addWidget(self.banner)

        # 2. Main Login Card
        self.card = QFrame()
        self.card.setFixedWidth(860)
        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {_WHITE};
                border: 1px solid {_BORDER};
                border-radius: 20px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)

        card_vlayout = QVBoxLayout(self.card)
        card_vlayout.setContentsMargins(40, 30, 40, 26)
        card_vlayout.setSpacing(0)

        content_hlayout = QHBoxLayout()
        content_hlayout.setContentsMargins(0, 0, 0, 0)
        content_hlayout.setSpacing(20)

        # Left Column (Instructions & Stepper)
        left_col = QVBoxLayout()
        left_col.setSpacing(0)
        left_col.setContentsMargins(0, 0, 0, 0)

        heading = QLabel("Scan to log in")
        heading.setFont(QFont("Segoe UI", 21, QFont.Weight.Medium))
        heading.setStyleSheet(f"color: {_DARK};")

        stepper = StepperWidget()
        help_link = UnderlineLinkWidget("Need help?", "↗")

        left_col.addWidget(heading)
        left_col.addSpacing(18)
        left_col.addWidget(stepper)
        left_col.addSpacing(12)
        left_col.addWidget(help_link)

        # Right Column (Live QR Code Container)
        right_col = QVBoxLayout()
        right_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        self.qr_label = QLabel()
        self.qr_label.setFixedSize(240, 240)
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.qr_label.mousePressEvent = self._on_qr_clicked
        self._apply_loading_state("Starting session...")

        right_col.addWidget(self.qr_label)

        content_hlayout.addLayout(left_col, stretch=1)
        content_hlayout.addLayout(right_col)

        # Bottom Row inside Card (Stay logged in on left, Log in with phone number on right)
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 22, 0, 0)

        check_b64 = base64.b64encode(CHECK_SVG.encode('utf-8')).decode()
        stay_lbl = QLabel(f"<img src='data:image/svg+xml;base64,{check_b64}' width='18' height='18' style='vertical-align: middle;'>&nbsp;&nbsp;<span style='color:{_DARK}; font-size:13px; font-family: Segoe UI;'>Stay logged in on this browser ⓘ</span>")
        stay_lbl.setTextFormat(Qt.TextFormat.RichText)

        phone_link = UnderlineLinkWidget("Log in with phone number", ">")

        bottom_row.addWidget(stay_lbl)
        bottom_row.addStretch()
        bottom_row.addWidget(phone_link)

        card_vlayout.addLayout(content_hlayout)
        card_vlayout.addLayout(bottom_row)

        outer_layout.addWidget(self.card)

        # 3. Authentic Footer
        footer = QVBoxLayout()
        footer.setSpacing(4)
        footer.setContentsMargins(0, 4, 0, 0)
        footer.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        f1_layout = QHBoxLayout()
        f1_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f1_txt = QLabel("Don't have a WhatsApp account? ")
        f1_txt.setFont(QFont("Segoe UI", 10))
        f1_txt.setStyleSheet(f"color: {_DARK};")
        f1_link = UnderlineLinkWidget("Get started", "↗")
        f1_layout.addWidget(f1_txt)
        f1_layout.addWidget(f1_link)

        enc_row = QHBoxLayout()
        enc_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        enc_row.setSpacing(6)

        lock_lbl = QLabel()
        lock_pix = QPixmap(14, 14)
        lock_pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(lock_pix)
        QSvgRenderer(LOCK_SVG.encode('utf-8')).render(p)
        p.end()
        lock_lbl.setPixmap(lock_pix)

        enc_text = QLabel("Your personal messages are end-to-end encrypted")
        enc_text.setFont(QFont("Segoe UI", 9))
        enc_text.setStyleSheet(f"color: {_MUTED};")

        enc_row.addWidget(lock_lbl)
        enc_row.addWidget(enc_text)

        terms = QLabel("Terms & Privacy Policy")
        terms.setFont(QFont("Segoe UI", 9))
        terms.setStyleSheet(f"color: {_MUTED};")

        footer.addLayout(f1_layout)
        footer.addLayout(enc_row)
        footer.addWidget(terms, alignment=Qt.AlignmentFlag.AlignCenter)

        outer_layout.addLayout(footer)

        # 4. Action Bar (Status text + Refresh + Cancel/Close)
        action_bar = QHBoxLayout()
        action_bar.setContentsMargins(0, 4, 0, 0)
        action_bar.setSpacing(12)

        self.lbl_status = QLabel("📱 Scan this QR in WhatsApp → Linked Devices. Stable for ~45s.")
        self.lbl_status.setFont(QFont("Segoe UI", 10))
        self.lbl_status.setStyleSheet("color: #54656F;")

        btn_refresh = QPushButton("🔄 Refresh QR")
        btn_refresh.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_refresh.setFixedHeight(34)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: #FFFFFF;
                border-radius: 8px;
                padding: 0 18px;
                border: none;
            }
            QPushButton:hover { background-color: #0369A1; }
        """)
        btn_refresh.clicked.connect(self._manual_refresh)

        btn_close = QPushButton("Cancel / Close")
        btn_close.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_close.setFixedHeight(34)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #E2E8F0;
                color: #334155;
                border-radius: 8px;
                padding: 0 18px;
                border: 1px solid #CBD5E1;
            }
            QPushButton:hover { background-color: #CBD5E1; }
        """)
        btn_close.clicked.connect(self._on_close)

        action_bar.addWidget(self.lbl_status)
        action_bar.addStretch()
        action_bar.addWidget(btn_refresh)
        action_bar.addWidget(btn_close)

        outer_layout.addLayout(action_bar)

        scroll.setWidget(container)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(scroll)

        # Connect internal signal for thread-safe QR rendering
        self.qr_ready.connect(self._render_qr_from_data_url)

        # Start session and background polling
        threading.Thread(target=self._start_session_once, daemon=True).start()

        if qr_data_url:
            self._render_qr_from_data_url(qr_data_url)
            self._start_poll_timer()
        else:
            QTimer.singleShot(2000, self._start_poll_timer)

    # ── State Rendering Helpers ───────────────────────────────────────────────

    def _apply_loading_state(self, message: str):
        """Authentic clean QR loading placeholder matching WhatsApp Web."""
        self.qr_label.setPixmap(QPixmap())
        self.qr_label.setStyleSheet(f"""
            QLabel {{
                background-color: #F8F9FA;
                border: 1px solid {_BORDER};
                border-radius: 12px;
                color: {_SUBTEXT};
                font-family: 'Segoe UI';
                font-size: 13px;
                padding: 16px;
            }}
        """)
        self.qr_label.setText(f"⏳ {message}")

    def _on_qr_clicked(self, event):
        self._manual_refresh()

    def _manual_refresh(self):
        self._apply_loading_state("Refreshing QR code...")
        self.lbl_status.setText("Connecting to engine...")
        threading.Thread(target=self._start_session_once, daemon=True).start()
        threading.Thread(target=self._fetch_qr_worker, daemon=True).start()

    # ── Session & Engine Logic (100% Preserved) ───────────────────────────────

    def _start_session_once(self):
        waha_url = get_setting("waha_url", "http://localhost:3000").rstrip("/")
        try:
            port = int(waha_url.split(":")[-1])
        except Exception:
            port = 3000

        try:
            httpx.get(f"{waha_url}/health", timeout=2.0)
        except Exception:
            WAHALauncher.start_waha_engine(port=port)
            import time
            time.sleep(2.0)

        try:
            resp = httpx.get(f"{waha_url}/api/qr", params={"session": self.session_name}, timeout=3.0)
            engine_data = resp.json()
            engine_status = engine_data.get("status", "").upper()
        except Exception:
            engine_status = "UNKNOWN"

        if engine_status in ("WORKING", "SCAN_QR_CODE", "STARTING"):
            return

        try:
            httpx.post(
                f"{waha_url}/api/sessions/start",
                json={"session": self.session_name, "scan_qr": self.is_new_account},
                timeout=5.0
            )
        except Exception:
            pass

    def _start_poll_timer(self):
        if self._stopped:
            return
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2500)
        self._poll_timer.timeout.connect(self._fetch_qr_async)
        self._poll_timer.start()
        self._fetch_qr_async()

    def _fetch_qr_async(self):
        if self._stopped:
            return
        threading.Thread(target=self._fetch_qr_worker, daemon=True).start()

    def _fetch_qr_worker(self):
        if self._stopped:
            return
        try:
            waha_url = get_setting("waha_url", "http://localhost:3000").rstrip("/")
            response = httpx.get(
                f"{waha_url}/api/qr",
                params={"session": self.session_name},
                timeout=4.0
            )
            data = response.json()
            status = data.get("status", "").upper()

            if status == "WORKING":
                self.qr_ready.emit("__CONNECTED__")
                return

            qr_data = data.get("qr")
            if qr_data:
                self.qr_ready.emit(qr_data)
            elif status == "SCAN_QR_CODE":
                self.qr_ready.emit("__WAITING__")
            else:
                self.qr_ready.emit(f"__STATUS__{status}")

        except httpx.ConnectError:
            self.qr_ready.emit("__ENGINE_OFFLINE__")
        except Exception as e:
            self.qr_ready.emit(f"__ERROR__{e}")

    def _render_qr_from_data_url(self, signal_value: str):
        if self._stopped:
            return

        if signal_value == "__CONNECTED__":
            self.qr_label.setStyleSheet("""
                QLabel {
                    background-color: #F0FDF4;
                    border: 2px solid #22C55E;
                    border-radius: 12px;
                    font-size: 15px;
                    font-weight: 700;
                    color: #15803D;
                    padding: 16px;
                }
            """)
            self.qr_label.setText("✅ WhatsApp Connected!\n\nYou can close this window.")
            self.lbl_status.setText("✅ WhatsApp session is WORKING.")
            if hasattr(self, '_poll_timer'):
                self._poll_timer.stop()
            QTimer.singleShot(1500, self.accept)
            return

        if signal_value == "__ENGINE_OFFLINE__":
            self._apply_loading_state("Starting WhatsApp Engine...")
            return

        if signal_value == "__WAITING__":
            self._apply_loading_state("Generating QR Code...")
            return

        if signal_value.startswith("__STATUS__"):
            status = signal_value.replace("__STATUS__", "")
            self._apply_loading_state(f"Status: {status}\nClick to refresh.")
            return

        if signal_value.startswith("__ERROR__"):
            self._apply_loading_state("Click to reload QR code.")
            return

        # Actual QR image rendering
        try:
            if "base64," in signal_value:
                b64_data = signal_value.split("base64,", 1)[1]
            else:
                b64_data = signal_value
            image_bytes = base64.b64decode(b64_data)
            pixmap = QPixmap()
            pixmap.loadFromData(image_bytes)
            if not pixmap.isNull():
                pixmap_with_logo = add_whatsapp_center_logo(pixmap)
                self.qr_label.setStyleSheet("QLabel { background-color: #FFFFFF; border: none; padding: 0; }")
                self.qr_label.setText("")
                self.qr_label.setPixmap(
                    pixmap_with_logo.scaled(240, 240, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
            else:
                self._apply_loading_state("Click to reload QR code.")
        except Exception:
            self._apply_loading_state("Click to reload QR code.")

    def _handle_cancel_or_close(self):
        self._stopped = True
        if hasattr(self, '_poll_timer'):
            self._poll_timer.stop()

        session_name = self.session_name

        parent_window = self.parent()
        if parent_window and hasattr(parent_window, "_user_cancelled_modals"):
            parent_window._user_cancelled_modals.add(session_name)

        def cleanup_worker():
            try:
                waha_url = get_setting("waha_url", "http://localhost:3000").rstrip("/")
                httpx.post(f"{waha_url}/api/sessions/logout", json={"session": session_name}, timeout=4.0)
            except Exception:
                pass

            accounts = get_all_accounts()
            for acc in accounts:
                if acc["session_name"] == session_name:
                    if acc.get("status") != "WORKING" and not acc.get("phone_number"):
                        delete_account(session_name)
                    else:
                        update_account_status(session_name, "STOPPED", last_error="Cancelled by user")
                    break

        threading.Thread(target=cleanup_worker, daemon=True).start()

    def _on_close(self):
        self._handle_cancel_or_close()
        self.accept()

    def closeEvent(self, event):
        self._handle_cancel_or_close()
        super().closeEvent(event)
