# -*- coding: utf-8 -*-

import copy
from aqt import mw

# This will hold the single, live configuration object for the entire addon.
_config = None
_addon_package = None

def _get_addon_package():
    """Gets the addon package name, caching it for efficiency."""
    global _addon_package
    if _addon_package is None:
        # This is the robust way to get the current add-on's package name
        # from within any of its modules, which is needed for config management.
        _addon_package = mw.addonManager.addonFromModule(__name__)
    return _addon_package

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
        # Use the correct add-on package name to write the config.
        mw.addonManager.writeConfig(_get_addon_package(), _config)

def _deep_merge(source, destination):
    """
    Recursively merges the `source` dict into the `destination` dict.
    It fills in missing keys in `destination` from `source` at any level
    without overwriting existing values in `destination`.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # Get the node in the destination or create an empty one
            node = destination.setdefault(key, {})
            _deep_merge(value, node)
        else:
            # Set the value in the destination only if the key doesn't exist
            destination.setdefault(key, value)
    return destination

def _load_and_merge_defaults():
    """Loads config from disk and merges it with defaults to ensure all keys exist."""
    # Load the user's saved configuration. Returns {} if not found.
    loaded_config = mw.addonManager.getConfig(_get_addon_package()) or {}

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
    # Define the complete default structure
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

    # We need to ensure all keys from the latest default config are present
    # in the loaded config, without overwriting any user-saved values.
    # The safest way is to merge the defaults INTO the loaded config.
    
    # We work on a copy to avoid issues with modifying a dictionary while iterating.
    config_copy = copy.deepcopy(loaded_config)

    # Merge the defaults into our copy of the loaded config.
    # This will add any missing keys/sub-keys from `defaults` to `config_copy`
    # without overwriting any existing user values.
    merged_config = _deep_merge(defaults, config_copy)

    return merged_config

RATIO_OPTIONS = ['4:1', '3:1', '2:1', '1:1', '1:2', '1:3', '1:4']
