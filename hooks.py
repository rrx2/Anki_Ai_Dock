# -*- coding: utf-8 -*-

import os

from anki.cards import Card
from aqt import gui_hooks, mw
from aqt.addcards import AddCards
from aqt.browser import Browser
from aqt.editcurrent import EditCurrent
from aqt.qt import QAction, QIcon, QKeySequence, Qt
from PyQt6.QtCore import QTimer

from .config import get_config
from .dock import inject_ai_dock
from .logic import (
    _on_copy_text_received,
    on_copy_with_prompt_from_editor,
    toggle_ai_dock_visibility,
    trigger_paste_from_ai_webview,
)


def setup_shortcuts():
    """
    Imposta le scorciatoie da tastiera globali per le azioni dell'add-on.
    """
    config = get_config()
    if hasattr(mw, '_ai_dock_shortcuts'):
        for action in mw._ai_dock_shortcuts: mw.removeAction(action)
    mw._ai_dock_shortcuts = []
    def register(key, fn_callback):
        if not key or key.isspace(): return
        try:
            q_key_seq = QKeySequence(key)
            if q_key_seq.isEmpty():
                return
        except Exception:
            return

        action = QAction(mw)
        action.setShortcut(q_key_seq)
        action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        action.triggered.connect(fn_callback)
        mw.addAction(action)
        mw._ai_dock_shortcuts.append(action)

    register(config.get("paste_direct_shortcut"), trigger_paste_from_ai_webview)
    register(config.get("toggle_dock_shortcut"), toggle_ai_dock_visibility)

    for p_idx, p_val in enumerate(config.get("prompts", [])):
        if p_val.get("shortcut"):
            register(p_val["shortcut"], lambda checked=False, tmpl=p_val['template']: on_copy_with_prompt_from_editor(tmpl))

def on_editor_context_menu(editor_webview, menu):
    """
    Aggiunge un sottomenù "AI Dock Prompts" al menu contestuale dell'editor
    quando del testo è selezionato.
    """
    selected_text_in_editor = editor_webview.page().selectedText().strip()
    if not selected_text_in_editor: return

    prompts = get_config().get("prompts", [])
    if not prompts: return

    ai_icon = QIcon(os.path.join(os.path.dirname(__file__), "icons", "ai_icon.png"))
    ai_submenu = menu.addMenu(ai_icon, "AI Dock Prompts")

    for p_val in prompts:
        action_text = p_val["name"]
        prompt_action = QAction(action_text, ai_submenu)
        # --- CORREZIONE APPLICATA QUI ---
        # Il riferimento corretto all'oggetto editor è `editor_webview.editor`.
        prompt_action.triggered.connect(lambda checked=False, tmpl=p_val['template'], txt=selected_text_in_editor, editor_obj=editor_webview.editor:
                                          _on_copy_text_received(editor_obj, txt, tmpl))
        ai_submenu.addAction(prompt_action)

def on_editor_note_loaded(editor):
    """
    Aggiorna la combobox dei campi quando una nuova nota viene caricata nell'editor.
    """
    if not hasattr(editor, 'ai_dock_field_combobox') or not editor.note : return

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
    """
    Inietta il dock AI quando l'editor viene inizializzato.
    """
    if isinstance(editor.parentWindow, (AddCards, Browser, EditCurrent)):
        QTimer.singleShot(150, lambda: inject_ai_dock(editor))
        QTimer.singleShot(250, lambda: on_editor_note_loaded(editor))

def on_reviewer_did_show(card: Card):
    """
    Inietta il dock AI quando il revisore viene mostrato.
    """
    if mw.reviewer and mw.reviewer.web:
        QTimer.singleShot(150, lambda: inject_ai_dock(mw.reviewer))

def register_hooks():
    """
    Registra tutti gli hooks necessari per l'add-on.
    """
    gui_hooks.editor_did_init.append(on_editor_did_init)
    gui_hooks.editor_did_load_note.append(on_editor_note_loaded)
    gui_hooks.reviewer_did_show_question.append(on_reviewer_did_show)
    gui_hooks.editor_will_show_context_menu.append(on_editor_context_menu)
    QTimer.singleShot(1000, setup_shortcuts)
