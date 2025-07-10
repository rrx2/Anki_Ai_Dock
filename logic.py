# -*- coding: utf-8 -*-

import json

from aqt import QApplication, mw
from aqt.editor import Editor
from aqt.utils import showWarning, tooltip

from .config import get_config

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

def update_open_docks_config():
    """Updates the site dropdown in all open AI docks."""
    config = get_config()
    ai_sites = config.get("ai_sites", {})
    last_choice = config.get("last_choice")

    open_dock_instances = []
    for win in mw.app.topLevelWidgets():
        if hasattr(win, 'editor') and win.editor and hasattr(win.editor, 'ai_dock_site_combobox'):
            open_dock_instances.append(win.editor)

    if mw.state == 'review' and hasattr(mw.reviewer, 'ai_dock_site_combobox'):
        open_dock_instances.append(mw.reviewer)

    for target_instance in open_dock_instances:
        combobox = target_instance.ai_dock_site_combobox
        current_text = combobox.currentText()
        combobox.blockSignals(True)
        combobox.clear()
        if ai_sites:
            combobox.addItems(list(ai_sites.keys()))
            if current_text in ai_sites:
                combobox.setCurrentText(current_text)
            elif last_choice in ai_sites:
                combobox.setCurrentText(last_choice)
        combobox.blockSignals(False)

def inject_prompt_into_ai_webview(target_object, prompt_text: str):
    """Injects the prompt text into the AI service's webview."""
    if not target_object or not hasattr(target_object, 'ai_dock_webview'):
        tooltip("Could not find an active AI Dock.")
        return

    target_webview = target_object.ai_dock_webview
    current_site_name = target_object.ai_dock_site_combobox.currentText()

    js_script = f"""
    (function(prompt, currentSiteName) {{
        let success = false;
        if (currentSiteName === "Gemini") {{
            const targetEditor = document.querySelector('div.ql-editor[contenteditable="true"]');
            if (targetEditor) {{
                targetEditor.focus();
                let p = targetEditor.querySelector('p');
                if (!p) {{ targetEditor.innerHTML = '<p></p>'; p = targetEditor.querySelector('p'); }}
                if(p) {{ p.textContent = prompt; }}
                const events = ['keydown', 'input', 'keyup', 'change'];
                events.forEach(e => targetEditor.dispatchEvent(new Event(e, {{ bubbles: true }})));
                success = true;
            }}
        }} else {{
            const selectors = ['#prompt-textarea', 'textarea'];
            let targetElement = null;
            for (const selector of selectors) {{
                targetElement = document.querySelector(selector);
                if (targetElement) break;
            }}
            if (targetElement) {{
                targetElement.value = prompt;
                targetElement.dispatchEvent(new Event('input', {{ bubbles: true }}));
                targetElement.focus();
                success = true;
            }}
        }}
        return success;
    }})({json.dumps(prompt_text)}, {json.dumps(current_site_name)});
    """
    target_webview.page().runJavaScript(js_script)

def on_text_pasted_from_ai(editor: Editor, selected_html: str, target_field_name: str):
    """
    Pastes the given HTML into the specified field of the current note.
    This version correctly handles both new notes and existing notes.
    """
    if not editor or not editor.note:
        showWarning("No note is currently loaded in the editor.")
        return

    if not selected_html:
        tooltip("No content selected in the AI panel.")
        return

    note = editor.note
    field_names = [f['name'] for f in note.model()['flds']]
    
    try:
        field_index = field_names.index(target_field_name)
    except ValueError:
        showWarning(f"Field '{target_field_name}' not found in this note type.")
        return

    current_content = note.fields[field_index]
    if current_content and not current_content.isspace():
        note.fields[field_index] += "<br>" + selected_html
    else:
        note.fields[field_index] = selected_html

    if not note.id:
        editor.loadNote()
    else:
        mw.checkpoint("Paste from AI")
        note.flush()
        editor.loadNote(focusTo=field_index)
        mw.progress.finish()
    tooltip(f"Pasted content into '{target_field_name}'.")

def trigger_paste_from_ai_webview():
    """Triggers pasting from the AI webview using the dropdown as the target."""
    editor = None
    for win in mw.app.topLevelWidgets():
        if hasattr(win, 'editor') and win.editor and win.isActiveWindow():
            if hasattr(win.editor, 'ai_dock_webview'):
                editor = win.editor
                break
    if not editor:
        tooltip("Shortcut can only be used when an editor with AI Dock is active.")
        return

    field_name = editor.ai_dock_field_combobox.currentText()
    if not field_name:
        showWarning("Please select a target field in the top bar.")
        return

    editor.ai_dock_webview.page().runJavaScript(GET_SELECTION_HTML_JS,
        lambda html: on_text_pasted_from_ai(editor, html, field_name))

def on_copy_with_prompt_from_editor(prompt_template: str):
    """Copies selected text from the Anki editor and injects it into the AI service."""
    editor = None
    for win in mw.app.topLevelWidgets():
        if hasattr(win, 'editor') and win.editor and win.isActiveWindow():
            editor = win.editor
            break
    if not editor:
        tooltip("Shortcut can only be used in an editor window.")
        return

    editor.web.page().runJavaScript("window.getSelection().toString();",
        lambda text: _on_copy_text_received(editor, text, prompt_template))

def _on_copy_text_received(editor, text: str, prompt_template:str):
    """Callback that formats the prompt and injects it."""
    if not text.strip():
        tooltip("No text selected in editor.")
        return
    full_prompt = prompt_template.format(text=text)
    inject_prompt_into_ai_webview(editor, full_prompt)

def toggle_ai_dock_visibility():
    """Shows or hides the AI dock panel in the currently active window."""
    target = None
    active_win = QApplication.activeWindow()
    if hasattr(active_win, 'editor') and active_win.editor:
        target = active_win.editor
    elif mw.state == "review" and hasattr(mw, 'reviewer'):
        target = mw.reviewer
    
    if target and hasattr(target, 'ai_dock_panel'):
        panel = target.ai_dock_panel
        is_visible = not panel.isVisible()
        panel.setVisible(is_visible)
        
        # Save visibility state to config
        is_editor = isinstance(target, Editor)
        settings_key = "editor_settings" if is_editor else "reviewer_settings"
        get_config()[settings_key]["visible"] = is_visible
    else:
        tooltip("AI Dock not found in the current window.")
