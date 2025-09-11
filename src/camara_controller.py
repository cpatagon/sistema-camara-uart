"""
Controlador de cámara para el sistema UART.

Este módulo maneja toda la interacción con la cámara Raspberry Pi,
incluyendo captura, configuración y gestión de archivos.
"""

import os
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List, Callable
from dataclasses import dataclass
from enum import Enum
import json

try:
    from picamera2 import Picamera2
    from picamera2.outputs import FileOutput
    from picamera2.encoders import JpegEncoder
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    Picamera2 = None

from .config_manager import ConfigManager
from .exceptions import (
    CamaraError,
    CamaraNotFoundError,
    CamaraInitError,
    CamaraCaptureError,
    CamaraResolutionError,
    DiskSpaceError,
    FileNotFoundError as CamaraFileNotFoundError
)


class EstadoCamara(Enum):
    """Estados de la cámara."""
    NO_DETECTADA = "no_detectada"
    INICIALIZANDO = "inicializando"
    LISTA = "lista"
    CAPTURANDO = "capturando"
    ERROR = "error"
    OCUPADA = "ocupada"


@dataclass
class InfoCaptura:
    """Información de una captura realizada."""
    nombre_archivo: str
    ruta_completa: str
    timestamp: datetime
    tamaño_bytes: int
    resolucion: Tuple[int, int]
    formato: str
    tiempo_captura: float
    checksum: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para serialización."""
        return {
            'nombre_archivo': self.nombre_archivo,
            'ruta_completa': self.ruta_completa,
            'timestamp': self.timestamp.isoformat(),
            'tamaño_bytes': self.tamaño_bytes,
            'resolucion': self.resolucion,
            'formato': self.formato,
            'tiempo_captura': self.tiempo_captura,
            'checksum': self.checksum
        }


@dataclass
class EstadisticasCamara:
    """Estadísticas de uso de la cámara."""
    fotos_totales: int = 0
    bytes_totales: int = 0
    tiempo_total_captura: float = 0.0
    ultima_captura: Optional[datetime] = None
    errores_captura: int = 0
    resolucion_actual: Tuple[int, int] = (0, 0)
    formato_actual: str = ""
    
    @property
    def tiempo_promedio_captura(self) -> float:
        """Tiempo promedio de captura en segundos."""
        if self.fotos_totales == 0:
            return 0.0
        return self.tiempo_total_captura / self.fotos_totales
    
    @property
    def tamaño_promedio_foto(self) -> float:
        """Tamaño promedio de foto en bytes."""
        if self.fotos_totales == 0:
            return 0.0
        return self.bytes_totales / self.fotos_totales


class CamaraController:
    """
    Controlador principal de la cámara Raspberry Pi.
    
    Maneja configuración, captura, gestión de archivos y estadísticas.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Inicializa el controlador de cámara.
        
        Args:
            config_manager: Gestor de configuración del sistema
        """
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Verificar disponibilidad de picamera2
        if not PICAMERA2_AVAILABLE:
            raise CamaraError("picamera2 no está disponible. Instalar con: pip install picamera2")
        
        # Estado de la cámara
        self.estado = EstadoCamara.NO_DETECTADA
        self.picam2: Optional[Picamera2] = None
        self.configuracion_actual: Optional[Dict] = None
        
        # Gestión de archivos
        self.directorio_fotos = Path(self.config.sistema.directorio_fotos)
        self.directorio_temp = Path(self.config.sistema.directorio_temp)
        
        # Estadísticas
        self.estadisticas = EstadisticasCamara()
        self.historial_capturas: List[InfoCaptura] = []
        
        # Thread safety
        self.lock_captura = threading.Lock()
        self.capturando = False
        
        # Callbacks
        self.callback_captura_completada: Optional[Callable[[InfoCaptura], None]] = None
        self.callback_error_captura: Optional[Callable[[Exception], None]] = None
        
        self.logger.info("CamaraController inicializado")
        
        # Detectar e inicializar cámara
        self._detectar_camara()
    
    def _detectar_camara(self) -> bool:
        """
        Detecta si la cámara está disponible.
        
        Returns:
            bool: True si la cámara fue detectada
        """
        try:
            self.logger.info("Detectando cámara...")
            
            # Verificar disponibilidad de hardware
            import subprocess
            result = subprocess.run(['vcgencmd', 'get_camera'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and 'detected=1' in result.stdout:
                self.logger.info("Cámara detectada por hardware")
                return self._inicializar_camara()
            else:
                self.estado = EstadoCamara.NO_DETECTADA
                self.logger.error("Cámara no detectada por hardware")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout detectando cámara")
            return False
        except FileNotFoundError:
            self.logger.warning("vcgencmd no disponible, intentando inicialización directa")
            return self._inicializar_camara()
        except Exception as e:
            self.logger.error(f"Error detectando cámara: {e}")
            return False
    
    def _inicializar_camara(self) -> bool:
        """
        Inicializa la cámara con la configuración actual.
        
        Returns:
            bool: True si la inicialización fue exitosa
        """
        try:
            self.estado = EstadoCamara.INICIALIZANDO
            self.logger.info("Inicializando cámara...")
            
            # Cerrar instancia previa si existe
            if self.picam2:
                try:
                    self.picam2.stop()
                    self.picam2.close()
                except:
                    pass
                self.picam2 = None
            
            # Crear nueva instancia
            self.picam2 = Picamera2()
            
            # Configurar cámara
            self._aplicar_configuracion()
            
            # Probar captura básica
            self._test_captura_basica()
            
            self.estado = EstadoCamara.LISTA
            self.estadisticas.resolucion_actual = self.config.camara.resolucion
            self.estadisticas.formato_actual = self.config.camara.formato
            
            self.logger.info(f"Cámara inicializada exitosamente: {self.config.camara.resolucion} @ {self.config.camara.formato}")
            return True
            
        except Exception as e:
            self.estado = EstadoCamara.ERROR
            error_msg = f"Error inicializando cámara: {str(e)}"
            self.logger.error(error_msg)
            raise CamaraInitError(error_msg)
    
    def _aplicar_configuracion(self):
        """Aplica la configuración actual a la cámara."""
        try:
            # Configuración de captura
            config_dict = {
                "main": {
                    "size": self.config.camara.resolucion,
                    "format": "RGB888"  # Formato interno
                }
            }
            
            # Aplicar transformaciones
            transform_dict = {}
            if self.config.camara.flip_horizontal:
                transform_dict["hflip"] = True
            if self.config.camara.flip_vertical:
                transform_dict["vflip"] = True
            if self.config.camara.rotacion != 0:
                transform_dict["rotation"] = self.config.camara.rotacion
            
            if transform_dict:
                config_dict["transform"] = transform_dict
            
            # Crear configuración
            self.configuracion_actual = self.picam2.create_still_configuration(**config_dict)
            self.picam2.configure(self.configuracion_actual)
            
            # Configurar controles de cámara
            controles = {}
            
            if not self.config.camara.exposicion_auto:
                # Configuración manual de exposición si está disponible
                pass
            
            if not self.config.camara.balance_blancos_auto:
                # Configuración manual de balance de blancos si está disponible
                pass
            
            if self.config.camara.iso > 0:
                controles["AnalogueGain"] = self.config.camara.iso / 100.0
            
            if controles:
                self.picam2.set_controls(controles)
            
            self.logger.debug(f"Configuración aplicada: {config_dict}")
            
        except Exception as e:
            raise CamaraInitError(f"Error aplicando configuración: {str(e)}")
    
    def _test_captura_basica(self):
        """Realiza una captura de prueba para verificar funcionamiento."""
        try:
            self.picam2.start()
            time.sleep(0.5)  # Tiempo para estabilizar
            
            # Captura de prueba en memoria
            import numpy as np
            array_prueba = self.picam2.capture_array()
            
            if array_prueba is None or array_prueba.size == 0:
                raise CamaraInitError("Captura de prueba resultó en array vacío")
            
            self.picam2.stop()
            self.logger.debug("Test de captura básica exitoso")
            
        except Exception as e:
            if self.picam2:
                try:
                    self.picam2.stop()
                except:
                    pass
            raise CamaraInitError(f"Test de captura falló: {str(e)}")
    
    def tomar_foto(self, nombre_personalizado: Optional[str] = None) -> InfoCaptura:
        """
        Toma una fotografía con la configuración actual.
        
        Args:
            nombre_personalizado: Nombre personalizado para el archivo (opcional)
            
        Returns:
            InfoCaptura: Información de la captura realizada
        """
        with self.lock_captura:
            if self.estado != EstadoCamara.LISTA:
                if self.estado == EstadoCamara.NO_DETECTADA:
                    raise CamaraNotFoundError()
                elif self.estado == EstadoCamara.ERROR:
                    # Intentar reinicializar
                    if not self._inicializar_camara():
                        raise CamaraCaptureError("Cámara en estado de error y no se pudo reinicializar")
                elif self.estado == EstadoCamara.CAPTURANDO:
                    raise CamaraCaptureError("Captura ya en progreso")
                else:
                    raise CamaraCaptureError(f"Cámara no lista, estado actual: {self.estado.value}")
            
            try:
                self.estado = EstadoCamara.CAPTURANDO
                self.capturando = True
                inicio_captura = time.time()
                
                self.logger.info("Iniciando captura de foto")
                
                # Verificar espacio en disco
                self._verificar_espacio_disco()
                
                # Generar nombre de archivo
                timestamp = datetime.now()
                if nombre_personalizado:
                    # Sanitizar nombre personalizado
                    nombre_base = self._sanitizar_nombre_archivo(nombre_personalizado)
                    nombre_archivo = f"{nombre_base}.{self.config.camara.formato}"
                else:
                    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
                    nombre_archivo = f"{timestamp_str}.{self.config.camara.formato}"
                
                ruta_completa = self.directorio_fotos / nombre_archivo
                
                # Realizar captura
                info_captura = self._ejecutar_captura(ruta_completa, timestamp, inicio_captura)
                
                # Actualizar estadísticas
                self._actualizar_estadisticas(info_captura)
                
                # Agregar al historial
                self.historial_capturas.append(info_captura)
                
                # Limpieza automática si está habilitada
                if self.config.sistema.auto_limpiar:
                    self._limpiar_archivos_antiguos()
                
                # Callback de captura completada
                if self.callback_captura_completada:
                    try:
                        self.callback_captura_completada(info_captura)
                    except Exception as e:
                        self.logger.error(f"Error en callback de captura completada: {e}")
                
                self.logger.info(f"Captura completada: {nombre_archivo} ({info_captura.tamaño_bytes} bytes)")
                return info_captura
                
            except Exception as e:
                self.estadisticas.errores_captura += 1
                
                # Callback de error
                if self.callback_error_captura:
                    try:
                        self.callback_error_captura(e)
                    except Exception as callback_error:
                        self.logger.error(f"Error en callback de error: {callback_error}")
                
                self.logger.error(f"Error en captura: {e}")
                raise CamaraCaptureError(str(e), str(ruta_completa) if 'ruta_completa' in locals() else None)
                
            finally:
                self.estado = EstadoCamara.LISTA
                self.capturando = False
    
    def _ejecutar_captura(self, ruta_archivo: Path, timestamp: datetime, inicio: float) -> InfoCaptura:
        """
        Ejecuta la captura física de la foto.
        
        Args:
            ruta_archivo: Ruta donde guardar la foto
            timestamp: Timestamp de la captura
            inicio: Tiempo de inicio para cálculo de duración
            
        Returns:
            InfoCaptura: Información de la captura
        """
        try:
            # Iniciar cámara
            self.picam2.start()
            
            # Tiempo de estabilización
            time.sleep(0.5)
            
            # Capturar a archivo
            if self.config.camara.formato.lower() in ['jpg', 'jpeg']:
                # Usar encoder JPEG con calidad específica
                encoder = JpegEncoder(q=self.config.camara.calidad)
                self.picam2.capture_file(str(ruta_archivo), encoder=encoder)
            else:
                # Captura directa para otros formatos
                self.picam2.capture_file(str(ruta_archivo))
            
            # Detener cámara
            self.picam2.stop()
            
            # Verificar que el archivo se creó correctamente
            if not ruta_archivo.exists():
                raise CamaraCaptureError("El archivo de foto no se creó")
            
            # Obtener información del archivo
            stat_archivo = ruta_archivo.stat()
            tiempo_captura = time.time() - inicio
            
            # Calcular checksum si está habilitado
            checksum = None
            if self.config.transferencia.verificar_checksum:
                checksum = self._calcular_checksum(ruta_archivo)
            
            return InfoCaptura(
                nombre_archivo=ruta_archivo.name,
                ruta_completa=str(ruta_archivo),
                timestamp=timestamp,
                tamaño_bytes=stat_archivo.st_size,
                resolucion=self.config.camara.resolucion,
                formato=self.config.camara.formato,
                tiempo_captura=tiempo_captura,
                checksum=checksum
            )
            
        except Exception as e:
            # Asegurar que la cámara se detiene en caso de error
            try:
                self.picam2.stop()
            except:
                pass
            
            # Limpiar archivo parcial si existe
            if ruta_archivo.exists():
                try:
                    ruta_archivo.unlink()
                except:
                    pass
            
            raise CamaraCaptureError(f"Error ejecutando captura: {str(e)}")
    
    def cambiar_resolucion(self, ancho: int, alto: int) -> bool:
        """
        Cambia la resolución de captura dinámicamente.
        
        Args:
            ancho: Ancho en píxeles
            alto: Alto en píxeles
            
        Returns:
            bool: True si el cambio fue exitoso
        """
        try:
            # Validar resolución
            resolucion_nueva = (ancho, alto)
            resoluciones_validas = self.config.obtener_resoluciones_disponibles()
            
            if resolucion_nueva not in resoluciones_validas:
                self.logger.warning(f"Resolución {resolucion_nueva} no está en lista estándar")
            
            # Verificar límites razonables
            if ancho < 64 or alto < 64 or ancho > 4096 or alto > 4096:
                raise CamaraResolutionError(resolucion_nueva, "Resolución fuera de límites razonables")
            
            self.logger.info(f"Cambiando resolución a {ancho}x{alto}")
            
            # Actualizar configuración
            self.config.actualizar_resolucion(ancho, alto)
            
            # Reinicializar cámara con nueva configuración
            if self.estado in [EstadoCamara.LISTA, EstadoCamara.ERROR]:
                self._inicializar_camara()
                self.logger.info(f"Resolución cambiada exitosamente a {ancho}x{alto}")
                return True
            else:
                self.logger.warning("Resolución actualizada en configuración, aplicará en próximo reinicio")
                return True
                
        except Exception as e:
            self.logger.error(f"Error cambiando resolución: {e}")
            return False
    
    def listar_archivos(self) -> List[Dict[str, Any]]:
        """
        Lista todos los archivos de fotos disponibles.
        
        Returns:
            List[Dict]: Lista de información de archivos
        """
        archivos = []
        
        try:
            # Patrones de archivos soportados
            patrones = ['*.jpg', '*.jpeg', '*.png', '*.bmp']
            
            for patron in patrones:
                for archivo in self.directorio_fotos.glob(patron):
                    try:
                        stat = archivo.stat()
                        
                        # Calcular checksum si está habilitado
                        checksum = None
                        if self.config.transferencia.verificar_checksum:
                            checksum = self._calcular_checksum(archivo)
                        
                        archivos.append({
                            'nombre': archivo.name,
                            'ruta_completa': str(archivo),
                            'tamaño_bytes': stat.st_size,
                            'fecha_creacion': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            'fecha_modificacion': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'checksum': checksum
                        })
                    except Exception as e:
                        self.logger.warning(f"Error procesando archivo {archivo.name}: {e}")
            
            # Ordenar por fecha de creación (más recientes primero)
            archivos.sort(key=lambda x: x['fecha_creacion'], reverse=True)
            
            self.logger.debug(f"Listados {len(archivos)} archivos")
            return archivos
            
        except Exception as e:
            self.logger.error(f"Error listando archivos: {e}")
            return []
    
    def obtener_info_archivo(self, nombre_archivo: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información detallada de un archivo específico.
        
        Args:
            nombre_archivo: Nombre del archivo
            
        Returns:
            Dict con información del archivo o None si no existe
        """
        try:
            ruta_archivo = self.directorio_fotos / nombre_archivo
            
            if not ruta_archivo.exists():
                return None
            
            stat = ruta_archivo.stat()
            
            # Información básica
            info = {
                'nombre': ruta_archivo.name,
                'ruta_completa': str(ruta_archivo),
                'tamaño_bytes': stat.st_size,
                'fecha_creacion': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'fecha_modificacion': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
            
            # Calcular checksum
            if self.config.transferencia.verificar_checksum:
                info['checksum'] = self._calcular_checksum(ruta_archivo)
            
            # Intentar obtener información de imagen
            try:
                from PIL import Image
                with Image.open(ruta_archivo) as img:
                    info['resolucion'] = img.size
                    info['formato_imagen'] = img.format
                    info['modo'] = img.mode
            except ImportError:
                self.logger.debug("PIL no disponible para información de imagen")
            except Exception as e:
                self.logger.debug(f"Error obteniendo info de imagen: {e}")
            
            return info
            
        except Exception as e:
            self.logger.error(f"Error obteniendo info de archivo {nombre_archivo}: {e}")
            return None
    
    def limpiar_archivos(self, criterio: str = "antiguos") -> Dict[str, Any]:
        """
        Limpia archivos según criterio especificado.
        
        Args:
            criterio: "antiguos", "todos", "por_tamaño"
            
        Returns:
            Dict con estadísticas de limpieza
        """
        archivos_eliminados = 0
        bytes_liberados = 0
        errores = 0
        
        try:
            archivos = self.listar_archivos()
            
            if criterio == "todos":
                archivos_a_eliminar = archivos
            elif criterio == "antiguos":
                # Eliminar archivos más antiguos que limpiar_dias
                from datetime import timedelta
                limite_fecha = datetime.now() - timedelta(days=self.config.sistema.limpiar_dias)
                archivos_a_eliminar = [
                    a for a in archivos 
                    if datetime.fromisoformat(a['fecha_creacion']) < limite_fecha
                ]
            elif criterio == "por_tamaño":
                # Eliminar archivos si se supera max_archivos
                if len(archivos) > self.config.sistema.max_archivos:
                    # Ordenar por fecha y eliminar los más antiguos
                    archivos.sort(key=lambda x: x['fecha_creacion'])
                    archivos_a_eliminar = archivos[:-self.config.sistema.max_archivos]
                else:
                    archivos_a_eliminar = []
            else:
                raise ValueError(f"Criterio de limpieza no válido: {criterio}")
            
            # Eliminar archivos
            for archivo_info in archivos_a_eliminar:
                try:
                    ruta_archivo = Path(archivo_info['ruta_completa'])
                    if ruta_archivo.exists():
                        bytes_liberados += archivo_info['tamaño_bytes']
                        ruta_archivo.unlink()
                        archivos_eliminados += 1
                        self.logger.debug(f"Archivo eliminado: {archivo_info['nombre']}")
                except Exception as e:
                    errores += 1
                    self.logger.error(f"Error eliminando {archivo_info['nombre']}: {e}")
            
            resultado = {
                'archivos_eliminados': archivos_eliminados,
                'bytes_liberados': bytes_liberados,
                'errores': errores,
                'criterio': criterio
            }
            
            self.logger.info(f"Limpieza completada: {archivos_eliminados} archivos, {bytes_liberados} bytes liberados")
            return resultado
            
        except Exception as e:
            self.logger.error(f"Error en limpieza de archivos: {e}")
            return {
                'archivos_eliminados': archivos_eliminados,
                'bytes_liberados': bytes_liberados,
                'errores': errores + 1,
                'criterio': criterio,
                'error': str(e)
            }
    
    def _limpiar_archivos_antiguos(self):
        """Limpieza automática de archivos antiguos."""
        try:
            resultado = self.limpiar_archivos("por_tamaño")
            if resultado['archivos_eliminados'] > 0:
                self.logger.info(f"Limpieza automática: {resultado['archivos_eliminados']} archivos eliminados")
        except Exception as e:
            self.logger.error(f"Error en limpieza automática: {e}")
    
    def _verificar_espacio_disco(self):
        """Verifica que hay suficiente espacio en disco."""
        if not self.config.validar_espacio_disco():
            import shutil
            espacio_libre = shutil.disk_usage(self.directorio_fotos).free
            raise DiskSpaceError(
                str(self.directorio_fotos),
                100 * 1024 * 1024,  # 100MB mínimo
                espacio_libre
            )
    
    def _sanitizar_nombre_archivo(self, nombre: str) -> str:
        """
        Sanitiza un nombre de archivo para uso seguro.
        
        Args:
            nombre: Nombre original
            
        Returns:
            str: Nombre sanitizado
        """
        import re
        # Remover caracteres no válidos
        nombre_limpio = re.sub(r'[<>:"/\\|?*]', '_', nombre)
        # Limitar longitud
        if len(nombre_limpio) > 50:
            nombre_limpio = nombre_limpio[:50]
        return nombre_limpio
    
    def _calcular_checksum(self, archivo_path: Path) -> str:
        """
        Calcula checksum MD5 de un archivo.
        
        Args:
            archivo_path: Ruta del archivo
            
        Returns:
            str: Checksum MD5 en hexadecimal
        """
        import hashlib
        
        hash_md5 = hashlib.md5()
        with open(archivo_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _actualizar_estadisticas(self, info_captura: InfoCaptura):
        """
        Actualiza estadísticas de la cámara.
        
        Args:
            info_captura: Información de la captura realizada
        """
        self.estadisticas.fotos_totales += 1
        self.estadisticas.bytes_totales += info_captura.tamaño_bytes
        self.estadisticas.tiempo_total_captura += info_captura.tiempo_captura
        self.estadisticas.ultima_captura = info_captura.timestamp
    
    def obtener_estado_sistema(self) -> Dict[str, Any]:
        """
        Obtiene estado completo del sistema de cámara.
        
        Returns:
            Dict con información completa del estado
        """
        archivos = self.listar_archivos()
        
        return {
            'estado_camara': self.estado.value,
            'capturando': self.capturando,
            'configuracion': {
                'resolucion': self.config.camara.resolucion,
                'formato': self.config.camara.formato,
                'calidad': self.config.camara.calidad,
                'rotacion': self.config.camara.rotacion
            },
            'estadisticas': {
                'fotos_totales': self.estadisticas.fotos_totales,
                'bytes_totales': self.estadisticas.bytes_totales,
                'tiempo_promedio_captura': self.estadisticas.tiempo_promedio_captura,
                'tamaño_promedio_foto': self.estadisticas.tamaño_promedio_foto,
                'errores_captura': self.estadisticas.errores_captura,
                'ultima_captura': self.estadisticas.ultima_captura.isoformat() if self.estadisticas.ultima_captura else None
            },
            'archivos': {
                'total_archivos': len(archivos),
                'directorio': str(self.directorio_fotos),
                'espacio_usado': sum(a['tamaño_bytes'] for a in archivos)
            },
            'sistema': {
                'directorio_fotos': str(self.directorio_fotos),
                'directorio_temp': str(self.directorio_temp),
                'auto_limpiar': self.config.sistema.auto_limpiar,
                'max_archivos': self.config.sistema.max_archivos
            }
        }
    
    def reinicializar(self) -> bool:
        """
        Reinicializa completamente el sistema de cámara.
        
        Returns:
            bool: True si la reinicialización fue exitosa
        """
        try:
            self.logger.info("Reinicializando sistema de cámara...")
            
            # Detener captura si está en progreso
            if self.capturando:
                self.logger.warning("Interrumpiendo captura en progreso para reinicializar")
            
            # Cerrar cámara actual
            if self.picam2:
                try:
                    self.picam2.stop()
                    self.picam2.close()
                except:
                    pass
                self.picam2 = None
            
            # Reinicializar
            return self._detectar_camara()
            
        except Exception as e:
            self.logger.error(f"Error reinicializando cámara: {e}")
            self.estado = EstadoCamara.ERROR
            return False
    
    def establecer_callback_captura(self, callback: Callable[[InfoCaptura], None]):
        """
        Establece callback para cuando se completa una captura.
        
        Args:
            callback: Función a llamar cuando se completa captura
        """
        self.callback_captura_completada = callback
    
    def establecer_callback_error(self, callback: Callable[[Exception], None]):
        """
        Establece callback para errores de captura.
        
        Args:
            callback: Función a llamar cuando ocurre error
        """
        self.callback_error_captura = callback
    
    def obtener_resoluciones_soportadas(self) -> List[Tuple[int, int]]:
        """
        Obtiene lista de resoluciones soportadas por la cámara.
        
        Returns:
            List[Tuple]: Lista de resoluciones (ancho, alto)
        """
        if not self.picam2:
            return self.config.obtener_resoluciones_disponibles()
        
        try:
            # Intentar obtener resoluciones desde la cámara
            sensor_modes = self.picam2.sensor_modes
            resoluciones = []
            
            for mode in sensor_modes:
                if 'size' in mode:
                    size = mode['size']
                    if size not in resoluciones:
                        resoluciones.append(size)
            
            # Si no se obtuvieron resoluciones, usar las por defecto
            if not resoluciones:
                resoluciones = self.config.obtener_resoluciones_disponibles()
            
            return sorted(resoluciones, key=lambda x: x[0] * x[1])
            
        except Exception as e:
            self.logger.warning(f"Error obteniendo resoluciones de cámara: {e}")
            return self.config.obtener_resoluciones_disponibles()
    
    def obtener_info_resolucion_actual(self) -> Dict[str, Any]:
        """
        Obtiene información detallada de la resolución actual.
        
        Returns:
            Dict con información de resolución
        """
        resolucion = self.config.camara.resolucion
        megapixeles = self.config.camara.megapixeles
        
        return {
            'resolucion': resolucion,
            'ancho': resolucion[0],
            'alto': resolucion[1],
            'megapixeles': round(megapixeles, 2),
            'formato': self.config.camara.formato,
            'calidad': self.config.camara.calidad,
            'aspecto': round(resolucion[0] / resolucion[1], 2) if resolucion[1] > 0 else 0
        }
    
    def realizar_captura_test(self) -> Dict[str, Any]:
        """
        Realiza una captura de prueba sin guardar archivo.
        
        Returns:
            Dict con resultado del test
        """
        try:
            if self.estado != EstadoCamara.LISTA:
                return {
                    'exito': False,
                    'error': f'Cámara no lista: {self.estado.value}'
                }
            
            self.logger.info("Realizando captura de prueba...")
            inicio = time.time()
            
            # Captura en memoria
            self.picam2.start()
            time.sleep(0.5)
            
            import numpy as np
            array_test = self.picam2.capture_array()
            
            self.picam2.stop()
            
            tiempo_captura = time.time() - inicio
            
            if array_test is None or array_test.size == 0:
                return {
                    'exito': False,
                    'error': 'Captura resultó en array vacío'
                }
            
            return {
                'exito': True,
                'tiempo_captura': tiempo_captura,
                'resolucion_capturada': array_test.shape[:2] if len(array_test.shape) >= 2 else None,
                'tamaño_array': array_test.size,
                'tipo_datos': str(array_test.dtype) if hasattr(array_test, 'dtype') else None
            }
            
        except Exception as e:
            try:
                self.picam2.stop()
            except:
                pass
            
            return {
                'exito': False,
                'error': str(e)
            }
    
    def exportar_configuracion(self) -> Dict[str, Any]:
        """
        Exporta la configuración actual de la cámara.
        
        Returns:
            Dict con configuración completa
        """
        return {
            'camara': self.config.camara.to_dict(),
            'sistema': self.config.sistema.to_dict(),
            'transferencia': self.config.transferencia.to_dict(),
            'estado_actual': {
                'estado': self.estado.value,
                'configuracion_aplicada': self.configuracion_actual,
                'resoluciones_soportadas': self.obtener_resoluciones_soportadas()
            },
            'estadisticas': {
                'fotos_totales': self.estadisticas.fotos_totales,
                'bytes_totales': self.estadisticas.bytes_totales,
                'tiempo_total_captura': self.estadisticas.tiempo_total_captura,
                'errores_captura': self.estadisticas.errores_captura
            }
        }
    
    def importar_historial_capturas(self, archivo_historial: str) -> bool:
        """
        Importa historial de capturas desde archivo JSON.
        
        Args:
            archivo_historial: Ruta al archivo de historial
            
        Returns:
            bool: True si la importación fue exitosa
        """
        try:
            historial_path = Path(archivo_historial)
            
            if not historial_path.exists():
                self.logger.warning(f"Archivo de historial no encontrado: {archivo_historial}")
                return False
            
            with open(historial_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'capturas' in data:
                capturas_importadas = 0
                
                for captura_dict in data['capturas']:
                    try:
                        # Reconstruir InfoCaptura desde diccionario
                        info_captura = InfoCaptura(
                            nombre_archivo=captura_dict['nombre_archivo'],
                            ruta_completa=captura_dict['ruta_completa'],
                            timestamp=datetime.fromisoformat(captura_dict['timestamp']),
                            tamaño_bytes=captura_dict['tamaño_bytes'],
                            resolucion=tuple(captura_dict['resolucion']),
                            formato=captura_dict['formato'],
                            tiempo_captura=captura_dict['tiempo_captura'],
                            checksum=captura_dict.get('checksum')
                        )
                        
                        self.historial_capturas.append(info_captura)
                        capturas_importadas += 1
                        
                    except Exception as e:
                        self.logger.warning(f"Error importando captura individual: {e}")
                
                self.logger.info(f"Historial importado: {capturas_importadas} capturas")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error importando historial: {e}")
            return False
    
    def exportar_historial_capturas(self, archivo_destino: str) -> bool:
        """
        Exporta historial de capturas a archivo JSON.
        
        Args:
            archivo_destino: Ruta del archivo de destino
            
        Returns:
            bool: True si la exportación fue exitosa
        """
        try:
            data = {
                'metadata': {
                    'version': '1.0',
                    'exportado': datetime.now().isoformat(),
                    'total_capturas': len(self.historial_capturas)
                },
                'configuracion': self.exportar_configuracion(),
                'capturas': [captura.to_dict() for captura in self.historial_capturas]
            }
            
            destino_path = Path(archivo_destino)
            destino_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(destino_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Historial exportado a: {archivo_destino}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exportando historial: {e}")
            return False
    
    def obtener_ultimas_capturas(self, cantidad: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las últimas capturas realizadas.
        
        Args:
            cantidad: Número de capturas a obtener
            
        Returns:
            List[Dict]: Lista de últimas capturas
        """
        capturas_recientes = sorted(
            self.historial_capturas,
            key=lambda x: x.timestamp,
            reverse=True
        )[:cantidad]
        
        return [captura.to_dict() for captura in capturas_recientes]
    
    def limpiar_historial(self, mantener_ultimas: int = 100):
        """
        Limpia historial de capturas manteniendo solo las más recientes.
        
        Args:
            mantener_ultimas: Número de capturas a mantener
        """
        if len(self.historial_capturas) > mantener_ultimas:
            self.historial_capturas = sorted(
                self.historial_capturas,
                key=lambda x: x.timestamp,
                reverse=True
            )[:mantener_ultimas]
            
            self.logger.info(f"Historial limpiado, mantenidas {mantener_ultimas} capturas")
    
    def __del__(self):
        """Destructor para limpiar recursos."""
        try:
            if self.picam2:
                self.picam2.stop()
                self.picam2.close()
        except:
            pass
