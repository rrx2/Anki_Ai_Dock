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

# Assicurati che questi import funzionino nel tuo ambiente Anki
# Se il file config.py è nella stessa cartella, questo import è corretto.
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

    # --- MODIFICA CHIAVE PER GEMINI (v2) ---
    # Questo snippet simula in modo più completo l'input dell'utente.
    js_script = f"""
    (function(prompt, currentSiteName) {{
        let success = false;

        if (currentSiteName === "Gemini") {{
            const targetEditor = document.querySelector('div.ql-editor[contenteditable="true"]');
            
            if (targetEditor) {{
                // 1. Mette il focus sull'editor, come farebbe un utente cliccandoci.
                targetEditor.focus();

                // 2. Inserisce il testo nel primo paragrafo o ne crea uno nuovo.
                let p = targetEditor.querySelector('p');
                if (!p) {{
                    targetEditor.innerHTML = '<p></p>';
                    p = targetEditor.querySelector('p');
                }}
                if(p) {{
                    p.textContent = prompt;
                }}

                // 3. Simula una sequenza di eventi per far credere al sito
                //    che l'input sia stato manuale. Questo è il passaggio cruciale.
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
            // Logica originale funzionante per ChatGPT, Claude, etc.
            const selectors = [
                'div[aria-label="Scrivi il tuo prompt per Claude"]', // Claude
                '#prompt-textarea',                                   // ChatGPT
                'textarea',                                           // Fallback generico
            ];
            let targetElement = null;
            for (const selector of selectors) {{
                targetElement = document.querySelector(selector);
                if (targetElement) break;
            }}

            if (targetElement) {{
                if (targetElement.tagName === 'TEXTAREA') {{
                    targetElement.value = prompt;
                }} else {{ // Assume un div contenteditable
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
    # --- FINE MODIFICA ---

    def on_injection_result(success):
        if success:
            tooltip("Prompt injected into AI service.")
        else:
            tooltip("Failed to inject prompt. The website's input field might have changed.")

    target_webview.page().runJavaScript(js_script, on_injection_result)

def on_text_pasted_from_ai(editor: Editor, selected_html: str, target_field_name: str):
    if not editor or not editor.note: return
    if not selected_html: tooltip("No content selected in the AI panel."); return
    field_names = [f['name'] for f in editor.note.model()['flds']]
    try: field_index = field_names.index(target_field_name)
    except ValueError: showWarning(f"Field '{{target_field_name}}' not found."); return
    escaped_html = json.dumps(selected_html)
    js = f"""
    const field = anki.editor.fields.get({field_index});
    if (field) {{
        field.focus();
        const wasEmpty = field.editingArea.innerHTML === "" || field.editingArea.innerHTML === "<br>";
        anki.editor.pasteHTML(wasEmpty ? {escaped_html} : ("<br>" + {escaped_html}));
        field.save();
    }}"""
    editor.web.eval(f"(() => {{{{{js}}}}})();")
    tooltip(f"Pasted content into '{{target_field_name}}'.")

def trigger_paste_from_ai_webview():
    editor = None
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

    field_name = editor.ai_dock_field_combobox.currentText()
    if not field_name: showWarning("Please select a target field."); return

    editor.ai_dock_webview.page().runJavaScript(GET_SELECTION_HTML_JS,
        lambda html: on_text_pasted_from_ai(editor, html, field_name))

def on_copy_with_prompt_from_editor(prompt_template: str):
    editor = None
    for win in mw.app.topLevelWidgets():
        if hasattr(win, 'editor') and win.editor and win.isActiveWindow():
            editor = win.editor
            break
    if not editor: tooltip("Shortcut can only be used in an editor window."); return

    editor.web.page().runJavaScript("window.getSelection().toString();",
        lambda text: _on_copy_text_received(editor, text, prompt_template))

def _on_copy_text_received(editor, text: str, prompt_template:str):
    if not text:
        tooltip("No text selected in editor.")
        return
    full_prompt = prompt_template.format(text=text)
    inject_prompt_into_ai_webview(editor, full_prompt)


def toggle_ai_dock_visibility():
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

        current_config = get_config()
        settings_key = "editor_settings" if isinstance(target, Editor) else "reviewer_settings"
        current_config[settings_key]["visible"] = is_visible
        write_config(current_config)
    else:
        tooltip(f"AI Dock not found or not applicable to current window/state.")
