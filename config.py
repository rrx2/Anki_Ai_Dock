# -*- coding: utf-8 -*-

from aqt import mw

# This will hold the single, live configuration object for the entire addon.
_config = None

def get_config():
    """
    Gets the single, live configuration object.
    If it's not loaded yet, it loads it from disk and caches it.
    """
    global _config
    if _config is None:
        _config = _load_and_merge_defaults()
    return _config

def write_config():
    """Writes the single, live configuration object to disk."""
    global _config
    if _config is not None:
        mw.addonManager.writeConfig(__name__, _config)

def _load_and_merge_defaults():
    """Loads config from disk and merges it with defaults to ensure all keys exist."""
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
        return defaults

    # Merge defaults into the loaded config to prevent errors
    # if new config options are added in an update.
    for key, value in defaults.items():
        if key not in config:
            config[key] = value
        elif isinstance(value, dict):
            # Also ensure sub-dictionaries are complete
            for sub_key, sub_value in value.items():
                config[key].setdefault(sub_key, sub_value)

    return config

RATIO_OPTIONS = ['4:1', '3:1', '2:1', '1:1', '1:2', '1:3', '1:4']
