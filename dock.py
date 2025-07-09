# -*- coding: utf-8 -*-

import os
from aqt import mw
from aqt.qt import (
    QWidget, QVBoxLayout, QComboBox, QSplitter, QHBoxLayout, QLabel,
    QDoubleSpinBox, QSizePolicy, QAction, QIcon, QPushButton, QFormLayout
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtCore import QUrl, QTimer, Qt
from aqt.editor import Editor

from .config import get_config, write_config, RATIO_OPTIONS
from .logic import on_text_pasted_from_ai, GET_SELECTION_HTML_JS
from .ui import PromptManagerDialog

class CustomWebView(QWebEngineView):
    def __init__(self, paste_callback, get_field_name_callback, is_editor, parent=None): # Added parent
        super().__init__(parent) # Pass parent
        self.paste_callback = paste_callback
        self.get_field_name_callback = get_field_name_callback
        self.is_editor = is_editor

    def contextMenuEvent(self, event):
        menu = self.page().createStandardContextMenu()
        if self.is_editor and self.page().hasSelection():
            menu.addSeparator()
            field_name = self.get_field_name_callback() # This gets the target field in Anki
            if field_name:
                action_text = f"Paste to Anki field '{field_name}'"
                icon = QIcon.fromTheme("edit-paste", QIcon(os.path.join(os.path.dirname(__file__), "icons", "paste.png"))) # Example icon path
                paste_action = QAction(icon, action_text, menu) # Create QAction
                paste_action.triggered.connect(self.paste_callback) # Connect its triggered signal
                menu.addAction(paste_action) # Add QAction to menu
        menu.exec(event.globalPos())

def inject_ai_dock(target_object):
    if not target_object or hasattr(target_object, "_ai_dock_injected_flag"): return
    target_object._ai_dock_injected_flag = True # Set flag early

    is_editor = isinstance(target_object, Editor)
    anki_webview = target_object.web # This is Anki's main webview (editor field area or reviewer content)

    # Determine parent window carefully
    if hasattr(target_object, 'parentWindow') and target_object.parentWindow:
        parent_window = target_object.parentWindow
    elif hasattr(target_object, 'window') and callable(target_object.window): # For reviewer
        parent_window = target_object.window()
    else:
        parent_window = mw # Fallback to main window

    config = get_config()
    settings_key = "editor_settings" if is_editor else "reviewer_settings"
    context_settings = config[settings_key] # This is a mutable reference to a part of config

    ai_panel = QWidget(parent_window) # Parent the panel to the window
    ai_panel.setVisible(context_settings.get("visible", True))
    ai_layout = QVBoxLayout(ai_panel)
    ai_layout.setContentsMargins(0, 0, 0, 0); ai_layout.setSpacing(2) # Reduced spacing

    controls_widget = QWidget(ai_panel) # Parent controls to panel
    controls_layout = QHBoxLayout(controls_widget)
    controls_layout.setContentsMargins(2, 2, 2, 2); controls_layout.setSpacing(4) # Reduced margins/spacing

    ai_sites = config.get("ai_sites", {})
    site_combo_box = QComboBox(controls_widget) # Parent to controls widget
    if ai_sites: site_combo_box.addItems(list(ai_sites.keys()))

    current_last_choice = config.get("last_choice", "")
    if current_last_choice and current_last_choice in ai_sites:
        site_combo_box.setCurrentText(current_last_choice)
    elif ai_sites: # Fallback if last_choice is invalid or not set
        site_combo_box.setCurrentIndex(0)
        config["last_choice"] = site_combo_box.currentText() # Update config
        # No immediate write_config here, will be saved by other actions or settings dialog

    controls_layout.addWidget(site_combo_box)

    zoom_spinbox = QDoubleSpinBox(controls_widget); zoom_spinbox.setMinimumWidth(60) # Parent and set min width
    zoom_spinbox.setRange(0.3, 3.0); zoom_spinbox.setSingleStep(0.1) # Wider range, adjusted step
    zoom_spinbox.setValue(float(context_settings.get("zoom_factor", 1.0)))
    zoom_spinbox.setDecimals(1) # Show one decimal place
    controls_layout.addWidget(zoom_spinbox)

    ratio_combobox = QComboBox(controls_widget); ratio_combobox.setMinimumWidth(70) # Parent and set min width
    ratio_combobox.addItems(RATIO_OPTIONS)
    ratio_combobox.setCurrentText(context_settings.get("splitRatio", "1:1")) # Default to 1:1 for safety
    controls_layout.addWidget(ratio_combobox)

    location_combo = QComboBox(controls_widget); location_combo.setMinimumWidth(80) # Parent and set min width
    location_combo.addItems(["right", "left", "above", "below"])
    location_combo.setCurrentText(context_settings.get("location", "right"))
    controls_layout.addWidget(location_combo)

    field_name_combobox = QComboBox(controls_widget) # Parent to controls widget
    field_name_combobox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    field_name_combobox.setEnabled(is_editor)
    if is_editor: controls_layout.addWidget(field_name_combobox) # Only add if editor

    settings_button = QPushButton("⚙️", controls_widget) # Use gear icon, parented
    settings_button.setToolTip("Open AI Dock Settings")
    settings_button.clicked.connect(lambda: PromptManagerDialog(parent_window).exec())
    controls_layout.addWidget(settings_button)
    # controls_layout.addStretch() # Removed stretch to keep controls compact
    ai_layout.addWidget(controls_widget)

    # Unique profile name incorporating window and context
    profile_name = f"ai_dock_{id(parent_window)}_{settings_key}"
    profile = QWebEngineProfile.defaultProfile() # Try default first
    if hasattr(QWebEngineProfile, 'clearHttpCache') and hasattr(QWebEngineProfile,'clearAllVisitedLinks'): # Check for methods
        # Attempt to use a persistent profile if possible, otherwise ephemeral
        try:
            persistent_profile = QWebEngineProfile(profile_name, parent_window)
            profile = persistent_profile
        except RuntimeError: # Can happen if not allowed (e.g. in some test environments)
            profile = QWebEngineProfile(parent_window) # Ephemeral

    ai_page = QWebEnginePage(profile, ai_panel) # Parent page to panel

    def _paste_into_field_callback(): # Renamed to avoid conflict
        if not is_editor: return
        target_field_name = field_name_combobox.currentText()
        if not target_field_name:
            showWarning("Please select a target Anki field.", parent=parent_window)
            return
        target_object.ai_dock_webview.page().runJavaScript(GET_SELECTION_HTML_JS,
            lambda html_content: on_text_pasted_from_ai(target_object, html_content, target_field_name))

    ai_dock_webview = CustomWebView(_paste_into_field_callback,
                                 lambda: field_name_combobox.currentText() if is_editor else "",
                                 is_editor=is_editor,
                                 parent=ai_panel)
    ai_dock_webview.setPage(ai_page)
    ai_dock_webview.setZoomFactor(zoom_spinbox.value())
    ai_layout.addWidget(ai_dock_webview, 1) # Add with stretch factor

    current_site_name = site_combo_box.currentText()
    initial_url = ai_sites.get(current_site_name)
    if initial_url: ai_dock_webview.load(QUrl(initial_url))
    elif ai_sites: # Fallback if current name from combobox (e.g. from old config) is not in ai_sites
        first_valid_site_name = list(ai_sites.keys())[0]
        ai_dock_webview.load(QUrl(ai_sites[first_valid_site_name]))
        site_combo_box.setCurrentText(first_valid_site_name) # Correct combobox
        config["last_choice"] = first_valid_site_name # Correct config
        # No write_config here, saved by other interactions

    target_object.ai_dock_webview = ai_dock_webview
    if is_editor: target_object.ai_dock_field_combobox = field_name_combobox
    target_object.ai_dock_site_combobox = site_combo_box
    target_object.ai_dock_panel = ai_panel

    # --- Splitter Injection ---
    # anki_webview is the main Anki editor area or reviewer content area
    # We need to find its direct parent layout to insert the splitter

    # For Editor, anki_webview is usually target_object.web (an EditorWebView instance)
    # Its parent is often a QStackedWidget or similar within the Editor's main layout.
    # For Reviewer, anki_webview is mw.reviewer.web

    container_of_anki_webview = anki_webview.parentWidget()
    if not container_of_anki_webview: return

    parent_layout_of_anki_webview_container = container_of_anki_webview.layout()

    # If anki_webview is directly in a layout (less common for complex widgets like Editor)
    if parent_layout_of_anki_webview_container and parent_layout_of_anki_webview_container.indexOf(anki_webview) != -1:
        web_index = parent_layout_of_anki_webview_container.indexOf(anki_webview)
        parent_layout_of_anki_webview_container.removeWidget(anki_webview)
    # More common: anki_webview is the central widget of its parent, or parent has no layout yet
    elif hasattr(container_of_anki_webview, 'setCentralWidget') or not parent_layout_of_anki_webview_container :
         # This case needs careful handling. Assuming anki_webview is *the* main content of its container.
         # We will replace the container_of_anki_webview with the splitter.
         grandparent_layout = container_of_anki_webview.parentWidget().layout()
         if not grandparent_layout: return # Cannot proceed
         web_index = grandparent_layout.indexOf(container_of_anki_webview)
         grandparent_layout.removeWidget(container_of_anki_webview) # Remove the old container
         # The anki_webview itself will be added to the new main_view_wrapper below.
         parent_layout_of_anki_webview_container = grandparent_layout # This is where splitter goes
    else: # Cannot determine how to inject
        return


    main_view_wrapper = QWidget(parent_window) # Wrapper for Anki's original webview
    main_view_wrapper_layout = QHBoxLayout(main_view_wrapper)
    main_view_wrapper_layout.setContentsMargins(0,0,0,0)
    main_view_wrapper_layout.addWidget(anki_webview) # Place Anki's webview into this wrapper

    splitter = QSplitter(parent_window) # Parent splitter to window
    target_object._ai_dock_injected_splitter = splitter

    # Use 'location' from context_settings, which is tied to the current config
    current_location = context_settings.get("location", "right")

    if current_location in ["right", "left"]:
        splitter.setOrientation(Qt.Orientation.Horizontal)
        splitter.addWidget(main_view_wrapper if current_location == "right" else ai_panel)
        splitter.addWidget(ai_panel if current_location == "right" else main_view_wrapper)
    else: # "above", "below"
        splitter.setOrientation(Qt.Orientation.Vertical)
        splitter.addWidget(main_view_wrapper if current_location == "below" else ai_panel)
        splitter.addWidget(ai_panel if current_location == "below" else main_view_wrapper)

    # Insert splitter into the layout where anki_webview (or its container) was
    if isinstance(parent_layout_of_anki_webview_container, QHBoxLayout) or \
       isinstance(parent_layout_of_anki_webview_container, QVBoxLayout) or \
       isinstance(parent_layout_of_anki_webview_container, QFormLayout):
        parent_layout_of_anki_webview_container.insertWidget(web_index, splitter, 1 if isinstance(parent_layout_of_anki_webview_container, QFormLayout) else -1)
    elif hasattr(parent_layout_of_anki_webview_container, 'addWidget'): # For basic layouts
        parent_layout_of_anki_webview_container.addWidget(splitter)


    # --- Signal Handlers (defined within inject_ai_dock to capture necessary variables) ---
    def update_ratio_handler(ratio_str, attempt=1): # Renamed to avoid conflict if we move it
        MAX_ATTEMPTS = 6 # Increased attempts
        RETRY_DELAY_MS = 250 # Increased delay

        nonlocal current_location # Use the location determined during injection

        # Ensure splitter is still valid (it's captured from outer scope)
        if not splitter or not hasattr(splitter, 'sizes'): return

        try:
            r1, r2 = map(int, ratio_str.split(':'))
            total = r1 + r2
            if total == 0:
                splitter.setSizes([1, 1]); return

            size_dim = splitter.width() if splitter.orientation() == Qt.Orientation.Horizontal else splitter.height()

            if size_dim <= 10: # If too small (e.g. hidden parent), retry or fallback
                if attempt < MAX_ATTEMPTS:
                    QTimer.singleShot(RETRY_DELAY_MS, lambda: update_ratio_handler(ratio_str, attempt + 1))
                    return
                else: # Fallback after max attempts
                    # Use a fixed pixel size as a last resort, as percentages of 0 are still 0
                    fallback_s = [200, 200]
                    if current_location in ["left", "above"]: fallback_s.reverse()
                    splitter.setSizes(fallback_s)
                    # Update config to a safe default if it failed consistently
                    active_config = get_config()
                    active_config[settings_key]['splitRatio'] = "1:1"
                    write_config(active_config)
                    return

            s1 = int(size_dim * r1 / total)
            s2 = size_dim - s1
            sizes = [s1, s2]

            # Prevent either panel from becoming too small or zero if main dimension is positive
            min_panel_size = 50 # Minimum pixels for a panel
            if size_dim > min_panel_size * 2: # Only apply if there's enough space
                if sizes[0] < min_panel_size:
                    sizes[0] = min_panel_size
                    sizes[1] = max(min_panel_size, size_dim - min_panel_size)
                elif sizes[1] < min_panel_size:
                    sizes[1] = min_panel_size
                    sizes[0] = max(min_panel_size, size_dim - min_panel_size)
            elif size_dim > 0 and (sizes[0] == 0 or sizes[1] == 0) : # If not enough for min_panel_size, but still >0
                 sizes = [size_dim // 2, size_dim - (size_dim // 2)]


            if current_location in ["left", "above"]:
                sizes.reverse()

            splitter.setSizes(sizes)

            # Save successful ratio to config
            active_config = get_config() # Get fresh config before writing
            active_config[settings_key]['splitRatio'] = ratio_str
            write_config(active_config)

        except ValueError: # From map(int,...)
            splitter.setSizes([1,1])
            active_config = get_config(); active_config[settings_key]['splitRatio'] = "1:1"; write_config(active_config)
        except Exception as e:
            # print(f"AI Dock: Critical error in update_ratio_handler: {e}")
            try: splitter.setSizes([1,1])
            except: pass # splitter might be invalid
            active_config = get_config(); active_config[settings_key]['splitRatio'] = "1:1"; write_config(active_config)


    def on_ai_site_changed_handler(ai_name):
        active_config = get_config()
        url = active_config.get("ai_sites", {}).get(ai_name)
        if url:
            ai_dock_webview.load(QUrl(url)) # ai_dock_webview captured from outer scope
        active_config['last_choice'] = ai_name
        write_config(active_config)

    def update_zoom_factor_handler(value):
        ai_dock_webview.setZoomFactor(value) # ai_dock_webview captured
        active_config = get_config()
        active_config[settings_key]['zoom_factor'] = value
        write_config(active_config)

    def update_dock_location_handler(new_loc_str):
        nonlocal current_location # Modify the 'current_location' used by update_ratio_handler
        current_location = new_loc_str

        active_config = get_config()
        active_config[settings_key]['location'] = new_loc_str
        write_config(active_config)
        tooltip("Dock location saved. Please reopen this window (e.g., close and reopen editor/card) for the change to take full effect.", parent=parent_window)
        # A full UI reconstruction for location change is complex and usually requires reopening the view.

    def save_target_field_name_handler(field_text):
        active_config = get_config()
        active_config['target_field'] = field_text
        write_config(active_config)

    # Connect signals
    site_combo_box.currentTextChanged.connect(on_ai_site_changed_handler)
    zoom_spinbox.valueChanged.connect(update_zoom_factor_handler)
    ratio_combobox.currentTextChanged.connect(update_ratio_handler)
    location_combo.currentTextChanged.connect(update_dock_location_handler)
    if is_editor:
        field_name_combobox.currentTextChanged.connect(save_target_field_name_handler)

    # Initial call to set ratio, deferred slightly more to allow UI to fully initialize
    QTimer.singleShot(300, lambda: update_ratio_handler(ratio_combobox.currentText()))