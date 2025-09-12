"""
Config Manager Completo - Compatible con daemon
Versión corregida que soluciona los errores de atributos faltantes
"""

import configparser
import os
import logging
from pathlib import Path

class ConfigManager:
    def __init__(self, config_file="config/camara.conf"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        # Crear configuración por defecto ANTES de cargar
        self._create_defaults()
        
        # Cargar configuración desde archivo
        self.load_config()
        
        # Crear objetos de compatibilidad que el daemon espera
        self._create_compatibility_objects()
    
    def _create_defaults(self):
        """Crear configuración por defecto"""
        self.config['UART'] = {
            'puerto': '/dev/ttyS0',
            'baudrate': '115200',
            'timeout': '1.0',
            'bytesize': '8',
            'parity': 'N',
            'stopbits': '1'
        }
        
        self.config['CAMERA'] = {
            'directorio': 'fotos',
            'resolucion': '1280x720',
            'formato': 'jpg',
            'resolucion_ancho': '1280',
            'resolucion_alto': '720',
            'calidad': '95'
        }
        
        self.config['SISTEMA'] = {
            'log_level': 'INFO',
            'log_file': 'logs/camara-uart.log',
            'directorio_fotos': 'fotos',
            'directorio_temp': 'data/temp',
            'directorio_logs': 'logs',
            'max_archivos': '1000',
            'auto_limpiar': 'true'
        }
        
        self.config['LOGGING'] = {
            'nivel': 'INFO',
            'archivo': 'logs/camara-uart.log',
            'formato': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'max_size_mb': '10',
            'backup_count': '5'
        }
        
        self.config['TRANSFERENCIA'] = {
            'chunk_size': '256',
            'timeout_chunk': '5.0',
            'max_reintentos': '3',
            'verificar_checksum': 'true',
            'compresion_habilitada': 'false',
            'compresion_nivel': '6'
        }
    
    def _create_compatibility_objects(self):
        """Crear objetos de compatibilidad que el daemon espera"""
        
        # Objeto logging
        class LoggingConfig:
            def __init__(self, config_manager):
                self.nivel = config_manager.get('LOGGING', 'nivel', 'INFO')
                self.archivo = config_manager.get('LOGGING', 'archivo', 'logs/camara-uart.log')
                self.formato = config_manager.get('LOGGING', 'formato', 
                                                '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                self.max_size_mb = int(config_manager.get('LOGGING', 'max_size_mb', '10'))
                self.backup_count = int(config_manager.get('LOGGING', 'backup_count', '5'))
        
        # Objeto sistema
        class SistemaConfig:
            def __init__(self, config_manager):
                self.log_level = config_manager.get('SISTEMA', 'log_level', 'INFO')
                self.log_file = config_manager.get('SISTEMA', 'log_file', 'logs/camara-uart.log')
                self.directorio_fotos = config_manager.get('SISTEMA', 'directorio_fotos', 'fotos')
                self.directorio_temp = config_manager.get('SISTEMA', 'directorio_temp', 'data/temp')
                self.directorio_logs = config_manager.get('SISTEMA', 'directorio_logs', 'logs')
                self.max_archivos = int(config_manager.get('SISTEMA', 'max_archivos', '1000'))
                self.auto_limpiar = config_manager.get('SISTEMA', 'auto_limpiar', 'true').lower() == 'true'
        
        # Objeto UART
        class UartConfig:
            def __init__(self, config_manager):
                self.puerto = config_manager.get('UART', 'puerto', '/dev/ttyS0')
                self.baudrate = int(config_manager.get('UART', 'baudrate', '115200'))
                self.timeout = float(config_manager.get('UART', 'timeout', '1.0'))
                self.bytesize = int(config_manager.get('UART', 'bytesize', '8'))
                self.parity = config_manager.get('UART', 'parity', 'N')
                self.stopbits = int(config_manager.get('UART', 'stopbits', '1'))
        
        # Objeto cámara
        class CamaraConfig:
            def __init__(self, config_manager):
                self.directorio = config_manager.get('CAMERA', 'directorio', 'fotos')
                self.resolucion = config_manager.get('CAMERA', 'resolucion', '1280x720')
                self.formato = config_manager.get('CAMERA', 'formato', 'jpg')
                self.resolucion_ancho = int(config_manager.get('CAMERA', 'resolucion_ancho', '1280'))
                self.resolucion_alto = int(config_manager.get('CAMERA', 'resolucion_alto', '720'))
                self.calidad = int(config_manager.get('CAMERA', 'calidad', '95'))
        
        # Objeto transferencia
        class TransferenciaConfig:
            def __init__(self, config_manager):
                self.chunk_size = int(config_manager.get('TRANSFERENCIA', 'chunk_size', '256'))
                self.timeout_chunk = float(config_manager.get('TRANSFERENCIA', 'timeout_chunk', '5.0'))
                self.max_reintentos = int(config_manager.get('TRANSFERENCIA', 'max_reintentos', '3'))
                self.verificar_checksum = config_manager.get('TRANSFERENCIA', 'verificar_checksum', 'true').lower() == 'true'
                self.compresion_habilitada = config_manager.get('TRANSFERENCIA', 'compresion_habilitada', 'false').lower() == 'true'
                self.compresion_nivel = int(config_manager.get('TRANSFERENCIA', 'compresion_nivel', '6'))
        
        # Crear instancias de objetos de compatibilidad
        self.logging = LoggingConfig(self)
        self.sistema = SistemaConfig(self)
        self.uart = UartConfig(self)
        self.camara = CamaraConfig(self)
        self.transferencia = TransferenciaConfig(self)
    
    def load_config(self):
        """Cargar configuración desde archivo"""
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file)
                print(f"✅ Configuración cargada: {self.config_file}")
            except Exception as e:
                print(f"⚠️  Error cargando config: {e}")
                # Continuar con configuración por defecto
        else:
            print(f"📝 Archivo de configuración no existe, creando: {self.config_file}")
            self.save_config()
    
    def save_config(self):
        """Guardar configuración a archivo"""
        # Crear directorio si no existe
        config_dir = os.path.dirname(self.config_file)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
            print(f"💾 Configuración guardada: {self.config_file}")
        except Exception as e:
            print(f"⚠️  Error guardando config: {e}")
    
    def get(self, section, key, fallback=None):
        """Obtener valor de configuración"""
        try:
            return self.config.get(section, key, fallback=fallback)
        except:
            return fallback
    
    def set(self, section, key, value):
        """Establecer valor de configuración"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
        
        # Actualizar objetos de compatibilidad
        self._update_compatibility_objects()
        
        # Guardar cambios
        self.save_config()
    
    def _update_compatibility_objects(self):
        """Actualizar objetos después de cambios"""
        try:
            self._create_compatibility_objects()
        except Exception as e:
            print(f"⚠️  Error actualizando objetos de compatibilidad: {e}")
    
    def obtener_info_sistema(self):
        """Obtener información del sistema para el daemon"""
        return {
            'config_file': self.config_file,
            'uart_puerto': self.uart.puerto,
            'uart_baudrate': self.uart.baudrate,
            'camara_directorio': self.camara.directorio,
            'camara_resolucion': self.camara.resolucion,
            'sistema_max_archivos': self.sistema.max_archivos,
            'logging_nivel': self.logging.nivel,
            'logging_archivo': self.logging.archivo
        }
    
    def actualizar_baudrate(self, nuevo_baudrate):
        """Actualizar velocidad UART"""
        self.set('UART', 'baudrate', nuevo_baudrate)
        print(f"🔧 Baudrate actualizado a: {nuevo_baudrate}")
    
    def obtener_velocidades_disponibles(self):
        """Obtener velocidades UART soportadas"""
        return [9600, 19200, 38400, 57600, 115200, 230400]
    
    def validar_configuracion(self):
        """Validar configuración actual"""
        errores = []
        
        # Validar puerto UART
        if not os.path.exists(self.uart.puerto):
            errores.append(f"Puerto UART no existe: {self.uart.puerto}")
        
        # Validar baudrate
        if self.uart.baudrate not in self.obtener_velocidades_disponibles():
            errores.append(f"Baudrate no válido: {self.uart.baudrate}")
        
        # Validar directorio de fotos
        try:
            Path(self.camara.directorio).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errores.append(f"No se puede crear directorio de fotos: {e}")
        
        # Validar directorio temporal
        try:
            Path(self.sistema.directorio_temp).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errores.append(f"No se puede crear directorio temporal: {e}")
        
        # Validar directorio de logs
        try:
            Path(self.sistema.directorio_logs).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errores.append(f"No se puede crear directorio de logs: {e}")
        
        return errores
    
    def crear_directorios_necesarios(self):
        """Crear directorios necesarios si no existen"""
        directorios = [
            self.camara.directorio,
            self.sistema.directorio_temp,
            self.sistema.directorio_logs,
            os.path.dirname(self.logging.archivo) if os.path.dirname(self.logging.archivo) else 'logs'
        ]
        
        for directorio in directorios:
            try:
                Path(directorio).mkdir(parents=True, exist_ok=True)
                print(f"📁 Directorio verificado: {directorio}")
            except Exception as e:
                print(f"⚠️  Error creando directorio {directorio}: {e}")
