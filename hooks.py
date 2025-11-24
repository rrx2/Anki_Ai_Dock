# -*- coding: utf-8 -*-

import os

from anki.cards import Card
from aqt import gui_hooks, mw
from aqt.addcards import AddCards
from aqt.browser import Browser
from aqt.editcurrent import EditCurrent
from aqt.qt import QAction, QIcon
from PyQt6.QtCore import QTimer

from .config import get_config, write_config
from .dock import inject_ai_dock
from .logic import _on_copy_text_received
from .shortcuts import setup_shortcuts


def on_editor_context_menu(editor_webview, menu):
    """Adds the 'AI Dock Prompts' context menu to the editor."""
    selected_text_in_editor = editor_webview.page().selectedText().strip()
    if not selected_text_in_editor:
        return

    prompts = get_config().get("prompts", [])
    if not prompts:
        return

    ai_icon = QIcon(os.path.join(os.path.dirname(__file__), "icons", "ai_icon.png"))
    ai_submenu = menu.addMenu(ai_icon, "AI Dock Prompts")

    # --- FIX: loop was incorrectly outside the function ---
    for p_val in prompts:
        action_text = p_val["name"]
        prompt_action = QAction(action_text, ai_submenu)
        prompt_action.triggered.connect(
            lambda checked=False,
                   tmpl=p_val['template'],
                   txt=selected_text_in_editor,
                   editor_obj=editor_webview.editor:
                   _on_copy_text_received(editor_obj, txt, tmpl)
        )
        ai_submenu.addAction(prompt_action)


def on_reviewer_context_menu(reviewer_webview, menu):
    """Adds the 'AI Dock Prompts' context menu to the reviewer."""
    selected_text_in_reviewer = reviewer_webview.page().selectedText().strip()
    if not selected_text_in_reviewer:
        return

    prompts = get_config().get("prompts", [])
    if not prompts:
        return

    ai_icon = QIcon(os.path.join(os.path.dirname(__file__), "icons", "ai_icon.png"))
    ai_submenu = menu.addMenu(ai_icon, "AI Dock Prompts")

    for p_val in prompts:
        action_text = p_val["name"]
        prompt_action = QAction(action_text, ai_submenu)
        prompt_action.triggered.connect(
            lambda checked=False,
                   tmpl=p_val['template'],
                   txt=selected_text_in_reviewer,
                   reviewer_obj=mw.reviewer:
                   _on_copy_text_received(reviewer_obj, txt, tmpl)
        )
        ai_submenu.addAction(prompt_action)


def on_webview_context_menu(webview, menu):
    """Universal context menu handler for both editor and reviewer."""
    # Debug info
    print(f"DEBUG: on_webview_context_menu called with webview: {webview}")
    print(f"DEBUG: mw.state = {mw.state}")

    # Check reviewer
    if (
        mw.state == "review"
        and hasattr(mw, 'reviewer')
        and mw.reviewer
        and mw.reviewer.web == webview
    ):
        print(f"DEBUG: Calling on_reviewer_context_menu")
        on_reviewer_context_menu(webview, menu)
    else:
        print(f"DEBUG: Not calling reviewer context menu")


def on_editor_note_loaded(editor):
    """Updates the target field dropdown when a note is loaded."""
    if not hasattr(editor, 'ai_dock_field_combobox') or not editor.note:
        return

    combobox = editor.ai_dock_field_combobox
    last_field_name = get_config().get("target_field")

    combobox.blockSignals(True)
    combobox.clear()

    field_names = [f['name'] for f in editor.note.model()['flds']]
    combobox.addItems(field_names)

    if last_field_name in field_names:
        combobox.setCurrentText(last_field_name)
    elif field_names:
        combobox.setCurrentIndex(0)

    combobox.blockSignals(False)


def on_editor_did_init(editor):
    """Injects the dock when an editor window is created."""
    if isinstance(editor.parentWindow, (AddCards, Browser, EditCurrent)):
        QTimer.singleShot(150, lambda: inject_ai_dock(editor))
        QTimer.singleShot(250, lambda: on_editor_note_loaded(editor))


def on_reviewer_did_show(card: Card):
    """Injects the dock when the reviewer is shown."""
    if mw.reviewer and mw.reviewer.web:
        QTimer.singleShot(150, lambda: inject_ai_dock(mw.reviewer))


def on_profile_will_close():
    """Saves config on exit."""
    write_config()


def register_hooks():
    """Registers all necessary hooks for the add-on."""
    print("DEBUG: register_hooks() called")

    gui_hooks.editor_did_init.append(on_editor_did_init)
    gui_hooks.editor_did_load_note.append(on_editor_note_loaded)
    gui_hooks.reviewer_did_show_question.append(on_reviewer_did_show)
    gui_hooks.editor_will_show_context_menu.append(on_editor_context_menu)

    if hasattr(gui_hooks, "reviewer_will_show_context_menu"):
        gui_hooks.reviewer_will_show_context_menu.append(on_reviewer_context_menu)

    gui_hooks.webview_will_show_context_menu.append(on_webview_context_menu)

    gui_hooks.profile_will_close.append(on_profile_will_close)

    QTimer.singleShot(1000, setup_shortcuts)
