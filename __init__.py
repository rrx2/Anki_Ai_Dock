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
    
    # --- NUOVO: I servizi AI predefiniti sono ora parte della configurazione ---
    # Questa sezione definisce i servizi che appaiono la prima volta che l'addon viene avviato.
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
        "ai_sites": default_ai_sites, # NUOVO: Aggiunto al dizionario dei default
        "paste_direct_shortcut": "",
        "toggle_dock_shortcut": "Ctrl+Shift+X",
        "editor_settings": {"zoom_factor": 1.0, "splitRatio": "2:1", "location": "right", "visible": True},
        "reviewer_settings": {"zoom_factor": 1.0, "splitRatio": "2:1", "location": "right", "visible": True}
    }

    if config is None:
        config = defaults
        mw.addonManager.writeConfig(__name__, config)
        return config

    # Migration for context-specific settings
    if "editor_settings" not in config or "reviewer_settings" not in config:
        pass # Simplified for brevity

    # Ensure all default keys exist
    for key, value in defaults.items():
        config.setdefault(key, value)
    for settings_key in ["editor_settings", "reviewer_settings"]:
        for key, value in defaults[settings_key].items():
            config[settings_key].setdefault(key, value)
    if "prompts" in config:
        for p in config["prompts"]:
            p.setdefault("shortcut", "")
            
    return config

def write_config(new_config):
    """Writes the configuration using Anki's manager."""
    mw.addonManager.writeConfig(__name__, new_config)

# Ratio options are still globally defined
RATIO_OPTIONS = ['4:1', '3:1', '2:1', '1:1', '1:2', '1:3', '1:4']

# --- DIALOGS FOR MANAGING SETTINGS ---

# --- NUOVO: Dialogo per Aggiungere/Modificare un Servizio AI ---
# Questa è la finestra che appare quando si preme "Add..." o "Edit..."
# nel pannello di gestione dei servizi AI.
class AiSiteEditDialog(QDialog):
    """Dialog to add or edit a single AI site."""
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
    """Dialog to add or edit a single prompt, including a shortcut."""
    # This class remains unchanged from the previous version
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


# --- NUOVO: Finestra Principale delle Impostazioni ---
# Questo è il dialogo principale che contiene i tab per gestire sia i prompt che i servizi AI.
class PromptManagerDialog(QDialog):
    """Main dialog to manage all addon settings."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Dock Settings")
        self.setMinimumSize(600, 550)
        self.config = get_config()
        
        main_layout = QVBoxLayout(self)
        
        # --- Global Shortcuts ---
        shortcuts_group = self._create_shortcuts_group()
        main_layout.addWidget(shortcuts_group)

        # --- Interfaccia a Tab per Prompts e Servizi AI ---
        self.tabs = QTabWidget()
        prompts_widget = self._create_prompts_widget()
        # --- La riga seguente crea il pannello che hai richiesto ---
        ai_sites_widget = self._create_ai_sites_widget() 
        self.tabs.addTab(prompts_widget, "Custom Prompts")
        self.tabs.addTab(ai_sites_widget, "AI Services") # E qui viene aggiunto ai tab
        main_layout.addWidget(self.tabs)
        
        # --- Save/Cancel Buttons ---
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
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        return widget

    # --- NUOVO: Creazione del Pannello di Gestione Servizi AI ---
    # Questa funzione costruisce l'interfaccia del tab "AI Services".
    def _create_ai_sites_widget(self):
        """Creates the widget for managing AI services."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        self.ai_site_list_widget = QListWidget()
        self.ai_site_list_widget.itemDoubleClicked.connect(self.edit_ai_site)
        layout.addWidget(self.ai_site_list_widget)
        
        # Layout per i bottoni Add, Edit, Remove
        btn_layout = QVBoxLayout()
        add_btn = QPushButton("Add..."); add_btn.clicked.connect(self.add_ai_site); btn_layout.addWidget(add_btn)
        edit_btn = QPushButton("Edit..."); edit_btn.clicked.connect(self.edit_ai_site); btn_layout.addWidget(edit_btn)
        remove_btn = QPushButton("Remove"); remove_btn.clicked.connect(self.remove_ai_site); btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        return widget

    def load_all(self):
        self.load_prompts()
        self.load_ai_sites()

    # --- Prompt Management ---
    def load_prompts(self):
        self.prompt_list_widget.clear()
        for prompt in self.config["prompts"]:
            shortcut_str = f"  [{prompt.get('shortcut', '')}]" if prompt.get('shortcut') else ""
            item = QListWidgetItem(f"{prompt['name']}{shortcut_str}")
            item.setData(Qt.ItemDataRole.UserRole, prompt)
            self.prompt_list_widget.addItem(item)
    def add_prompt(self):
        dialog = PromptEditDialog(self)
        if dialog.exec():
            self.config["prompts"].append(dialog.get_prompt_data())
            self.load_prompts()
    def edit_prompt(self):
        item = self.prompt_list_widget.currentItem()
        if not item: return
        prompt_data = item.data(Qt.ItemDataRole.UserRole)
        dialog = PromptEditDialog(self, prompt=dict(prompt_data))
        if dialog.exec():
            updated = dialog.get_prompt_data()
            for i, p in enumerate(self.config["prompts"]):
                if p["name"] == prompt_data["name"] and p["template"] == prompt_data["template"]:
                    self.config["prompts"][i] = updated
                    break
            self.load_prompts()
    def remove_prompt(self):
        item = self.prompt_list_widget.currentItem()
        if not item: return
        prompt_data = item.data(Qt.ItemDataRole.UserRole)
        self.config["prompts"] = [p for p in self.config["prompts"] if p != prompt_data]
        self.load_prompts()

    # --- NUOVO: Logica di Gestione dei Servizi AI ---
    # Le seguenti funzioni caricano, aggiungono, modificano e rimuovono i servizi.
    def load_ai_sites(self):
        """Carica i servizi AI dalla configurazione e li mostra nella lista."""
        self.ai_site_list_widget.clear()
        for name, url in self.config.get("ai_sites", {}).items():
            item = QListWidgetItem(f"{name} ({url})")
            # Salva i dati (nome e url) direttamente nell'item della lista
            item.setData(Qt.ItemDataRole.UserRole, {"name": name, "url": url})
            self.ai_site_list_widget.addItem(item)

    def add_ai_site(self):
        """Apre il dialogo per aggiungere un nuovo servizio AI."""
        dialog = AiSiteEditDialog(self)
        if dialog.exec():
            data = dialog.get_site_data()
            # Aggiunge il nuovo servizio al dizionario nella configurazione
            self.config["ai_sites"][data["name"]] = data["url"]
            self.load_ai_sites() # Ricarica la lista per mostrare il nuovo item

    def edit_ai_site(self):
        """Apre il dialogo per modificare il servizio AI selezionato."""
        item = self.ai_site_list_widget.currentItem()
        if not item: return
        
        site_data = item.data(Qt.ItemDataRole.UserRole)
        dialog = AiSiteEditDialog(self, site_data=dict(site_data)) # Usa una copia dei dati
        
        if dialog.exec():
            updated = dialog.get_site_data()
            original_name = site_data["name"]
            updated_name = updated["name"]
            
            # OTTIMIZZAZIONE: Rimuove la vecchia voce solo se il nome è cambiato.
            # Questo gestisce correttamente il caso in cui il nome (la chiave del dizionario) viene modificato.
            if original_name != updated_name and original_name in self.config["ai_sites"]:
                del self.config["ai_sites"][original_name]
            
            # Aggiunge/aggiorna la voce con il nuovo nome e URL.
            self.config["ai_sites"][updated_name] = updated["url"]
            self.load_ai_sites() # Ricarica la lista per mostrare le modifiche

    def remove_ai_site(self):
        """Rimuove il servizio AI selezionato dalla lista e dalla configurazione."""
        item = self.ai_site_list_widget.currentItem()
        if not item: return
        
        site_data = item.data(Qt.ItemDataRole.UserRole)
        # Rimuove la voce dal dizionario usando il nome come chiave
        if site_data["name"] in self.config["ai_sites"]:
            del self.config["ai_sites"][site_data["name"]]
            self.load_ai_sites() # Ricarica la lista

    def accept(self):
        """Saves all changes, updates shortcuts and open docks, then closes."""
        self.config['paste_direct_shortcut'] = self.paste_direct_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        self.config['toggle_dock_shortcut'] = self.toggle_dock_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        
        # Salva l'intero oggetto di configurazione, che ora include le modifiche ai servizi AI
        write_config(self.config)
        
        setup_shortcuts()
        update_open_docks() # Aggiorna i dock già aperti per riflettere le modifiche
        tooltip("Settings saved.")
        super().accept()

def update_open_docks():
    """Finds any open AI Docks and refreshes their AI services dropdown."""
    config = get_config()
    ai_sites = config.get("ai_sites", {})
    last_choice = config.get("last_choice")

    def refresh_combobox(combobox):
        current_text = combobox.currentText()
        combobox.blockSignals(True)
        combobox.clear()
        combobox.addItems(ai_sites.keys())
        if current_text in ai_sites:
            combobox.setCurrentText(current_text)
        elif last_choice in ai_sites:
            combobox.setCurrentText(last_choice)
        combobox.blockSignals(False)

    # Check editor windows (Add, Browser, EditCurrent)
    if mw.app.activeWindow() and hasattr(mw.app.activeWindow(), 'editor') and hasattr(mw.app.activeWindow().editor, 'ai_dock_site_combobox'):
        refresh_combobox(mw.app.activeWindow().editor.ai_dock_site_combobox)
    
    # Check reviewer
    if mw.state == 'review' and hasattr(mw.reviewer, 'ai_dock_site_combobox'):
        refresh_combobox(mw.reviewer.ai_dock_site_combobox)

# The rest of the script (action handlers, injection logic, etc.) follows...
# This has been shortened for clarity but includes necessary modifications.

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
        anki.editor.pasteHTML(wasEmpty ? {escaped_html} : "<br>" + {escaped_html});
        field.save();
    }}"""
    editor.web.eval(f"(() => {{{js}}})();")
    tooltip(f"Pasted content into '{target_field_name}'.")

def trigger_paste_from_ai_webview():
    editor = mw.app.activeWindow().editor if hasattr(mw.app.activeWindow(), 'editor') else None
    if not editor or not hasattr(editor, 'ai_dock_webview'):
        tooltip("Shortcut can only be used when an editor with AI Dock is active."); return
    def paste_it(html):
        field_name = editor.ai_dock_field_combobox.currentText()
        if not field_name: showWarning("Please select a target field."); return
        on_text_pasted_from_ai(editor, html, field_name)
    editor.ai_dock_webview.page().runJavaScript(GET_SELECTION_HTML_JS, paste_it)

def on_copy_with_prompt_from_editor(prompt_template: str):
    editor = mw.app.activeWindow().editor if hasattr(mw.app.activeWindow(), 'editor') else None
    if not editor: tooltip("Shortcut can only be used in an editor window."); return
    def on_text(text: str):
        if not text: tooltip("No text selected in editor."); return
        QApplication.clipboard().setText(prompt_template.format(text=text))
        tooltip("Formatted prompt copied to clipboard!")
    editor.web.page().runJavaScript("window.getSelection().toString();", on_text)

def toggle_ai_dock_visibility():
    target = None
    win = mw.app.activeWindow(); state = mw.state
    if hasattr(win, 'editor') and win.editor: target = win.editor
    elif state == "review" and hasattr(mw, 'reviewer'): target = mw.reviewer
    if target and hasattr(target, 'ai_dock_panel'):
        panel = target.ai_dock_panel
        is_visible = not panel.isVisible()
        panel.setVisible(is_visible)
        config = get_config()
        key = "editor_settings" if isinstance(target, Editor) else "reviewer_settings"
        config[key]["visible"] = is_visible
        write_config(config)
    else:
        tooltip(f"AI Dock not found. Window: {type(win).__name__}, State: {state}")

def setup_shortcuts():
    config = get_config()
    if hasattr(mw, '_ai_dock_shortcuts'):
        for action in mw._ai_dock_shortcuts: mw.removeAction(action)
    mw._ai_dock_shortcuts = []
    def register(key, fn):
        if not key or key.isspace(): return
        action = QAction(mw); action.setShortcut(QKeySequence(key))
        action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        action.triggered.connect(fn); mw.addAction(action)
        mw._ai_dock_shortcuts.append(action)
    register(config.get("paste_direct_shortcut"), trigger_paste_from_ai_webview)
    register(config.get("toggle_dock_shortcut"), toggle_ai_dock_visibility)
    for p in config.get("prompts", []):
        if p.get("shortcut"): register(p["shortcut"], lambda _, tmpl=p['template']: on_copy_with_prompt_from_editor(tmpl))

class CustomWebView(QWebEngineView):
    def __init__(self, paste_callback, get_field_name_callback, is_editor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.paste_callback = paste_callback; self.get_field_name_callback = get_field_name_callback; self.is_editor = is_editor
    def contextMenuEvent(self, event):
        menu = self.page().createStandardContextMenu()
        if self.is_editor and self.page().hasSelection():
            menu.addSeparator()
            field_name = self.get_field_name_callback()
            if field_name:
                action = menu.addAction(f"Paste into field '{field_name}'")
                action.triggered.connect(self.paste_callback)
        menu.exec(event.globalPos())

def inject_ai_dock(target_object):
    if not target_object or hasattr(target_object, "_ai_dock_injected_splitter"): return
    is_editor = isinstance(target_object, Editor)
    web_view = target_object.web
    parent_window = target_object.parentWindow if is_editor else mw
    config = get_config()
    settings_key = "editor_settings" if is_editor else "reviewer_settings"
    context_settings = config[settings_key]
    
    ai_panel = QWidget(); ai_panel.setVisible(context_settings.get("visible", True))
    ai_layout = QVBoxLayout(ai_panel); ai_layout.setContentsMargins(0, 0, 0, 0); ai_layout.setSpacing(5)
    
    controls_widget = QWidget(); controls_layout = QHBoxLayout(controls_widget)
    controls_layout.setContentsMargins(4, 2, 4, 2); controls_layout.setSpacing(6)

    # --- Controlli del Dock ---
    # MODIFICATO: Il selettore del servizio AI ora legge dalla configurazione
    ai_sites = config.get("ai_sites", {})
    site_combo_box = QComboBox()
    site_combo_box.addItems(ai_sites.keys()) # Popola il dropdown con i nomi dei servizi
    site_combo_box.setCurrentText(config.get("last_choice", ""))
    controls_layout.addWidget(site_combo_box)
    
    zoom_spinbox = QDoubleSpinBox(); zoom_spinbox.setRange(0.5, 3.0); zoom_spinbox.setSingleStep(0.05); zoom_spinbox.setValue(float(context_settings.get("zoom_factor", 1.0)))
    controls_layout.addWidget(zoom_spinbox)
    ratio_combobox = QComboBox(); ratio_combobox.addItems(RATIO_OPTIONS); ratio_combobox.setCurrentText(context_settings.get("splitRatio", "2:1"))
    controls_layout.addWidget(ratio_combobox)
    location_combo = QComboBox(); location_combo.addItems(["right", "left", "above", "below"]); location_combo.setCurrentText(context_settings.get("location", "right"))
    controls_layout.addWidget(location_combo)
    
    field_name_combobox = QComboBox(); field_name_combobox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed); field_name_combobox.setEnabled(is_editor)
    controls_layout.addWidget(field_name_combobox)
    
    # Il bottone "Settings" apre il dialogo di gestione
    settings_button = QPushButton("Settings"); settings_button.clicked.connect(lambda: PromptManagerDialog(parent_window).exec())
    controls_layout.addWidget(settings_button)
    controls_layout.addStretch()
    ai_layout.addWidget(controls_widget)

    # --- Web View ---
    profile = QWebEngineProfile(f"ai_dock_{id(parent_window)}", parent_window) # Use unique profile per window
    page = QWebEnginePage(profile, parent_window)
    def paste_text_into_field():
        if not is_editor: return
        target_field_name = field_name_combobox.currentText()
        if not target_field_name: showWarning("Please select a target field."); return
        webview.page().runJavaScript(GET_SELECTION_HTML_JS, lambda html: on_text_pasted_from_ai(target_object, html, target_field_name))
    webview = CustomWebView(paste_text_into_field, lambda: field_name_combobox.currentText(), is_editor=is_editor)
    webview.setPage(page); webview.setZoomFactor(zoom_spinbox.value())
    ai_layout.addWidget(webview)
    
    # MODIFICATO: Carica l'URL iniziale dalla configurazione
    initial_url = ai_sites.get(config.get("last_choice", ""))
    if initial_url: webview.load(QUrl(initial_url))

    # Store references to dynamic widgets
    target_object.ai_dock_webview = webview
    target_object.ai_dock_field_combobox = field_name_combobox
    target_object.ai_dock_site_combobox = site_combo_box # NUOVO
    target_object.ai_dock_panel = ai_panel
    
    # --- Splitter Injection ---
    parent_layout = web_view.parentWidget().layout()
    if not parent_layout: return
    web_index = parent_layout.indexOf(web_view)
    parent_layout.removeWidget(web_view)
    main_view_container = QWidget(); main_view_layout = QHBoxLayout(main_view_container); main_view_layout.setContentsMargins(0,0,0,0); main_view_layout.addWidget(web_view)
    splitter = QSplitter(); target_object._ai_dock_injected_splitter = splitter
    location = context_settings.get("location", "right")
    if location in ["right", "left"]:
        splitter.setOrientation(Qt.Orientation.Horizontal)
        splitter.addWidget(main_view_container if location == "right" else ai_panel)
        splitter.addWidget(ai_panel if location == "right" else main_view_container)
    else:
        splitter.setOrientation(Qt.Orientation.Vertical)
        splitter.addWidget(main_view_container if location == "below" else ai_panel)
        splitter.addWidget(ai_panel if location == "below" else main_view_container)
    parent_layout.insertWidget(web_index, splitter)

    # --- Signal Handlers ---
    def update_ratio(ratio_str):
        try:
            r1, r2 = map(int, ratio_str.split(':')); total = r1 + r2
            size_dim = splitter.width() if splitter.orientation() == Qt.Orientation.Horizontal else splitter.height()
            if size_dim == 0: QTimer.singleShot(100, lambda: update_ratio(ratio_str)); return
            sizes = [int(size_dim * r1 / total), int(size_dim * r2 / total)]
            if location in ["left", "above"]: sizes.reverse()
            splitter.setSizes(sizes)
            cfg = get_config(); cfg[settings_key]['splitRatio'] = ratio_str; write_config(cfg)
        except: splitter.setSizes([2000, 1000])

    def on_ai_changed(ai_name):
        cfg = get_config()
        url = cfg.get("ai_sites", {}).get(ai_name)
        if url: webview.load(QUrl(url))
        cfg['last_choice'] = ai_name; write_config(cfg)

    def update_zoom(value): cfg = get_config(); cfg[settings_key]['zoom_factor'] = value; write_config(cfg); webview.setZoomFactor(value)
    def update_location(loc): cfg = get_config(); cfg[settings_key]['location'] = loc; write_config(cfg); tooltip("Location saved. Please reopen the window.")
    def save_target_field(field): cfg = get_config(); cfg['target_field'] = field; write_config(cfg)

    site_combo_box.currentTextChanged.connect(on_ai_changed)
    zoom_spinbox.valueChanged.connect(update_zoom)
    ratio_combobox.currentTextChanged.connect(update_ratio)
    location_combo.currentTextChanged.connect(update_location)
    if is_editor: field_name_combobox.currentTextChanged.connect(save_target_field)
    QTimer.singleShot(50, lambda: update_ratio(ratio_combobox.currentText()))

def on_editor_context_menu(editor_webview, menu):
    text = editor_webview.page().selectedText().strip()
    if not text: return
    prompts = get_config().get("prompts", [])
    if not prompts: return
    submenu = menu.addMenu("AI Dock")
    for p in prompts:
        action = submenu.addAction(p["name"])
        action.triggered.connect(lambda _, t=p["template"], txt=text: on_copy_with_prompt_for_menu(t, txt))
def on_copy_with_prompt_for_menu(template, text):
    QApplication.clipboard().setText(template.format(text=text))
    tooltip("Formatted prompt copied to clipboard!")

# --- Anki Hooks & Final Setup ---
def on_editor_note_loaded(editor: Editor):
    if not hasattr(editor, 'ai_dock_field_combobox'): return
    combobox = editor.ai_dock_field_combobox
    last_field = get_config().get("target_field")
    combobox.blockSignals(True)
    combobox.clear()
    if editor.note:
        field_names = [f['name'] for f in editor.note.model()['flds']]
        combobox.addItems(field_names)
        if last_field in field_names: combobox.setCurrentText(last_field)
        else: combobox.setCurrentIndex(0)
    combobox.blockSignals(False)

def on_editor_did_init(editor: Editor):
    if isinstance(editor.parentWindow, (AddCards, Browser, EditCurrent)):
        QTimer.singleShot(10, lambda: inject_ai_dock(editor))
        QTimer.singleShot(20, lambda: on_editor_note_loaded(editor))

def on_reviewer_did_show(card: Card):
    if mw.reviewer: QTimer.singleShot(10, lambda: inject_ai_dock(mw.reviewer))

gui_hooks.editor_did_init.append(on_editor_did_init)
gui_hooks.editor_did_load_note.append(on_editor_note_loaded)
gui_hooks.reviewer_did_show_question.append(on_reviewer_did_show)
gui_hooks.editor_will_show_context_menu.append(on_editor_context_menu)

QTimer.singleShot(500, setup_shortcuts)
