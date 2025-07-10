# -*- coding: utf-8 -*-

import os

from aqt import mw
from aqt.editor import Editor
from aqt.qt import (
    QAction,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QIcon,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import showWarning, tooltip
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView

# MODIFICA: Aggiunto 'write_config' per il salvataggio immediato
from .config import RATIO_OPTIONS, get_config, write_config
from .logic import GET_SELECTION_HTML_JS, on_text_pasted_from_ai
from .ui import PromptManagerDialog

_persistent_ai_dock_profile = None

def get_persistent_ai_dock_profile():
    """Creates and returns a single, persistent QWebEngineProfile for the AI Dock."""
    global _persistent_ai_dock_profile
    if _persistent_ai_dock_profile is None:
        profile_dir = os.path.join(mw.pm.profileFolder(), "ai_dock_cache")
        os.makedirs(profile_dir, exist_ok=True)
        
        _persistent_ai_dock_profile = QWebEngineProfile("ai_dock_shared", mw)
        _persistent_ai_dock_profile.setPersistentStoragePath(profile_dir)
        _persistent_ai_dock_profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        _persistent_ai_dock_profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        
        settings = _persistent_ai_dock_profile.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)

    return _persistent_ai_dock_profile

class CustomWebView(QWebEngineView):
    """
    A custom QWebEngineView that handles the context menu for pasting into specific fields.
    """
    def __init__(self, target_object, parent=None):
        super().__init__(parent)
        self.target_object = target_object
        self.is_editor = isinstance(self.target_object, Editor)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()

        if self.is_editor and self.target_object.note and self.page().hasSelection():
            menu.addSeparator()
            paste_icon = QIcon.fromTheme("edit-paste", QIcon(os.path.join(os.path.dirname(__file__), "icons", "paste.png")))
            paste_menu = menu.addMenu(paste_icon, "Paste to Field")
            try:
                field_names = [f['name'] for f in self.target_object.note.model()['flds']]
            except Exception:
                field_names = []

            if not field_names:
                paste_menu.setEnabled(False)
            else:
                for field_name in field_names:
                    action = QAction(field_name, paste_menu)
                    action.triggered.connect(
                        lambda checked=False, fn=field_name: self.trigger_paste_to_field(fn)
                    )
                    paste_menu.addAction(action)
        
        menu.addSeparator()
        save_html_action = QAction("Save Page HTML...", menu)
        save_html_action.triggered.connect(self.save_page_html)
        menu.addAction(save_html_action)

        menu.exec(event.globalPos())

    def trigger_paste_to_field(self, field_name: str):
        """Gets the selected HTML from the webview and calls the main paste logic."""
        def paste_handler(html: str):
            if not html:
                tooltip("No content selected to paste.")
                return
            on_text_pasted_from_ai(self.target_object, html, field_name)

        self.page().runJavaScript(GET_SELECTION_HTML_JS, paste_handler)

    def save_page_html(self):
        """Gets the current page's HTML and prompts the user to save it."""
        self.page().runJavaScript("document.documentElement.outerHTML", self._save_html_callback)

    def _save_html_callback(self, html_content):
        """Callback to save the HTML content to a file."""
        if not html_content:
            tooltip("No HTML content to save.")
            return
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        default_filepath = os.path.join(desktop_path, "ai_dock_page.html")
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Page HTML", default_filepath, "HTML Files (*.html);;All Files (*)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                tooltip(f"Page HTML saved to: {file_path}")
            except Exception as e:
                showWarning(f"Failed to save HTML: {e}")

def inject_ai_dock(target_object):
    if not target_object or hasattr(target_object, "_ai_dock_injected_flag"): return
    target_object._ai_dock_injected_flag = True

    is_editor = isinstance(target_object, Editor)
    anki_webview = target_object.web
    parent_window = getattr(target_object, 'parentWindow', None) or (target_object.window() if hasattr(target_object, 'window') else mw)

    config = get_config()
    settings_key = "editor_settings" if is_editor else "reviewer_settings"
    context_settings = config[settings_key]

    ai_panel = QWidget(parent_window)
    ai_panel.setVisible(context_settings.get("visible", True))
    ai_layout = QVBoxLayout(ai_panel)
    ai_layout.setContentsMargins(0, 0, 0, 0); ai_layout.setSpacing(2)

    controls_widget = QWidget(ai_panel)
    controls_layout = QHBoxLayout(controls_widget)
    controls_layout.setContentsMargins(2, 2, 2, 2); controls_layout.setSpacing(4)

    site_combo_box = QComboBox(controls_widget)
    site_combo_box.addItems(list(config.get("ai_sites", {}).keys()))
    site_combo_box.setCurrentText(config.get("last_choice", ""))
    controls_layout.addWidget(site_combo_box)

    zoom_spinbox = QDoubleSpinBox(controls_widget)
    zoom_spinbox.setRange(0.3, 3.0); zoom_spinbox.setSingleStep(0.1)
    zoom_spinbox.setValue(float(context_settings.get("zoom_factor", 1.0)))
    controls_layout.addWidget(zoom_spinbox)
    
    ratio_combobox = QComboBox(controls_widget)
    ratio_combobox.addItems(RATIO_OPTIONS)
    ratio_combobox.setCurrentText(context_settings.get("splitRatio", "1:1"))
    controls_layout.addWidget(ratio_combobox)

    location_combo = QComboBox(controls_widget)
    location_combo.addItems(["right", "left", "above", "below"])
    location_combo.setCurrentText(context_settings.get("location", "right"))
    controls_layout.addWidget(location_combo)

    field_name_combobox = QComboBox(controls_widget)
    field_name_combobox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    if is_editor: controls_layout.addWidget(field_name_combobox)
    else: field_name_combobox.setVisible(False)

    settings_button = QPushButton("⚙️", controls_widget)
    settings_button.setToolTip("Open AI Dock Settings")
    settings_button.clicked.connect(lambda: PromptManagerDialog(parent_window).exec())
    controls_layout.addWidget(settings_button)
    ai_layout.addWidget(controls_widget)

    profile = get_persistent_ai_dock_profile()
    ai_page = QWebEnginePage(profile, ai_panel)

    ai_dock_webview = CustomWebView(target_object=target_object, parent=ai_panel)
    ai_dock_webview.setPage(ai_page)
    ai_dock_webview.setZoomFactor(zoom_spinbox.value())
    ai_layout.addWidget(ai_dock_webview, 1)

    initial_url = config.get("ai_sites", {}).get(site_combo_box.currentText())
    if initial_url: ai_dock_webview.load(QUrl(initial_url))

    target_object.ai_dock_webview = ai_dock_webview
    if is_editor: target_object.ai_dock_field_combobox = field_name_combobox
    target_object.ai_dock_site_combobox = site_combo_box
    target_object.ai_dock_panel = ai_panel

    container_of_anki_webview = anki_webview.parentWidget()
    if not container_of_anki_webview: return
    parent_layout = container_of_anki_webview.layout()
    web_index = -1
    if parent_layout and parent_layout.indexOf(anki_webview) != -1:
        web_index = parent_layout.indexOf(anki_webview)
        parent_layout.removeWidget(anki_webview)
    else: 
        grandparent = container_of_anki_webview.parentWidget()
        if grandparent and grandparent.layout():
            parent_layout = grandparent.layout()
            web_index = parent_layout.indexOf(container_of_anki_webview)
            if web_index != -1:
                parent_layout.removeWidget(container_of_anki_webview)
            else: return 
        else: return 
    
    main_view_wrapper = QWidget(parent_window)
    main_view_wrapper_layout = QHBoxLayout(main_view_wrapper)
    main_view_wrapper_layout.setContentsMargins(0,0,0,0)
    main_view_wrapper_layout.addWidget(anki_webview)

    splitter = QSplitter(parent_window)
    target_object._ai_dock_injected_splitter = splitter
    current_location = context_settings.get("location", "right")
    splitter.setOrientation(Qt.Orientation.Horizontal if current_location in ["right", "left"] else Qt.Orientation.Vertical)
    widgets = [main_view_wrapper, ai_panel]
    if current_location in ["left", "above"]: widgets.reverse()
    splitter.addWidget(widgets[0]); splitter.addWidget(widgets[1])
    parent_layout.insertWidget(web_index, splitter, 1)

    # --- Signal Handlers ---
    def update_ratio_handler(ratio_str):
        nonlocal current_location
        if not splitter or not hasattr(splitter, 'sizes'): return
        try:
            r1, r2 = map(int, ratio_str.split(':'))
            total = r1 + r2
            if total == 0: return
            size_dim = splitter.width() if splitter.orientation() == Qt.Orientation.Horizontal else splitter.height()
            if size_dim <= 10:
                QTimer.singleShot(250, lambda: update_ratio_handler(ratio_str))
                return
            s1 = int(size_dim * r1 / total); s2 = size_dim - s1
            sizes = [s1, s2]
            if current_location in ["left", "above"]: sizes.reverse()
            splitter.setSizes(sizes)
            get_config()[settings_key]['splitRatio'] = ratio_str
            write_config() # MODIFICA: Salvataggio immediato
        except (ValueError, Exception):
            splitter.setSizes([1, 1])

    def on_ai_site_changed_handler(ai_name):
        url = get_config().get("ai_sites", {}).get(ai_name)
        if url: ai_dock_webview.load(QUrl(url))
        get_config()['last_choice'] = ai_name
        write_config() # MODIFICA: Salvataggio immediato

    def update_zoom_factor_handler(value):
        ai_dock_webview.setZoomFactor(value)
        get_config()[settings_key]['zoom_factor'] = value
        write_config() # MODIFICA: Salvataggio immediato

    def update_dock_location_handler(new_loc_str):
        nonlocal current_location
        current_location = new_loc_str
        get_config()[settings_key]['location'] = new_loc_str
        write_config() # MODIFICA: Salvataggio immediato
        tooltip("Dock location will update when you reopen this window.", parent=parent_window)

    def save_target_field_name_handler(field_text):
        get_config()['target_field'] = field_text
        write_config() # MODIFICA: Salvataggio immediato

    # Connect signals
    site_combo_box.currentTextChanged.connect(on_ai_site_changed_handler)
    zoom_spinbox.valueChanged.connect(update_zoom_factor_handler)
    ratio_combobox.currentTextChanged.connect(update_ratio_handler)
    location_combo.currentTextChanged.connect(update_dock_location_handler)
    if is_editor:
        field_name_combobox.currentTextChanged.connect(save_target_field_name_handler)

    QTimer.singleShot(300, lambda: update_ratio_handler(ratio_combobox.currentText()))
