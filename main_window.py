import threading
import asyncio
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QScrollArea
)
from PyQt6.QtCore import QTimer, pyqtSignal

from ui.theme import CYBER_CORPORATE_QSS, COLOR_DARK_BG
from ui.sidebar import SidebarNavWidget
from ui.pages.dashboard_page import DashboardPage
from ui.pages.rule_studio_page import RuleStudioPage
from ui.pages.ai_page import AIPage
from ui.pages.accounts_page import AccountsPage
from ui.pages.settings_page import SettingsPage

import database as db
from queue_processor import DurableQueueProcessor
from webhook_server import set_session_status_callback
from waha_launcher import WAHALauncher
from waha_client import WAHAClient


class MainWindow(QMainWindow):
    # Qt signal for safe cross-thread UI updates
    session_status_received = pyqtSignal(str, dict)

    def __init__(self, queue_processor: DurableQueueProcessor):
        super().__init__()
        self.queue_processor = queue_processor

        self.setWindowTitle("CyberSolu Auto — Enterprise WhatsApp Support Studio")
        self.resize(1280, 820)
        self.setMinimumSize(850, 550)  # Responsive minimum window size

        # Apply Refined Corporate Dark Theme QSS
        self.setStyleSheet(CYBER_CORPORATE_QSS)

        # Main Root Horizontal Container (Sidebar + Content View)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Navigation Sidebar
        self.sidebar = SidebarNavWidget()
        self.sidebar.page_changed.connect(self._on_page_changed)
        self.sidebar.global_toggle_changed.connect(self._on_global_toggle_changed)
        root_layout.addWidget(self.sidebar)

        # 2. Main Multi-Page Stacked Area
        self.stacked = QStackedWidget()

        # Instantiate Pages
        self.page_dashboard = DashboardPage()
        self.page_rules = RuleStudioPage()
        self.page_ai = AIPage()
        self.page_accounts = AccountsPage()
        self.page_settings = SettingsPage()

        def wrap_scroll(widget: QWidget) -> QScrollArea:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(widget)
            scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {COLOR_DARK_BG}; }}")
            return scroll

        self.stacked.addWidget(wrap_scroll(self.page_dashboard))   # Index 0
        self.stacked.addWidget(self.page_rules)                    # Index 1 (internal scroll)
        self.stacked.addWidget(wrap_scroll(self.page_ai))          # Index 2
        self.stacked.addWidget(wrap_scroll(self.page_accounts))    # Index 3
        self.stacked.addWidget(wrap_scroll(self.page_settings))    # Index 4

        root_layout.addWidget(self.stacked, stretch=1)

        # Connect Rule Studio Signals
        self._connect_rule_signals()

        # Live timer to refresh metrics and active activity log
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._refresh_live_metrics)
        self.timer.start()

        # Connect session_status_received signal to handler on MAIN Qt thread
        self.session_status_received.connect(self._handle_session_status_on_main_thread)

        # Register the webhook callback
        set_session_status_callback(self._session_status_from_background_thread)

        # Initial rules load
        self.refresh_rules_matrix()

    def _session_status_from_background_thread(self, status: str, payload: dict):
        self.session_status_received.emit(status, payload)

    def _handle_session_status_on_main_thread(self, status: str, payload: dict):
        self.sidebar.update_session_status(status)
        session_name = payload.get("session") or payload.get("session_name", "default")
        phone = payload.get("phone", "")
        error = payload.get("error", "")

        # Update DB account status
        db.update_account_status(session_name, status, phone_number=phone, last_error=error)
        self.page_accounts.refresh_accounts_matrix()

        if status.upper() == "WORKING":
            db.backup_session_keys(session_name)

    def _connect_rule_signals(self):
        editor = self.page_rules.rule_editor
        registry = self.page_rules.rule_registry

        editor.rule_added.connect(self._on_rule_added)
        editor.rule_modified.connect(self._on_rule_modified)
        editor.rule_deleted.connect(self._on_rule_deleted)

        registry.rule_toggled.connect(self._on_rule_toggled)
        registry.rules_imported.connect(self._on_rules_imported)

    def refresh_rules_matrix(self):
        rules = db.get_all_rules()
        self.page_rules.rule_registry.display_rules(rules)
        self.page_dashboard.refresh_metrics()

    def _refresh_live_metrics(self):
        self.sidebar.update_session_status()
        if self.stacked.currentIndex() == 0:
            self.page_dashboard.refresh_metrics()

    def _on_page_changed(self, index: int):
        self.stacked.setCurrentIndex(index)
        if index == 0:
            self.page_dashboard.refresh_metrics()
        elif index == 1:
            self.refresh_rules_matrix()
        elif index == 3:
            self.page_accounts.refresh_accounts_matrix()

    def _on_global_toggle_changed(self, enabled: bool):
        self.queue_processor.set_global_automation(enabled)
        if enabled:
            # Re-activating engine — ensure gateway process & ALL account sessions are active
            threading.Thread(target=self._start_all_accounts_background, daemon=True).start()

    def _start_all_accounts_background(self):
        w_url = db.get_setting("waha_url", "http://localhost:3000")
        try:
            port = int(w_url.rstrip("/").split(":")[-1])
        except Exception:
            port = 3000
        WAHALauncher.start_waha_engine(port=port)

        client = WAHAClient()
        accounts = db.get_all_accounts()
        for acc in accounts:
            if acc.get("is_enabled", 1) == 1:
                try:
                    asyncio.run(client.start_session(acc["session_name"]))
                except Exception:
                    pass

    def _on_rule_added(self, rule_data: dict):
        db.add_rule(
            name=rule_data["rule_name"],
            operator=rule_data["matching_operator"],
            keyword=rule_data["keyword_payload"],
            response=rule_data["response_message"],
            is_enabled=rule_data["is_enabled"],
            attachments=rule_data.get("attachments")
        )
        self.refresh_rules_matrix()

    def _on_rule_modified(self, rule_id: int, rule_data: dict):
        db.update_rule(
            rule_id=rule_id,
            name=rule_data["rule_name"],
            operator=rule_data["matching_operator"],
            keyword=rule_data["keyword_payload"],
            response=rule_data["response_message"],
            is_enabled=rule_data["is_enabled"],
            attachments=rule_data.get("attachments")
        )
        self.refresh_rules_matrix()

    def _on_rule_deleted(self, rule_id: int):
        db.delete_rule(rule_id)
        self.refresh_rules_matrix()

    def _on_rule_toggled(self, rule_id: int, is_enabled: int):
        db.toggle_rule(rule_id, is_enabled)
        self.refresh_rules_matrix()

    def _on_rules_imported(self, imported_rules: list):
        for r in imported_rules:
            db.add_rule(
                name=r.get("rule_name", "Imported Rule"),
                operator=r.get("matching_operator", "Contains"),
                keyword=r.get("keyword_payload", ""),
                response=r.get("response_message", ""),
                is_enabled=r.get("is_enabled", 1),
                attachments=r.get("attachments")
            )
        self.refresh_rules_matrix()

    def closeEvent(self, event):
        try:
            db.clear_activity_logs()
        except Exception:
            pass
        w_url = db.get_setting("waha_url", "http://localhost:3000").rstrip("/")
        try:
            port = int(w_url.split(":")[-1])
        except Exception:
            port = 3000
        WAHALauncher.stop_waha_engine(port=port)
        event.accept()
