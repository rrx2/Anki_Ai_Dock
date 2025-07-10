# -*- coding: utf-8 -*-

from aqt import mw
from aqt.qt import QAction, QKeySequence, Qt

from .config import get_config
from .logic import (
    on_copy_with_prompt_from_editor,
    toggle_ai_dock_visibility,
    trigger_paste_from_ai_webview,
)


def setup_shortcuts():
    """
    Sets up or re-applies global keyboard shortcuts for the add-on.
    It clears old shortcuts before creating new ones.
    """
    config = get_config()
    
    # Clear any previously registered shortcuts to prevent duplicates
    if hasattr(mw, '_ai_dock_shortcuts'):
        for action in mw._ai_dock_shortcuts:
            mw.removeAction(action)
    mw._ai_dock_shortcuts = []

    def register(key, fn_callback):
        if not key or key.isspace():
            return
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

    # Register main shortcuts
    register(config.get("paste_direct_shortcut"), trigger_paste_from_ai_webview)
    register(config.get("toggle_dock_shortcut"), toggle_ai_dock_visibility)

    # Register shortcuts for each custom prompt
    for p_val in config.get("prompts", []):
        if p_val.get("shortcut"):
            # Use a lambda that captures p_val['template'] by value
            register(p_val["shortcut"], lambda checked=False, tmpl=p_val['template']: on_copy_with_prompt_from_editor(tmpl))
