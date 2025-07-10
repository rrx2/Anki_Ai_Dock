# -*- coding: utf-8 -*-

import copy

from aqt.qt import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QKeySequence,
    QKeySequenceEdit,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    Qt,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import showWarning, tooltip

from .config import get_config, write_config
from .logic import update_open_docks_config
from .shortcuts import setup_shortcuts


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
        if not url.startswith(("http://", "https://")):
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
        form = QFormLayout()
        self.name_edit = QLineEdit(self.prompt_data["name"])
        form.addRow("Prompt Name:", self.name_edit)
        self.template_edit = QTextEdit(self.prompt_data["template"])
        self.template_edit.setAcceptRichText(False)
        form.addRow("Template ({text}):", self.template_edit)
        self.shortcut_edit = QKeySequenceEdit(QKeySequence(self.prompt_data.get("shortcut", "")))
        form.addRow("Shortcut:", self.shortcut_edit)
        layout.addLayout(form)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def on_accept(self):
        name = self.name_edit.text().strip()
        template = self.template_edit.toPlainText().strip()
        shortcut = self.shortcut_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        if not name or not template:
            showWarning("Name and template cannot be empty.", parent=self); return
        if "{text}" not in template:
            showWarning("Template must contain {text}.", parent=self); return
        self.prompt_data = {"name": name, "template": template, "shortcut": shortcut}
        self.accept()
        
    def get_prompt_data(self): return self.prompt_data

class PromptManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Dock Settings")
        self.setMinimumSize(600, 550)
        
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_prompts_widget(), "Custom Prompts")
        self.tabs.addTab(self._create_ai_sites_widget(), "AI Services")
        self.tabs.addTab(self._create_shortcuts_widget(), "Global Shortcuts")
        main_layout.addWidget(self.tabs)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.on_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)
        self.load_all()

    def _create_shortcuts_widget(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        config = get_config() # Get live config
        self.paste_direct_edit = QKeySequenceEdit(QKeySequence(config.get("paste_direct_shortcut", "")))
        layout.addRow("Paste from AI into Field:", self.paste_direct_edit)
        self.toggle_dock_edit = QKeySequenceEdit(QKeySequence(config.get("toggle_dock_shortcut", "")))
        layout.addRow("Show/Hide Dock:", self.toggle_dock_edit)
        return widget

    def _create_list_management_widget(self, double_click_handler, add_handler, edit_handler, remove_handler):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        list_widget = QListWidget()
        list_widget.itemDoubleClicked.connect(double_click_handler)
        layout.addWidget(list_widget, 1)
        btn_layout = QVBoxLayout()
        add_btn = QPushButton("Add..."); add_btn.clicked.connect(add_handler); btn_layout.addWidget(add_btn)
        edit_btn = QPushButton("Edit..."); edit_btn.clicked.connect(edit_handler); btn_layout.addWidget(edit_btn)
        remove_btn = QPushButton("Remove"); remove_btn.clicked.connect(remove_handler); btn_layout.addWidget(remove_btn)
        btn_layout.addStretch(); layout.addLayout(btn_layout)
        return widget, list_widget

    def _create_prompts_widget(self):
        widget, self.prompt_list_widget = self._create_list_management_widget(
            self.edit_prompt, self.add_prompt, self.edit_prompt, self.remove_prompt)
        return widget

    def _create_ai_sites_widget(self):
        widget, self.ai_site_list_widget = self._create_list_management_widget(
            self.edit_ai_site, self.add_ai_site, self.edit_ai_site, self.remove_ai_site)
        return widget

    def load_all(self): self.load_prompts(); self.load_ai_sites()

    def load_prompts(self):
        self.prompt_list_widget.clear()
        for prompt in get_config().get("prompts", []):
            shortcut_str = f"  [{prompt.get('shortcut', '')}]" if prompt.get('shortcut') else ""
            item = QListWidgetItem(f'{prompt["name"]}{shortcut_str}')
            item.setData(Qt.ItemDataRole.UserRole, prompt)
            self.prompt_list_widget.addItem(item)

    def add_prompt(self):
        dialog = PromptEditDialog(self)
        if dialog.exec():
            get_config()["prompts"].append(dialog.get_prompt_data())
            self.load_prompts()

    def edit_prompt(self):
        item = self.prompt_list_widget.currentItem()
        if not item: return
        original_prompt = item.data(Qt.ItemDataRole.UserRole)
        # Use deepcopy here ONLY for the dialog, so "Cancel" works correctly
        dialog = PromptEditDialog(self, prompt=copy.deepcopy(original_prompt))
        if dialog.exec():
            updated_prompt = dialog.get_prompt_data()
            # Find and replace the original in the live config
            live_prompts = get_config()["prompts"]
            for i, p in enumerate(live_prompts):
                if p == original_prompt:
                    live_prompts[i] = updated_prompt
                    break
            self.load_prompts()

    def remove_prompt(self):
        item = self.prompt_list_widget.currentItem()
        if not item: return
        prompt_to_remove = item.data(Qt.ItemDataRole.UserRole)
        get_config()["prompts"].remove(prompt_to_remove)
        self.load_prompts()

    def load_ai_sites(self):
        self.ai_site_list_widget.clear()
        for name, url in get_config().get("ai_sites", {}).items():
            item = QListWidgetItem(f"{name} ({url})")
            item.setData(Qt.ItemDataRole.UserRole, {"name": name, "url": url})
            self.ai_site_list_widget.addItem(item)

    def add_ai_site(self):
        dialog = AiSiteEditDialog(self)
        if dialog.exec():
            data = dialog.get_site_data()
            get_config()["ai_sites"][data["name"]] = data["url"]
            self.load_ai_sites()

    def edit_ai_site(self):
        item = self.ai_site_list_widget.currentItem()
        if not item: return
        original_site = item.data(Qt.ItemDataRole.UserRole)
        dialog = AiSiteEditDialog(self, site_data=copy.deepcopy(original_site))
        if dialog.exec():
            updated = dialog.get_site_data()
            live_sites = get_config()["ai_sites"]
            if original_site["name"] != updated["name"]:
                del live_sites[original_site["name"]]
            live_sites[updated["name"]] = updated["url"]
            self.load_ai_sites()

    def remove_ai_site(self):
        item = self.ai_site_list_widget.currentItem()
        if not item: return
        site_data = item.data(Qt.ItemDataRole.UserRole)
        live_config = get_config()
        if site_data["name"] in live_config["ai_sites"]:
            del live_config["ai_sites"][site_data["name"]]
            if live_config["last_choice"] == site_data["name"]:
                live_config["last_choice"] = list(live_config["ai_sites"].keys())[0] if live_config["ai_sites"] else ""
            self.load_ai_sites()

    def on_accept(self):
        # Get the live config object
        config = get_config()
        
        # Update shortcut values from the dialog fields into the live config
        config['paste_direct_shortcut'] = self.paste_direct_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        config['toggle_dock_shortcut'] = self.toggle_dock_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        
        # Now, write the single, authoritative config object to disk
        write_config(config)
        
        # Re-apply shortcuts and update any open docks with the saved changes
        setup_shortcuts()
        update_open_docks_config()
        
        tooltip("Settings saved successfully.")
        super().accept()
