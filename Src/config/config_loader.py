# Src/Config/config_loader.py
import json
import os
import logging
from pathlib import Path

DEFAULT_CONFIG = {
    "database": {
        "engine": "sqlserver",
        "server": "DESKTOP-QGCQ59D\\SQLEXPRESS",
        "database": "PuntoventaDB",
        "username": "Elgomez05",
        "password": "123456"
    },
    "printer": {
        "use_default": True,
        "name": "COL-POS",
        "paper_width": 58,
        "cut_paper": True,
        "open_cash_drawer": False
    },
    "scanner": {
        "enabled": True,
        "mode": "keyboard"
    },
    "invoicing": {
        "data_path": "C:/ProgramData/PuntoVenta",
        "save_billing": "C:/ProgramData/PuntoVenta/invoices",
        "currency": "COP",
        "currency_symbol": "$",
        "adjustment": 50,
        "enterprise": "PEPE INTELIGENT SYSTEM S.A.S",
        "nit": "1006029934-0",
        "address": "Barrio Floresta alta/-Planadas Tolima",
        "cellphone": "(57) 314-5052022",
        "footer": "Gracias por su compra\n"
    },
    "app": {
        "environment": "production",
        "debug": True
    },
    "turno": {
        "Status": "ABIERTO",
        "user": "POS",
        "info_only": True
    }
}

class ConfigManager:
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Carga la configuración desde settings.json o crea uno por defecto"""
        config_path = "C:/ProgramData/PuntoVenta/Setting/settings.json"
        
        try:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logging.info(f"Configuración cargada desde {config_path}")
            else:
                self._config = DEFAULT_CONFIG.copy()
                self._save_config()
                logging.info(f"Archivo de configuración creado en {config_path}")
                
        except Exception as e:
            logging.error(f"Error cargando configuración: {e}")
            self._config = DEFAULT_CONFIG.copy()
    
    def _save_config(self):
        """Guarda la configuración en el archivo"""
        try:
            config_path = "C:/ProgramData/PuntoVenta/Setting/settings.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error guardando configuración: {e}")
    
    def get(self, section=None, key=None, default=None):
        """Obtiene un valor de configuración"""
        if self._config is None:
            self._load_config()
            
        if section is None and key is None:
            return self._config.copy()
        elif key is None:
            return self._config.get(section, default)
        else:
            return self._config.get(section, {}).get(key, default)
    
    def set(self, section, key, value):
        """Establece un valor de configuración"""
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value
        self._save_config()
    
    def set_section(self, section, values):
        """Establece una sección completa de configuración"""
        self._config[section] = values
        self._save_config()
    
    def reload(self):
        """Recarga la configuración desde el archivo"""
        self._load_config()

# Función de conveniencia para compatibilidad
def load_config():
    """Carga la configuración (para compatibilidad con código existente)"""
    return ConfigManager().get()

# Singleton global para acceso fácil
config = ConfigManager()
CURRENT_USER = {}

# import json
# import os

# CONFIG_PATH = "C:/ProgramData/PuntoVenta/Setting/settings.json"

# def load_config():
#     with open(CONFIG_PATH, "r", encoding="utf-8") as f:
#         return json.load(f)
####v4