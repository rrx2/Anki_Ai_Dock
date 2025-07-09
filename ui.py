# -*- coding: utf-8 -*-

from aqt.qt import (
    QWidget, QVBoxLayout, QComboBox, QHBoxLayout, QLabel, QLineEdit, QAction, 
    QKeySequence, QPushButton, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QTextEdit, QKeySequenceEdit, QGroupBox, QFormLayout, QTabWidget, Qt
)
from aqt.utils import showWarning, tooltip

# Import from our new modules
from .config import get_config, write_config

from .logic import update_open_docks_config # And this one too

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
            item = QListWidgetItem(f'{prompt["name"]}{shortcut_str}')
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
        from .hooks import setup_shortcuts # Moved import here to fix circular dependency
        self.config['paste_direct_shortcut'] = self.paste_direct_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        self.config['toggle_dock_shortcut'] = self.toggle_dock_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        write_config(self.config)
        setup_shortcuts()
        update_open_docks_config() # Changed name
        tooltip("Settings saved.")
        super().accept()