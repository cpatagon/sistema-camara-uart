"""
Gestor de configuración para el sistema de cámara UART.

Este módulo maneja la lectura, validación y actualización dinámica
de la configuración del sistema desde archivos .conf.
"""

import os
import configparser
import logging
from typing import Dict, Any, Optional, Union, List, Tuple
from pathlib import Path
import json
from dataclasses import dataclass, asdict

from .exceptions import (
    ConfigError, 
    ConfigFileNotFoundError, 
    ConfigInvalidError,
    PermissionError as CamaraPermissionError
)


@dataclass
class UARTConfig:
    """Configuración UART del sistema."""
    puerto: str = "/dev/ttyS0"
    baudrate: int = 115200
    timeout: float = 1.0
    bytesize: int = 8
    parity: str = "N"  # N=None, E=Even, O=Odd
    stopbits: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CamaraConfig:
    """Configuración de la cámara."""
    resolucion_ancho: int = 1920
    resolucion_alto: int = 1080
    calidad: int = 95
    formato: str = "jpg"
    flip_horizontal: bool = False
    flip_vertical: bool = False
    rotacion: int = 0  # 0, 90, 180, 270
    iso: int = 0  # 0 = auto
    exposicion_auto: bool = True
    balance_blancos_auto: bool = True
    
    @property
    def resolucion(self) -> Tuple[int, int]:
        return (self.resolucion_ancho, self.resolucion_alto)
    
    @property
    def megapixeles(self) -> float:
        return (self.resolucion_ancho * self.resolucion_alto) / 1_000_000
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SistemaConfig:
    """Configuración general del sistema."""
    directorio_fotos: str = "/data/fotos"
    directorio_temp: str = "/data/temp"
    directorio_logs: str = "/var/log"
    max_archivos: int = 1000
    max_size_mb: int = 500
    auto_limpiar: bool = True
    limpiar_dias: int = 7
    backup_habilitado: bool = False
    backup_directorio: str = "/backup"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TransferenciaConfig:
    """Configuración de transferencia de archivos."""
    chunk_size: int = 256
    timeout_chunk: float = 5.0
    max_reintentos: int = 3
    verificar_checksum: bool = True
    compresion_habilitada: bool = False
    compresion_nivel: int = 6
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LoggingConfig:
    """Configuración de logging."""
    nivel: str = "INFO"
    archivo: str = "/var/log/camara-uart.log"
    max_size_mb: int = 10
    backup_count: int = 5
    formato: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    console_output: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfigManager:
    """
    Gestor centralizado de configuración del sistema.
    
    Maneja lectura, validación, actualización y persistencia
    de toda la configuración del sistema.
    """
    
    # Valores por defecto y validaciones
    BAUDRATES_VALIDOS = [9600, 19200, 38400, 57600, 115200, 230400]
    FORMATOS_VALIDOS = ["jpg", "jpeg", "png", "bmp"]
    RESOLUCIONES_VALIDAS = [
        (640, 480),     # VGA
        (800, 600),     # SVGA
        (1024, 768),    # XGA
        (1280, 720),    # HD
        (1280, 1024),   # SXGA
        (1920, 1080),   # Full HD
        (2592, 1944),   # 5MP
        (3280, 2464),   # 8MP
    ]
    NIVELES_LOG_VALIDOS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    
    def __init__(self, archivo_config: str = "config/camara.conf"):
        """
        Inicializa el gestor de configuración.
        
        Args:
            archivo_config: Ruta al archivo de configuración
        """
        self.archivo_config = Path(archivo_config)
        self.archivo_ejemplo = Path("config/camara.conf.example")
        
        # Configuraciones
        self.uart: UARTConfig = UARTConfig()
        self.camara: CamaraConfig = CamaraConfig()
        self.sistema: SistemaConfig = SistemaConfig()
        self.transferencia: TransferenciaConfig = TransferenciaConfig()
        self.logging: LoggingConfig = LoggingConfig()
        
        self.config_parser = configparser.ConfigParser()
        self.logger = logging.getLogger(__name__)
        
        # Cargar configuración
        self.cargar_configuracion()
    
    def cargar_configuracion(self):
        """Carga la configuración desde archivo."""
        try:
            # Verificar si existe el archivo
            if not self.archivo_config.exists():
                self._crear_config_desde_ejemplo()
            
            # Leer archivo de configuración
            self.config_parser.read(self.archivo_config, encoding='utf-8')
            
            # Cargar cada sección
            self._cargar_uart_config()
            self._cargar_camara_config()
            self._cargar_sistema_config()
            self._cargar_transferencia_config()
            self._cargar_logging_config()
            
            # Validar configuración completa
            self._validar_configuracion()
            
            # Crear directorios necesarios
            self._crear_directorios()
            
            self.logger.info("Configuración cargada exitosamente")
            
        except Exception as e:
            raise ConfigError(f"Error al cargar configuración: {str(e)}")
    
    def _crear_config_desde_ejemplo(self):
        """Crea archivo de configuración desde el ejemplo."""
        if not self.archivo_ejemplo.exists():
            # Crear archivo ejemplo con valores por defecto
            self._crear_archivo_ejemplo()
        
        try:
            # Copiar ejemplo a configuración real
            import shutil
            shutil.copy2(self.archivo_ejemplo, self.archivo_config)
            self.logger.info(f"Archivo de configuración creado desde ejemplo: {self.archivo_config}")
        except Exception as e:
            raise ConfigFileNotFoundError(str(self.archivo_config))
    
    def _crear_archivo_ejemplo(self):
        """Crea el archivo de ejemplo con valores por defecto."""
        config_ejemplo = configparser.ConfigParser()
        
        # Sección UART
        config_ejemplo.add_section('UART')
        config_ejemplo.set('UART', 'puerto', '/dev/ttyS0')
        config_ejemplo.set('UART', 'baudrate', '115200')
        config_ejemplo.set('UART', 'timeout', '1.0')
        config_ejemplo.set('UART', 'bytesize', '8')
        config_ejemplo.set('UART', 'parity', 'N')
        config_ejemplo.set('UART', 'stopbits', '1')
        
        # Sección CAMARA
        config_ejemplo.add_section('CAMARA')
        config_ejemplo.set('CAMARA', 'resolucion_ancho', '1920')
        config_ejemplo.set('CAMARA', 'resolucion_alto', '1080')
        config_ejemplo.set('CAMARA', 'calidad', '95')
        config_ejemplo.set('CAMARA', 'formato', 'jpg')
        config_ejemplo.set('CAMARA', 'flip_horizontal', 'false')
        config_ejemplo.set('CAMARA', 'flip_vertical', 'false')
        config_ejemplo.set('CAMARA', 'rotacion', '0')
        config_ejemplo.set('CAMARA', 'iso', '0')
        config_ejemplo.set('CAMARA', 'exposicion_auto', 'true')
        config_ejemplo.set('CAMARA', 'balance_blancos_auto', 'true')
        
        # Sección SISTEMA
        config_ejemplo.add_section('SISTEMA')
        config_ejemplo.set('SISTEMA', 'directorio_fotos', '/data/fotos')
        config_ejemplo.set('SISTEMA', 'directorio_temp', '/data/temp')
        config_ejemplo.set('SISTEMA', 'directorio_logs', '/var/log')
        config_ejemplo.set('SISTEMA', 'max_archivos', '1000')
        config_ejemplo.set('SISTEMA', 'max_size_mb', '500')
        config_ejemplo.set('SISTEMA', 'auto_limpiar', 'true')
        config_ejemplo.set('SISTEMA', 'limpiar_dias', '7')
        config_ejemplo.set('SISTEMA', 'backup_habilitado', 'false')
        config_ejemplo.set('SISTEMA', 'backup_directorio', '/backup')
        
        # Sección TRANSFERENCIA
        config_ejemplo.add_section('TRANSFERENCIA')
        config_ejemplo.set('TRANSFERENCIA', 'chunk_size', '256')
        config_ejemplo.set('TRANSFERENCIA', 'timeout_chunk', '5.0')
        config_ejemplo.set('TRANSFERENCIA', 'max_reintentos', '3')
        config_ejemplo.set('TRANSFERENCIA', 'verificar_checksum', 'true')
        config_ejemplo.set('TRANSFERENCIA', 'compresion_habilitada', 'false')
        config_ejemplo.set('TRANSFERENCIA', 'compresion_nivel', '6')
        
        # Sección LOGGING
        config_ejemplo.add_section('LOGGING')
        config_ejemplo.set('LOGGING', 'nivel', 'INFO')
        config_ejemplo.set('LOGGING', 'archivo', '/var/log/camara-uart.log')
        config_ejemplo.set('LOGGING', 'max_size_mb', '10')
        config_ejemplo.set('LOGGING', 'backup_count', '5')
        config_ejemplo.set('LOGGING', 'formato', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        config_ejemplo.set('LOGGING', 'console_output', 'true')
        
        # Crear directorio si no existe
        self.archivo_ejemplo.parent.mkdir(parents=True, exist_ok=True)
        
        # Guardar archivo
        with open(self.archivo_ejemplo, 'w', encoding='utf-8') as f:
            config_ejemplo.write(f)
    
    def _cargar_uart_config(self):
        """Carga configuración UART."""
        if 'UART' in self.config_parser:
            seccion = self.config_parser['UART']
            
            self.uart.puerto = seccion.get('puerto', self.uart.puerto)
            self.uart.baudrate = seccion.getint('baudrate', self.uart.baudrate)
            self.uart.timeout = seccion.getfloat('timeout', self.uart.timeout)
            self.uart.bytesize = seccion.getint('bytesize', self.uart.bytesize)
            self.uart.parity = seccion.get('parity', self.uart.parity)
            self.uart.stopbits = seccion.getint('stopbits', self.uart.stopbits)
    
    def _cargar_camara_config(self):
        """Carga configuración de cámara."""
        if 'CAMARA' in self.config_parser:
            seccion = self.config_parser['CAMARA']
            
            self.camara.resolucion_ancho = seccion.getint('resolucion_ancho', self.camara.resolucion_ancho)
            self.camara.resolucion_alto = seccion.getint('resolucion_alto', self.camara.resolucion_alto)
            self.camara.calidad = seccion.getint('calidad', self.camara.calidad)
            self.camara.formato = seccion.get('formato', self.camara.formato)
            self.camara.flip_horizontal = seccion.getboolean('flip_horizontal', self.camara.flip_horizontal)
            self.camara.flip_vertical = seccion.getboolean('flip_vertical', self.camara.flip_vertical)
            self.camara.rotacion = seccion.getint('rotacion', self.camara.rotacion)
            self.camara.iso = seccion.getint('iso', self.camara.iso)
            self.camara.exposicion_auto = seccion.getboolean('exposicion_auto', self.camara.exposicion_auto)
            self.camara.balance_blancos_auto = seccion.getboolean('balance_blancos_auto', self.camara.balance_blancos_auto)
    
    def _cargar_sistema_config(self):
        """Carga configuración del sistema."""
        if 'SISTEMA' in self.config_parser:
            seccion = self.config_parser['SISTEMA']
            
            self.sistema.directorio_fotos = seccion.get('directorio_fotos', self.sistema.directorio_fotos)
            self.sistema.directorio_temp = seccion.get('directorio_temp', self.sistema.directorio_temp)
            self.sistema.directorio_logs = seccion.get('directorio_logs', self.sistema.directorio_logs)
            self.sistema.max_archivos = seccion.getint('max_archivos', self.sistema.max_archivos)
            self.sistema.max_size_mb = seccion.getint('max_size_mb', self.sistema.max_size_mb)
            self.sistema.auto_limpiar = seccion.getboolean('auto_limpiar', self.sistema.auto_limpiar)
            self.sistema.limpiar_dias = seccion.getint('limpiar_dias', self.sistema.limpiar_dias)
            self.sistema.backup_habilitado = seccion.getboolean('backup_habilitado', self.sistema.backup_habilitado)
            self.sistema.backup_directorio = seccion.get('backup_directorio', self.sistema.backup_directorio)
    
    def _cargar_transferencia_config(self):
        """Carga configuración de transferencia."""
        if 'TRANSFERENCIA' in self.config_parser:
            seccion = self.config_parser['TRANSFERENCIA']
            
            self.transferencia.chunk_size = seccion.getint('chunk_size', self.transferencia.chunk_size)
            self.transferencia.timeout_chunk = seccion.getfloat('timeout_chunk', self.transferencia.timeout_chunk)
            self.transferencia.max_reintentos = seccion.getint('max_reintentos', self.transferencia.max_reintentos)
            self.transferencia.verificar_checksum = seccion.getboolean('verificar_checksum', self.transferencia.verificar_checksum)
            self.transferencia.compresion_habilitada = seccion.getboolean('compresion_habilitada', self.transferencia.compresion_habilitada)
            self.transferencia.compresion_nivel = seccion.getint('compresion_nivel', self.transferencia.compresion_nivel)
    
    def _cargar_logging_config(self):
        """Carga configuración de logging."""
        if 'LOGGING' in self.config_parser:
            seccion = self.config_parser['LOGGING']
            
            self.logging.nivel = seccion.get('nivel', self.logging.nivel)
            self.logging.archivo = seccion.get('archivo', self.logging.archivo)
            self.logging.max_size_mb = seccion.getint('max_size_mb', self.logging.max_size_mb)
            self.logging.backup_count = seccion.getint('backup_count', self.logging.backup_count)
            self.logging.formato = seccion.get('formato', self.logging.formato)
            self.logging.console_output = seccion.getboolean('console_output', self.logging.console_output)
    
    def _validar_configuracion(self):
        """Valida toda la configuración cargada."""
        # Validar UART
        if self.uart.baudrate not in self.BAUDRATES_VALIDOS:
            raise ConfigInvalidError('UART', 'baudrate', str(self.uart.baudrate), 
                                   f"Debe ser uno de: {self.BAUDRATES_VALIDOS}")
        
        if self.uart.timeout <= 0:
            raise ConfigInvalidError('UART', 'timeout', str(self.uart.timeout), 
                                   "Debe ser mayor que 0")
        
        # Validar CAMARA
        if self.camara.formato.lower() not in self.FORMATOS_VALIDOS:
            raise ConfigInvalidError('CAMARA', 'formato', self.camara.formato,
                                   f"Debe ser uno de: {self.FORMATOS_VALIDOS}")
        
        if not (1 <= self.camara.calidad <= 100):
            raise ConfigInvalidError('CAMARA', 'calidad', str(self.camara.calidad),
                                   "Debe estar entre 1 y 100")
        
        if self.camara.rotacion not in [0, 90, 180, 270]:
            raise ConfigInvalidError('CAMARA', 'rotacion', str(self.camara.rotacion),
                                   "Debe ser 0, 90, 180 o 270")
        
        # Validar resolución
        resolucion = (self.camara.resolucion_ancho, self.camara.resolucion_alto)
        if resolucion not in self.RESOLUCIONES_VALIDAS:
            self.logger.warning(f"Resolución {resolucion} no está en la lista estándar. Verificar compatibilidad.")
        
        # Validar SISTEMA
        if self.sistema.max_archivos <= 0:
            raise ConfigInvalidError('SISTEMA', 'max_archivos', str(self.sistema.max_archivos),
                                   "Debe ser mayor que 0")
        
        # Validar LOGGING
        if self.logging.nivel not in self.NIVELES_LOG_VALIDOS:
            raise ConfigInvalidError('LOGGING', 'nivel', self.logging.nivel,
                                   f"Debe ser uno de: {self.NIVELES_LOG_VALIDOS}")
    
    def _crear_directorios(self):
        """Crea los directorios necesarios."""
        directorios = [
            self.sistema.directorio_fotos,
            self.sistema.directorio_temp,
            self.sistema.directorio_logs
        ]
        
        if self.sistema.backup_habilitado:
            directorios.append(self.sistema.backup_directorio)
        
        for directorio in directorios:
            try:
                Path(directorio).mkdir(parents=True, exist_ok=True)
                self.logger.debug(f"Directorio verificado/creado: {directorio}")
            except PermissionError:
                raise CamaraPermissionError(directorio, "crear directorio")
    
    def actualizar_baudrate(self, nuevo_baudrate: int) -> bool:
        """
        Actualiza la velocidad UART dinámicamente.
        
        Args:
            nuevo_baudrate: Nueva velocidad en baudios
            
        Returns:
            bool: True si se actualizó correctamente
        """
        if nuevo_baudrate not in self.BAUDRATES_VALIDOS:
            raise ConfigInvalidError('UART', 'baudrate', str(nuevo_baudrate),
                                   f"Debe ser uno de: {self.BAUDRATES_VALIDOS}")
        
        self.uart.baudrate = nuevo_baudrate
        return self._guardar_seccion('UART', 'baudrate', str(nuevo_baudrate))
    
    def actualizar_resolucion(self, ancho: int, alto: int) -> bool:
        """
        Actualiza la resolución de cámara dinámicamente.
        
        Args:
            ancho: Ancho en píxeles
            alto: Alto en píxeles
            
        Returns:
            bool: True si se actualizó correctamente
        """
        self.camara.resolucion_ancho = ancho
        self.camara.resolucion_alto = alto
        
        exito = True
        exito &= self._guardar_seccion('CAMARA', 'resolucion_ancho', str(ancho))
        exito &= self._guardar_seccion('CAMARA', 'resolucion_alto', str(alto))
        
        return exito
    
    def _guardar_seccion(self, seccion: str, clave: str, valor: str) -> bool:
        """
        Guarda un valor específico en el archivo de configuración.
        
        Args:
            seccion: Nombre de la sección
            clave: Clave a actualizar
            valor: Nuevo valor
            
        Returns:
            bool: True si se guardó correctamente
        """
        try:
            # Actualizar en memoria
            if seccion not in self.config_parser:
                self.config_parser.add_section(seccion)
            
            self.config_parser.set(seccion, clave, valor)
            
            # Guardar a archivo
            with open(self.archivo_config, 'w', encoding='utf-8') as f:
                self.config_parser.write(f)
            
            self.logger.info(f"Configuración actualizada: [{seccion}][{clave}] = {valor}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error al guardar configuración: {e}")
            return False
    
    def obtener_configuracion_completa(self) -> Dict[str, Any]:
        """
        Obtiene toda la configuración como diccionario.
        
        Returns:
            Dict con toda la configuración
        """
        return {
            'uart': self.uart.to_dict(),
            'camara': self.camara.to_dict(),
            'sistema': self.sistema.to_dict(),
            'transferencia': self.transferencia.to_dict(),
            'logging': self.logging.to_dict()
        }
    
    def obtener_info_sistema(self) -> str:
        """
        Obtiene información resumida del sistema para status.
        
        Returns:
            str: Información formateada del sistema
        """
        return (f"Puerto:{self.uart.puerto}|"
                f"Velocidad:{self.uart.baudrate}|"
                f"Resolucion:{self.camara.resolucion_ancho}x{self.camara.resolucion_alto}|"
                f"Formato:{self.camara.formato}|"
                f"Fotos:{self.sistema.directorio_fotos}")
    
    def validar_espacio_disco(self, bytes_necesarios: int = None) -> bool:
        """
        Valida si hay suficiente espacio en disco.
        
        Args:
            bytes_necesarios: Bytes requeridos (opcional)
            
        Returns:
            bool: True si hay suficiente espacio
        """
        import shutil
        
        try:
            espacio_libre = shutil.disk_usage(self.sistema.directorio_fotos).free
            
            if bytes_necesarios:
                return espacio_libre >= bytes_necesarios
            
            # Verificar que quede al menos 100MB libres
            return espacio_libre >= (100 * 1024 * 1024)
            
        except Exception:
            return False
    
    def obtener_velocidades_disponibles(self) -> List[int]:
        """Obtiene lista de velocidades UART válidas."""
        return self.BAUDRATES_VALIDOS.copy()
    
    def obtener_resoluciones_disponibles(self) -> List[Tuple[int, int]]:
        """Obtiene lista de resoluciones recomendadas."""
        return self.RESOLUCIONES_VALIDAS.copy()
    
    def __str__(self) -> str:
        """Representación string del gestor de configuración."""
        return f"ConfigManager(uart={self.uart.puerto}@{self.uart.baudrate}, camera={self.camara.resolucion})"
