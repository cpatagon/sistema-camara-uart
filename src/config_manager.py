"""
Config Manager Completo - Compatible con daemon
"""

import configparser
import os
import logging

class ConfigManager:
    def __init__(self, config_file="config/camara.conf"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._create_defaults()
        self.load_config()
        
        # Crear objetos de compatibilidad que el daemon espera
        self.logging = self._create_logging_config()
        self.sistema = self._create_sistema_config()
        self.uart = self._create_uart_config()
        self.camara = self._create_camara_config()
    
    def _create_defaults(self):
        self.config['UART'] = {
            'puerto': '/dev/ttyS0',
            'baudrate': '9600',
            'timeout': '1'
        }
        
        self.config['CAMERA'] = {
            'directorio': 'fotos',
            'resolucion': '1280x720',
            'formato': 'jpg'
        }
        
        self.config['SISTEMA'] = {
            'log_level': 'INFO',
            'log_file': 'logs/camara-uart.log'
        }
        
        self.config['LOGGING'] = {
            'level': 'INFO',
            'file': 'logs/camara-uart.log',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    
    def _create_logging_config(self):
        """Crear objeto logging config"""
        class LoggingConfig:
            def __init__(self, config):
                self.level = config.get('LOGGING', 'level', 'INFO')
                self.file = config.get('LOGGING', 'file', 'logs/camara-uart.log')
                self.format = config.get('LOGGING', 'format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        return LoggingConfig(self)
    
    def _create_sistema_config(self):
        """Crear objeto sistema config"""
        class SistemaConfig:
            def __init__(self, config):
                self.log_level = config.get('SISTEMA', 'log_level', 'INFO')
                self.log_file = config.get('SISTEMA', 'log_file', 'logs/camara-uart.log')
        
        return SistemaConfig(self)
    
    def _create_uart_config(self):
        """Crear objeto uart config"""
        class UartConfig:
            def __init__(self, config):
                self.puerto = config.get('UART', 'puerto', '/dev/ttyS0')
                self.baudrate = int(config.get('UART', 'baudrate', '9600'))
                self.timeout = int(config.get('UART', 'timeout', '1'))
        
        return UartConfig(self)
    
    def _create_camara_config(self):
        """Crear objeto camara config"""
        class CamaraConfig:
            def __init__(self, config):
                self.directorio = config.get('CAMERA', 'directorio', 'fotos')
                self.resolucion = config.get('CAMERA', 'resolucion', '1280x720')
                self.formato = config.get('CAMERA', 'formato', 'jpg')
        
        return CamaraConfig(self)
    
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file)
                print(f"✅ Configuración cargada: {self.config_file}")
            except Exception as e:
                print(f"⚠️  Error cargando config: {e}")
        else:
            self.save_config()
    
    def save_config(self):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
        except Exception as e:
            print(f"⚠️  Error guardando config: {e}")
    
    def get(self, section, key, fallback=None):
        try:
            return self.config.get(section, key, fallback=fallback)
        except:
            return fallback
    
    def set(self, section, key, value):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
        
        # Actualizar objetos de compatibilidad
        self._update_compatibility_objects()
    
    def _update_compatibility_objects(self):
        """Actualizar objetos después de cambios"""
        self.logging = self._create_logging_config()
        self.sistema = self._create_sistema_config()
        self.uart = self._create_uart_config()
        self.camara = self._create_camara_config()
