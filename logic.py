# -*- coding: utf-8 -*-

import json
from aqt import mw, QApplication
from aqt.editor import Editor
from aqt.reviewer import Reviewer
from aqt.utils import showWarning, tooltip
from aqt.addcards import AddCards
from aqt.browser import Browser
from aqt.editcurrent import EditCurrent
from aqt.qt import QUrl

from .config import get_config, write_config

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
    """
    Aggiorna la configurazione e l'interfaccia di tutti i dock AI aperti.
    """
    config = get_config()
    ai_sites = config.get("ai_sites", {})
    last_choice = config.get("last_choice")

    if not last_choice or last_choice not in ai_sites:
        last_choice = list(ai_sites.keys())[0] if ai_sites else None
        if last_choice:
            config["last_choice"] = last_choice
            write_config(config)

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
            elif ai_sites:
                combobox.setCurrentIndex(0)
        combobox.blockSignals(False)

        current_selected_site_name = combobox.currentText()
        if current_selected_site_name and hasattr(target_instance, 'ai_dock_webview'):
            new_url = ai_sites.get(current_selected_site_name)
            current_webview_url = target_instance.ai_dock_webview.url().toString()
            if new_url and new_url != current_webview_url:
                target_instance.ai_dock_webview.load(QUrl(new_url))
            elif not new_url and ai_sites:
                if last_choice and ai_sites.get(last_choice):
                    target_instance.ai_dock_webview.load(QUrl(ai_sites.get(last_choice)))


def inject_prompt_into_ai_webview(target_object, prompt_text: str):
    """
    Inietta il testo del prompt nel webview del servizio AI.
    Contiene la logica specifica e aggiornata per Gemini.
    """
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
                if (!p) {{
                    targetEditor.innerHTML = '<p></p>';
                    p = targetEditor.querySelector('p');
                }}
                if(p) {{
                    p.textContent = prompt;
                }}
                const events = ['keydown', 'input', 'keyup', 'change'];
                events.forEach(eventType => {{
                    const event = new Event(eventType, {{
                        bubbles: true,
                        cancelable: true,
                    }});
                    targetEditor.dispatchEvent(event);
                }});
                success = true;
            }}

        }} else {{
            const selectors = [
                'div[aria-label="Scrivi il tuo prompt per Claude"]',
                '#prompt-textarea',
                'textarea',
            ];
            let targetElement = null;
            for (const selector of selectors) {{
                targetElement = document.querySelector(selector);
                if (targetElement) break;
            }}
            if (targetElement) {{
                if (targetElement.tagName === 'TEXTAREA') {{
                    targetElement.value = prompt;
                }} else {{
                    targetElement.innerHTML = prompt;
                }}
                targetElement.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
                targetElement.dispatchEvent(new Event('change', {{ bubbles: true, cancelable: true }}));
                targetElement.focus();
                success = true;
            }}
        }}
        
        return success;
    }})({json.dumps(prompt_text)}, {json.dumps(current_site_name)});
    """

    def on_injection_result(success):
        if success:
            tooltip("Prompt injected into AI service.")
        else:
            tooltip("Failed to inject prompt. The website's input field might have changed.")

    target_webview.page().runJavaScript(js_script, on_injection_result)

# --- FUNZIONE AGGIORNATA ---
def on_text_pasted_from_ai(editor: Editor, selected_html: str, target_field_name: str):
    """
    Pastes the given HTML into the specified field of the current note.
    This version correctly handles both new notes (in AddCards) and existing notes.
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
        showWarning(f"Field '{target_field_name}' not found in this note type.\nAvailable fields: {', '.join(field_names)}")
        return

    # Combine content
    current_content = note.fields[field_index]
    if current_content and not current_content.isspace():
        note.fields[field_index] += "<br>" + selected_html
    else:
        note.fields[field_index] = selected_html

    # Check if the note is new (its id will be 0).
    if not note.id:
        # For a new note, we can't 'flush' (save). We just reload the editor's state
        # to show the updated (but unsaved) content. The user saves by clicking "Add".
        editor.loadNote()
        tooltip("Pasted content. Click 'Add' to save the new card.")
    else:
        # For an existing note, we use a checkpoint and flush to save immediately.
        mw.checkpoint("Paste from AI")
        note.flush()
        editor.loadNote(focusTo=field_index) # Reload and focus on the edited field
        mw.progress.finish()
        tooltip(f"Pasted content into '{target_field_name}'.")

# --- FUNZIONE AGGIORNATA ---
def trigger_paste_from_ai_webview():
    """
    Attiva l'incollamento del contenuto selezionato nel webview del dock AI.
    """
    editor = None
    # Iterate through top-level widgets to find the active editor
    for win in mw.app.topLevelWidgets():
        if hasattr(win, 'editor') and win.editor and win.isActiveWindow():
            if hasattr(win.editor, 'ai_dock_webview'):
                editor = win.editor
                break

    if not editor:
        if mw.state == 'review' and hasattr(mw.reviewer, 'ai_dock_webview'):
            tooltip("Pasting from AI is typically for editor windows.")
            return
        tooltip("Shortcut can only be used when an editor with AI Dock is active."); return

    """Triggers pasting from the AI webview using the dropdown as the target."""
    target_object = None
    
    # First check for active editor windows
    for win in mw.app.topLevelWidgets():
        if hasattr(win, 'editor') and win.editor and win.isActiveWindow():
            if hasattr(win.editor, 'ai_dock_webview'):
                target_object = win.editor
                break
    
    # If no editor found, check if we're in review mode
    if not target_object and mw.state == "review" and hasattr(mw, 'reviewer') and mw.reviewer:
        if hasattr(mw.reviewer, 'ai_dock_webview'):
            target_object = mw.reviewer
    
    if not target_object:
        tooltip("Shortcut can only be used when an editor or reviewer with AI Dock is active.")
        return


    # For reviewer, we can't paste to fields, so just show the selected content from AI panel
    if target_object == mw.reviewer:
        print(f"DEBUG: Trying to get selection from AI webview in reviewer")
        target_object.ai_dock_webview.page().runJavaScript(GET_SELECTION_HTML_JS,
            lambda html: tooltip(f"AI Panel content: {html[:100]}...") if html else tooltip("No content selected in AI panel."))
        return


    # Use the AI dock's webview to get selected HTML
    editor.ai_dock_webview.page().runJavaScript(GET_SELECTION_HTML_JS,
        lambda html: on_text_pasted_from_ai(editor, html, field_name))

def on_copy_with_prompt_from_editor(prompt_template: str):
    """
    Copia il testo selezionato dall'editor e lo combina con un template di prompt.
    """
    editor = None

    # For editor, use the field dropdown to paste content from AI panel
    field_name = target_object.ai_dock_field_combobox.currentText()
    if not field_name:
        showWarning("Please select a target field in the top bar.")
        return

    target_object.ai_dock_webview.page().runJavaScript(GET_SELECTION_HTML_JS,
        lambda html: on_text_pasted_from_ai(target_object, html, field_name))

def on_copy_with_prompt_from_editor(prompt_template: str):
    """Copies selected text from the Anki editor or reviewer and injects it into the AI service."""
    target_object = None
    webview = None
    
    # Debug: mostra lo stato di Anki
    print(f"DEBUG: mw.state = {mw.state}")
    print(f"DEBUG: hasattr(mw, 'reviewer') = {hasattr(mw, 'reviewer')}")
    if hasattr(mw, 'reviewer'):
        print(f"DEBUG: mw.reviewer = {mw.reviewer}")
    
    # First check for active editor windows

    for win in mw.app.topLevelWidgets():
        if hasattr(win, 'editor') and win.editor and win.isActiveWindow():
            target_object = win.editor
            webview = target_object.web
            print(f"DEBUG: Found editor window: {target_object}")
            break
    
    # If no editor found, check if we're in review mode
    if not target_object and mw.state == "review" and hasattr(mw, 'reviewer') and mw.reviewer:
        target_object = mw.reviewer
        webview = mw.reviewer.web
        print(f"DEBUG: Found reviewer: {target_object}")
    
    if not target_object:
        print(f"DEBUG: No target object found")
        tooltip("Shortcut can only be used in an editor or review window.")
        return


    editor.web.page().runJavaScript("window.getSelection().toString();",
        lambda text: _on_copy_text_received(editor, text, prompt_template))

def _on_copy_text_received(editor, text: str, prompt_template:str):
    """
    Funzione callback che riceve il testo e inietta il prompt completo.
    """
    if not text:
        tooltip("No text selected in editor.")

    if not webview:
        print(f"DEBUG: No webview found")
        tooltip("Could not find web content to extract text from.")
        return

    print(f"DEBUG: Using webview: {webview}")
    print(f"DEBUG: About to get text selection from webview")
    webview.page().runJavaScript("window.getSelection().toString();",
        lambda text: _on_copy_text_received(target_object, text, prompt_template))

def _on_copy_text_received(target_object, text: str, prompt_template:str):
    """Callback that formats the prompt and injects it."""
    print(f"DEBUG: _on_copy_text_received called with text: '{text[:50]}...' (length: {len(text)})")
    if not text.strip():
        tooltip("No text selected.")

        return
    full_prompt = prompt_template.format(text=text)
    print(f"DEBUG: Formatted prompt: '{full_prompt[:50]}...'")
    inject_prompt_into_ai_webview(target_object, full_prompt)

def toggle_ai_dock_visibility():

    """
    Mostra o nasconde il pannello del dock AI nella finestra attiva.
    """

    """Shows or hides the AI dock panel in the currently active window."""

    target = None
    active_win = QApplication.activeWindow()
    if hasattr(active_win, 'editor') and active_win.editor:
        target = active_win.editor
    elif mw.state == "review" and hasattr(mw, 'reviewer'):
        target = mw.reviewer

    else:
        for win in mw.app.topLevelWidgets():
            if isinstance(win, (AddCards, Browser, EditCurrent)) and hasattr(win, 'editor') and win.editor:
                target = win.editor
                break


    

    if target and hasattr(target, 'ai_dock_panel'):
        panel = target.ai_dock_panel
        is_visible = not panel.isVisible()
        panel.setVisible(is_visible)
        
        # Save visibility state to config
        is_editor = isinstance(target, Editor)
        settings_key = "editor_settings" if is_editor else "reviewer_settings"
        get_config()[settings_key]["visible"] = is_visible
        write_config() # MODIFICA: Salvataggio immediato
    else:
        tooltip("AI Dock not found in the current window.")
