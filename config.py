# -*- coding: utf-8 -*-

from aqt import mw

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
