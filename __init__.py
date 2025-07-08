# -*- coding: utf-8 -*-

import json
from aqt import mw, gui_hooks
from aqt.qt import (
    QWidget, QVBoxLayout, QComboBox, QSplitter, QHBoxLayout, QLabel,
    QDoubleSpinBox, QLineEdit, QAction, QKeySequence, QMenu, QApplication,
    QPushButton, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QTextEdit, QSizePolicy, QKeySequenceEdit, QGroupBox, QFormLayout, QIcon,
    QTabWidget
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtCore import QUrl, QTimer, Qt
from aqt.editor import Editor
from aqt.reviewer import Reviewer
from aqt.utils import showWarning, tooltip, showInfo
from aqt.addcards import AddCards
from aqt.browser import Browser
from aqt.editcurrent import EditCurrent
from anki.cards import Card
import os

# --- JS Snippet for getting selection as HTML ---
GET_SELECTION_HTML_JS = """
(function() {
    var selection = window.getSelection();
    if (selection.rangeCount > 0) {
        var div = document.createElement('div');
        div.appendChild(selection.getRangeAt(0).cloneContents());
        return div.innerHTML;
    }
    return '';
})()
"""

# --- CONFIGURATION MANAGEMENT ---

def get_config():
    """Loads the configuration, creating defaults and handling migrations."""
    config = mw.addonManager.getConfig(__name__)

    default_prompts = [
        {"name": "Explain Simply", "template": "Explain this concept in simple terms for a beginner: {text}", "shortcut": ""},
        {"name": "Translate to English", "template": "Translate the following sentence into English: \"{text}\"", "shortcut": ""},
        {"name": "Create Q&A", "template": "Based on this text, create a clear question and a concise answer for an Anki flashcard:\n\n{text}", "shortcut": ""}
    ]

    default_ai_sites = {
        "Gemini": "https://gemini.google.com/",
        "ChatGPT": "https://chat.openai.com/",
        "Perplexity": "https://www.perplexity.ai/",
        "Claude": "https://claude.ai/"
    }

    defaults = {
        "last_choice": "Gemini",
        "target_field": "Extra",
        "prompts": default_prompts,
        "ai_sites": default_ai_sites,
        "paste_direct_shortcut": "",
        "toggle_dock_shortcut": "Ctrl+Shift+X",
        "editor_settings": {"zoom_factor": 1.0, "splitRatio": "2:1", "location": "right", "visible": True},
        "reviewer_settings": {"zoom_factor": 1.0, "splitRatio": "2:1", "location": "right", "visible": True}
    }

    if config is None:
        config = defaults
        mw.addonManager.writeConfig(__name__, config)
        return config

    for key, value in defaults.items():
        config.setdefault(key, value)
    for settings_key in ["editor_settings", "reviewer_settings"]:
        if settings_key not in config: # Ensure the whole settings dict exists
            config[settings_key] = defaults[settings_key]
        else:
            for key, value in defaults[settings_key].items():
                config[settings_key].setdefault(key, value)
    if "prompts" in config:
        for p in config["prompts"]:
            p.setdefault("shortcut", "")
    if "ai_sites" not in config or not config["ai_sites"]: # Ensure ai_sites exists and is not empty
        config["ai_sites"] = default_ai_sites
    if "last_choice" not in config or config["last_choice"] not in config["ai_sites"]:
        config["last_choice"] = list(config["ai_sites"].keys())[0] if config["ai_sites"] else ""

    return config

def write_config(new_config):
    mw.addonManager.writeConfig(__name__, new_config)

RATIO_OPTIONS = ['4:1', '3:1', '2:1', '1:1', '1:2', '1:3', '1:4']

class AiSiteEditDialog(QDialog):
    def __init__(self, parent=None, site_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit AI Site" if site_data else "Add AI Site")
        self.site_data = site_data or {"name": "", "url": ""}
        layout = QFormLayout(self)
        self.name_edit = QLineEdit(self.site_data["name"])
        layout.addRow("Service Name:", self.name_edit)
        self.url_edit = QLineEdit(self.site_data["url"])
        layout.addRow("URL:", self.url_edit)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    def on_accept(self):
        name = self.name_edit.text().strip()
        url = self.url_edit.text().strip()
        if not name or not url:
            showWarning("Both name and URL cannot be empty.", parent=self)
            return
        if not url.startswith("http://") and not url.startswith("https://"):
            showWarning("URL must start with http:// or https://", parent=self)
            return
        self.site_data["name"] = name
        self.site_data["url"] = url
        self.accept()

    def get_site_data(self):
        return self.site_data

class PromptEditDialog(QDialog):
    def __init__(self, parent=None, prompt=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Prompt" if prompt else "Add Prompt")
        self.prompt_data = prompt or {"name": "", "template": "", "shortcut": ""}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Prompt Name (shown in menu):"))
        self.name_edit = QLineEdit(self.prompt_data["name"])
        layout.addWidget(self.name_edit)
        layout.addWidget(QLabel("Template (use {text} for selected text):"))
        self.template_edit = QTextEdit(self.prompt_data["template"])
        self.template_edit.setAcceptRichText(False); self.template_edit.setMinimumHeight(150)
        layout.addWidget(self.template_edit)
        form_layout = QFormLayout()
        self.shortcut_edit = QKeySequenceEdit(self)
        if self.prompt_data.get("shortcut"): self.shortcut_edit.setKeySequence(QKeySequence(self.prompt_data["shortcut"]))
        form_layout.addRow(QLabel("Shortcut:"), self.shortcut_edit)
        layout.addLayout(form_layout)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def on_accept(self):
        name = self.name_edit.text().strip(); template = self.template_edit.toPlainText().strip()
        shortcut = self.shortcut_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        if not name or not template: showWarning("Name and template cannot be empty.", parent=self); return
        if "{text}" not in template: showWarning("Template must contain {text}.", parent=self); return
        self.prompt_data["name"] = name; self.prompt_data["template"] = template; self.prompt_data["shortcut"] = shortcut
        self.accept()
    def get_prompt_data(self): return self.prompt_data

class PromptManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Dock Settings")
        self.setMinimumSize(600, 550)
        self.config = get_config()
        main_layout = QVBoxLayout(self)
        shortcuts_group = self._create_shortcuts_group()
        main_layout.addWidget(shortcuts_group)
        self.tabs = QTabWidget()
        prompts_widget = self._create_prompts_widget()
        ai_sites_widget = self._create_ai_sites_widget()
        self.tabs.addTab(prompts_widget, "Custom Prompts")
        self.tabs.addTab(ai_sites_widget, "AI Services")
        main_layout.addWidget(self.tabs)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)
        self.load_all()

    def _create_shortcuts_group(self):
        group = QGroupBox("Global Shortcuts")
        layout = QFormLayout(group)
        self.paste_direct_edit = QKeySequenceEdit(self)
        if self.config.get("paste_direct_shortcut"): self.paste_direct_edit.setKeySequence(QKeySequence(self.config["paste_direct_shortcut"]))
        layout.addRow("Paste from AI into Field:", self.paste_direct_edit)
        self.toggle_dock_edit = QKeySequenceEdit(self)
        if self.config.get("toggle_dock_shortcut"): self.toggle_dock_edit.setKeySequence(QKeySequence(self.config["toggle_dock_shortcut"]))
        layout.addRow("Show/Hide Dock:", self.toggle_dock_edit)
        return group

    def _create_prompts_widget(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        self.prompt_list_widget = QListWidget()
        self.prompt_list_widget.itemDoubleClicked.connect(self.edit_prompt)
        layout.addWidget(self.prompt_list_widget)
        btn_layout = QVBoxLayout()
        add_btn = QPushButton("Add..."); add_btn.clicked.connect(self.add_prompt); btn_layout.addWidget(add_btn)
        edit_btn = QPushButton("Edit..."); edit_btn.clicked.connect(self.edit_prompt); btn_layout.addWidget(edit_btn)
        remove_btn = QPushButton("Remove"); remove_btn.clicked.connect(self.remove_prompt); btn_layout.addWidget(remove_btn)
        btn_layout.addStretch(); layout.addLayout(btn_layout)
        return widget

    def _create_ai_sites_widget(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        self.ai_site_list_widget = QListWidget()
        self.ai_site_list_widget.itemDoubleClicked.connect(self.edit_ai_site)
        layout.addWidget(self.ai_site_list_widget)
        btn_layout = QVBoxLayout()
        add_btn = QPushButton("Add..."); add_btn.clicked.connect(self.add_ai_site); btn_layout.addWidget(add_btn)
        edit_btn = QPushButton("Edit..."); edit_btn.clicked.connect(self.edit_ai_site); btn_layout.addWidget(edit_btn)
        remove_btn = QPushButton("Remove"); remove_btn.clicked.connect(self.remove_ai_site); btn_layout.addWidget(remove_btn)
        btn_layout.addStretch(); layout.addLayout(btn_layout)
        return widget

    def load_all(self): self.load_prompts(); self.load_ai_sites()

    def load_prompts(self):
        self.prompt_list_widget.clear()
        for prompt in self.config["prompts"]:
            shortcut_str = f"  [{prompt.get('shortcut', '')}]" if prompt.get('shortcut') else ""
            item = QListWidgetItem(f"{prompt['name']}{shortcut_str}")
            item.setData(Qt.ItemDataRole.UserRole, prompt)
            self.prompt_list_widget.addItem(item)

    def add_prompt(self):
        dialog = PromptEditDialog(self)
        if dialog.exec(): self.config["prompts"].append(dialog.get_prompt_data()); self.load_prompts()

    def edit_prompt(self):
        item = self.prompt_list_widget.currentItem(); PDR = Qt.ItemDataRole.UserRole
        if not item: return
        prompt_data = item.data(PDR)
        dialog = PromptEditDialog(self, prompt=dict(prompt_data))
        if dialog.exec():
            updated = dialog.get_prompt_data()
            for i, p in enumerate(self.config["prompts"]):
                if p["name"] == prompt_data["name"] and p["template"] == prompt_data["template"]:
                    self.config["prompts"][i] = updated; break
            self.load_prompts()

    def remove_prompt(self):
        item = self.prompt_list_widget.currentItem(); PDR = Qt.ItemDataRole.UserRole
        if not item: return
        prompt_data = item.data(PDR)
        self.config["prompts"] = [p for p in self.config["prompts"] if p != prompt_data]
        self.load_prompts()

    def load_ai_sites(self):
        self.ai_site_list_widget.clear()
        for name, url in self.config.get("ai_sites", {}).items():
            item = QListWidgetItem(f"{name} ({url})")
            item.setData(Qt.ItemDataRole.UserRole, {"name": name, "url": url})
            self.ai_site_list_widget.addItem(item)

    def add_ai_site(self):
        dialog = AiSiteEditDialog(self)
        if dialog.exec():
            data = dialog.get_site_data()
            self.config["ai_sites"][data["name"]] = data["url"]
            self.load_ai_sites()

    def edit_ai_site(self):
        item = self.ai_site_list_widget.currentItem(); PDR = Qt.ItemDataRole.UserRole
        if not item: return
        site_data = item.data(PDR)
        dialog = AiSiteEditDialog(self, site_data=dict(site_data))
        if dialog.exec():
            updated = dialog.get_site_data(); original_name = site_data["name"]
            if original_name != updated["name"] and original_name in self.config["ai_sites"]:
                del self.config["ai_sites"][original_name]
            self.config["ai_sites"][updated["name"]] = updated["url"]
            self.load_ai_sites()

    def remove_ai_site(self):
        item = self.ai_site_list_widget.currentItem(); PDR = Qt.ItemDataRole.UserRole
        if not item: return
        site_data = item.data(PDR)
        if site_data["name"] in self.config["ai_sites"]:
            del self.config["ai_sites"][site_data["name"]]
            self.load_ai_sites()
            # Ensure last_choice is still valid
            if self.config["last_choice"] == site_data["name"]:
                self.config["last_choice"] = list(self.config["ai_sites"].keys())[0] if self.config["ai_sites"] else ""


    def accept(self):
        self.config['paste_direct_shortcut'] = self.paste_direct_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        self.config['toggle_dock_shortcut'] = self.toggle_dock_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        write_config(self.config)
        setup_shortcuts()
        update_open_docks_config() # Changed name
        tooltip("Settings saved.")
        super().accept()

def update_open_docks_config(): # Renamed from update_open_docks
    config = get_config() # Get fresh config
    ai_sites = config.get("ai_sites", {})
    last_choice = config.get("last_choice")

    # Ensure last_choice is valid, default if not
    if not last_choice or last_choice not in ai_sites:
        last_choice = list(ai_sites.keys())[0] if ai_sites else None
        if last_choice: # Update config if changed
            config["last_choice"] = last_choice
            write_config(config) # Save corrected last_choice

    open_dock_instances = []
    # Check editor windows
    for win in mw.app.topLevelWidgets():
        if hasattr(win, 'editor') and win.editor and hasattr(win.editor, 'ai_dock_site_combobox'):
            open_dock_instances.append(win.editor)
        # Potentially check other window types if dock can be in them

    # Check reviewer
    if mw.state == 'review' and hasattr(mw.reviewer, 'ai_dock_site_combobox'):
        open_dock_instances.append(mw.reviewer)

    for target_instance in open_dock_instances:
        combobox = target_instance.ai_dock_site_combobox
        current_text = combobox.currentText()
        combobox.blockSignals(True)
        combobox.clear()
        if ai_sites: # Only populate if there are sites
            combobox.addItems(list(ai_sites.keys()))
            if current_text in ai_sites:
                combobox.setCurrentText(current_text)
            elif last_choice in ai_sites : # last_choice should be valid now
                combobox.setCurrentText(last_choice)
            elif ai_sites: # Fallback to first if others fail
                 combobox.setCurrentIndex(0)
        combobox.blockSignals(False)

        # Also update the webview if the current/last_choice site was removed or URL changed
        # This is a bit more involved as it needs to check if the current URL is still valid for the selected name
        current_selected_site_name = combobox.currentText()
        if current_selected_site_name and hasattr(target_instance, 'ai_dock_webview'):
            new_url = ai_sites.get(current_selected_site_name)
            current_webview_url = target_instance.ai_dock_webview.url().toString()
            if new_url and new_url != current_webview_url:
                target_instance.ai_dock_webview.load(QUrl(new_url))
            elif not new_url and ai_sites: # Current site removed, load new last_choice
                 if last_choice and ai_sites.get(last_choice): # Should be valid
                      target_instance.ai_dock_webview.load(QUrl(ai_sites.get(last_choice)))


def on_text_pasted_from_ai(editor: Editor, selected_html: str, target_field_name: str):
    if not editor or not editor.note: return
    if not selected_html: tooltip("No content selected in the AI panel."); return
    field_names = [f['name'] for f in editor.note.model()['flds']]
    try: field_index = field_names.index(target_field_name)
    except ValueError: showWarning(f"Field '{target_field_name}' not found."); return
    escaped_html = json.dumps(selected_html)
    js = f"""
    const field = anki.editor.fields.get({field_index});
    if (field) {{
        field.focus();
        const wasEmpty = field.editingArea.innerHTML === "" || field.editingArea.innerHTML === "<br>";
        anki.editor.pasteHTML(wasEmpty ? {escaped_html} : ("<br>" + {escaped_html}));
        field.save();
    }}"""
    editor.web.eval(f"(() => {{{js}}})();")
    tooltip(f"Pasted content into '{target_field_name}'.")

def trigger_paste_from_ai_webview():
    editor = None
    # Iterate through top-level widgets to find the active editor
    for win in mw.app.topLevelWidgets():
        if hasattr(win, 'editor') and win.editor and win.isActiveWindow():
             if hasattr(win.editor, 'ai_dock_webview'):
                editor = win.editor
                break
    if not editor: # Fallback for reviewer or other contexts if needed
        if mw.state == 'review' and hasattr(mw.reviewer, 'ai_dock_webview'): # This case might not be fully supported by original logic
            # editor = mw.reviewer # This would be wrong, paste is editor-only
            tooltip("Pasting from AI is typically for editor windows.")
            return
        tooltip("Shortcut can only be used when an editor with AI Dock is active."); return

    field_name = editor.ai_dock_field_combobox.currentText()
    if not field_name: showWarning("Please select a target field."); return

    # Use the AI dock's webview
    editor.ai_dock_webview.page().runJavaScript(GET_SELECTION_HTML_JS,
        lambda html: on_text_pasted_from_ai(editor, html, field_name))


def on_copy_with_prompt_from_editor(prompt_template: str):
    editor = None
    for win in mw.app.topLevelWidgets():
        if hasattr(win, 'editor') and win.editor and win.isActiveWindow():
            editor = win.editor
            break
    if not editor: tooltip("Shortcut can only be used in an editor window."); return

    # This JS runs on Anki's main editor webview, not the AI dock's one.
    editor.web.page().runJavaScript("window.getSelection().toString();",
        lambda text: _on_copy_text_received(text, prompt_template))

def _on_copy_text_received(text: str, prompt_template:str):
    if not text: tooltip("No text selected in editor."); return
    QApplication.clipboard().setText(prompt_template.format(text=text))
    tooltip("Formatted prompt copied to clipboard!")


def toggle_ai_dock_visibility():
    target = None
    # Find active window that might have an editor
    active_win = QApplication.activeWindow()
    if hasattr(active_win, 'editor') and active_win.editor:
        target = active_win.editor
    elif mw.state == "review" and hasattr(mw, 'reviewer'): # Reviewer is a global mw attribute
        target = mw.reviewer
    else: # Check other top-level windows if they are AddCards, Browser, EditCurrent
        for win in mw.app.topLevelWidgets():
            if isinstance(win, (AddCards, Browser, EditCurrent)) and hasattr(win, 'editor') and win.editor:
                target = win.editor # Found an editor in a known window type
                break

    if target and hasattr(target, 'ai_dock_panel'):
        panel = target.ai_dock_panel
        is_visible = not panel.isVisible()
        panel.setVisible(is_visible)

        current_config = get_config()
        settings_key = "editor_settings" if isinstance(target, Editor) else "reviewer_settings"
        current_config[settings_key]["visible"] = is_visible
        write_config(current_config)
    else:
        tooltip(f"AI Dock not found or not applicable to current window/state.")


def setup_shortcuts():
    config = get_config()
    if hasattr(mw, '_ai_dock_shortcuts'):
        for action in mw._ai_dock_shortcuts: mw.removeAction(action)
    mw._ai_dock_shortcuts = []
    def register(key, fn_callback):
        if not key or key.isspace(): return
        try:
            q_key_seq = QKeySequence(key)
            if q_key_seq.isEmpty():
                # print(f"AI Dock: Invalid or empty shortcut key: {key}")
                return
        except Exception: # Catches potential errors from QKeySequence constructor
            # print(f"AI Dock: Could not parse shortcut key: {key}")
            return

        action = QAction(mw) # Parent to main window
        action.setShortcut(q_key_seq)
        action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut) # Global context
        action.triggered.connect(fn_callback)
        mw.addAction(action) # Add to main window's actions
        mw._ai_dock_shortcuts.append(action)

    register(config.get("paste_direct_shortcut"), trigger_paste_from_ai_webview)
    register(config.get("toggle_dock_shortcut"), toggle_ai_dock_visibility)

    for p_idx, p_val in enumerate(config.get("prompts", [])):
        if p_val.get("shortcut"):
            # Use a lambda that captures p_val['template'] by value
            register(p_val["shortcut"], lambda checked=False, tmpl=p_val['template']: on_copy_with_prompt_from_editor(tmpl))


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


def on_editor_context_menu(editor_webview, menu): # editor_webview is Anki's main editor field
    selected_text_in_editor = editor_webview.page().selectedText().strip()
    if not selected_text_in_editor: return

    prompts = get_config().get("prompts", [])
    if not prompts: return

    # Use an icon for the submenu
    ai_icon = QIcon.fromTheme("applications-internet", QIcon(os.path.join(os.path.dirname(__file__), "icons", "ai_icon.png"))) # Example path
    ai_submenu = menu.addMenu(ai_icon, "AI Dock Prompts") # Add submenu with icon

    for p_val in prompts:
        action_text = p_val["name"]
        # Optional: Add shortcut string to menu item if it exists
        # if p_val.get("shortcut"): action_text += f" ({p_val['shortcut']})"

        prompt_action = QAction(action_text, ai_submenu)
        prompt_action.triggered.connect(lambda checked=False, tmpl=p_val['template'], txt=selected_text_in_editor:
                                          _on_copy_text_received(txt, tmpl))
        ai_submenu.addAction(prompt_action)

# --- Anki Hooks & Final Setup ---
def on_editor_note_loaded(editor: Editor): # editor is the Anki Editor instance
    if not hasattr(editor, 'ai_dock_field_combobox') or not editor.note : return

    combobox = editor.ai_dock_field_combobox
    last_field_name = get_config().get("target_field")

    combobox.blockSignals(True)
    combobox.clear()
    field_names = [f['name'] for f in editor.note.model()['flds']]
    combobox.addItems(field_names)

    if last_field_name in field_names:
        combobox.setCurrentText(last_field_name)
    elif field_names: # Default to first field if last_field_name is not found or not set
        combobox.setCurrentIndex(0)
        # Update config if a valid field is selected by default
        # cfg = get_config(); cfg['target_field'] = combobox.currentText(); write_config(cfg)
    combobox.blockSignals(False)

def on_editor_did_init(editor: Editor): # editor is the Anki Editor instance
    # Check if the editor's parent window is one of the types we want to inject into
    if isinstance(editor.parentWindow, (AddCards, Browser, EditCurrent)):
        # Defer injection slightly to ensure the editor's UI is more likely to be set up
        QTimer.singleShot(150, lambda: inject_ai_dock(editor))
        # Defer field loading even more, as note might not be loaded when editor is first initialized
        QTimer.singleShot(250, lambda: on_editor_note_loaded(editor))


def on_reviewer_did_show(card: Card): # card is an Anki Card object
    if mw.reviewer and mw.reviewer.web: # Ensure reviewer and its webview exist
        # Defer injection for reviewer
        QTimer.singleShot(150, lambda: inject_ai_dock(mw.reviewer))

# Hook registrations
gui_hooks.editor_did_init.append(on_editor_did_init)
gui_hooks.editor_did_load_note.append(on_editor_note_loaded) # For when note changes in an existing editor
gui_hooks.reviewer_did_show_question.append(on_reviewer_did_show) # For when a card is shown in reviewer
gui_hooks.editor_will_show_context_menu.append(on_editor_context_menu)

# Initial setup of global shortcuts, deferred to ensure mw is fully initialized
QTimer.singleShot(1000, setup_shortcuts)
