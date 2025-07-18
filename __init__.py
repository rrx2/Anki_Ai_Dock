# -*- coding: utf-8 -*-

"""
Anki AI Dock Add-on

Main entry point for the add-on. This file handles the initialization
and hooks into Anki to load the dock functionality.
"""

# Import the hook registration function from our new module
print("DEBUG: AI Dock addon is loading...")
from .hooks import register_hooks

# Call the function to set up all the Anki hooks and shortcuts.
# This one function call is all that should be needed to start the add-on.
print("DEBUG: About to register hooks...")
register_hooks()
print("DEBUG: Hooks registered!")