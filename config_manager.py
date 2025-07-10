# -*- coding: utf-8 -*-

import json
import os
import time
from datetime import datetime
from aqt import mw
from aqt.utils import showWarning, tooltip

class ConfigManager:
    """
    Sistema di configurazione completamente personalizzato per AI Dock.
    Bypassa completamente il sistema di Anki per garantire la persistenza.
    """
    
    def __init__(self):
        self._config = None
        self._config_file = None
        self._backup_file = None
        
    @property
    def config_file(self):
        """Lazy initialization of config file path."""
        if self._config_file is None:
            if mw and mw.pm:
                self._config_file = os.path.join(mw.pm.profileFolder(), "ai_dock_settings.json")
            else:
                # Fallback se il profilo non è ancora disponibile
                import tempfile
                self._config_file = os.path.join(tempfile.gettempdir(), "ai_dock_settings_fallback.json")
        return self._config_file
        
    @property  
    def backup_file(self):
        """Lazy initialization of backup file path."""
        if self._backup_file is None:
            if mw and mw.pm:
                self._backup_file = os.path.join(mw.pm.profileFolder(), "ai_dock_settings_backup.json")
            else:
                # Fallback se il profilo non è ancora disponibile
                import tempfile
                self._backup_file = os.path.join(tempfile.gettempdir(), "ai_dock_settings_backup_fallback.json")
        return self._backup_file
        
    def get_defaults(self):
        """Restituisce la configurazione di default."""
        return {
            "version": "1.0",
            "last_saved": datetime.now().isoformat(),
            "settings": {
                "last_choice": "Gemini",
                "zoom_factor": 1.0,
                "splitRatio": "2:1",
                "location": "right",
                "target_field": "Extra",
                "prompts": [
                    {
                        "name": "Explain Simply",
                        "template": "Explain this concept in simple terms for a beginner: {text}",
                        "shortcut": ""
                    },
                    {
                        "name": "Translate to English",
                        "template": "Translate the following sentence into English: \"{text}\"",
                        "shortcut": ""
                    },
                    {
                        "name": "Create Q&A",
                        "template": "Based on this text, create a clear question and a concise answer for an Anki flashcard:\n\n{text}",
                        "shortcut": ""
                    }
                ],
                "ai_sites": {
                    "Gemini": "https://gemini.google.com/",
                    "ChatGPT": "https://chat.openai.com/",
                    "Perplexity": "https://www.perplexity.ai/",
                    "Claude": "https://claude.ai/"
                },
                "paste_direct_shortcut": "",
                "toggle_dock_shortcut": "Ctrl+Shift+X",
                "editor_settings": {
                    "zoom_factor": 1.0, 
                    "splitRatio": "2:1", 
                    "location": "right", 
                    "visible": True
                },
                "reviewer_settings": {
                    "zoom_factor": 1.0, 
                    "splitRatio": "2:1", 
                    "location": "right", 
                    "visible": True
                }
            }
        }
    
    def load_config(self):
        """Carica la configurazione dal file JSON personalizzato."""
        if self._config is not None:
            return self._config
            
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                    
                # Validazione e migrazione se necessario
                if not self._validate_config(self._config):
                    self._config = self._migrate_config(self._config)
            else:
                # Primo avvio - crea file di default
                self._config = self.get_defaults()
                self.save_config()
                
        except Exception as e:
            showWarning(f"Errore nel caricamento della configurazione AI Dock: {e}\nVerrà utilizzata la configurazione di default.")
            self._config = self.get_defaults()
            
        return self._config
    
    def save_config(self):
        """Salva la configurazione nel file JSON personalizzato."""
        if self._config is None:
            return False
            
        try:
            # Crea backup del file esistente
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    backup_data = f.read()
                with open(self.backup_file, 'w', encoding='utf-8') as f:
                    f.write(backup_data)
            
            # Aggiorna timestamp
            self._config["last_saved"] = datetime.now().isoformat()
            
            # Salva la nuova configurazione
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
                
            return True
            
        except Exception as e:
            showWarning(f"Errore nel salvataggio della configurazione AI Dock: {e}")
            return False
    
    def get_setting(self, key, default=None):
        """Ottiene un'impostazione specifica."""
        config = self.load_config()
        return config.get("settings", {}).get(key, default)
    
    def set_setting(self, key, value):
        """Imposta un'impostazione specifica e salva immediatamente."""
        config = self.load_config()
        config["settings"][key] = value
        return self.save_config()
    
    def get_all_settings(self):
        """Ottiene tutte le impostazioni."""
        config = self.load_config()
        return config.get("settings", {})
    
    def update_settings(self, new_settings):
        """Aggiorna multiple impostazioni e salva."""
        config = self.load_config()
        config["settings"].update(new_settings)
        return self.save_config()
    
    def reset_config(self):
        """Resetta la configurazione ai valori di default."""
        self._config = self.get_defaults()
        success = self.save_config()
        if success:
            tooltip("Configurazione AI Dock resettata ai valori di default.")
        return success
    
    def _validate_config(self, config):
        """Valida la struttura della configurazione."""
        if not isinstance(config, dict):
            return False
        if "settings" not in config:
            return False
        if "version" not in config:
            return False
        return True
    
    def _migrate_config(self, config):
        """Migra configurazioni vecchie al nuovo formato."""
        defaults = self.get_defaults()
        
        # Se è una configurazione del vecchio sistema, migra
        if "settings" not in config:
            # Il config è nel vecchio formato (direttamente i settings)
            migrated = defaults.copy()
            migrated["settings"].update(config)
            return migrated
        
        # Altrimenti, assicurati che tutti i campi necessari siano presenti
        for key, value in defaults["settings"].items():
            if key not in config["settings"]:
                config["settings"][key] = value
                
        return config

# Istanza globale del manager
config_manager = ConfigManager()

# Funzioni di compatibilità per rimpiazzare quelle vecchie
def get_config():
    """Funzione di compatibilità - restituisce le impostazioni."""
    return config_manager.get_all_settings()

def write_config(new_config=None):
    """Funzione di compatibilità - salva le nuove impostazioni."""
    if new_config is not None:
        return config_manager.update_settings(new_config)
    else:
        # Se non viene passato new_config, salva la configurazione corrente
        return config_manager.save_config()