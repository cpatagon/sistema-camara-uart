"""
Controlador de Cámara - Versión Simplificada y Funcional
Compatible con el daemon principal
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

# Intentar importar picamera2, con fallback si no está disponible
try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    print("⚠️  picamera2 no disponible, usando modo simulación")
    PICAMERA_AVAILABLE = False
    Picamera2 = None

class CamaraController:
    """
    Controlador de cámara compatible con el daemon
    """
    
    def __init__(self, config_manager=None):
        """Inicializa el controlador de cámara"""
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        
        # Configuración desde config manager o valores por defecto
        if config_manager:
            self.directorio = config_manager.camara.directorio
            self.resolucion_default = (config_manager.camara.resolucion_ancho, 
                                     config_manager.camara.resolucion_alto)
            self.calidad = config_manager.camara.calidad
            self.formato = config_manager.camara.formato
        else:
            self.directorio = "fotos"
            self.resolucion_default = (1280, 720)
            self.calidad = 95
            self.formato = "jpg"
        
        # Crear directorio si no existe
        Path(self.directorio).mkdir(parents=True, exist_ok=True)
        
        # Estado del controlador
        self.capturas_realizadas = 0
        self.ultima_captura = None
        self.historial_capturas = []
        
        self.logger.info(f"CamaraController inicializado")
        self.logger.info(f"Directorio: {self.directorio}")
        self.logger.info(f"Resolución: {self.resolucion_default[0]}x{self.resolucion_default[1]}")
        self.logger.info(f"PiCamera2 disponible: {PICAMERA_AVAILABLE}")
    
    def verificar_camara_disponible(self) -> bool:
        """Verifica si la cámara está disponible"""
        if not PICAMERA_AVAILABLE:
            self.logger.warning("PiCamera2 no disponible")
            return False
        
        try:
            # Intentar crear instancia básica
            picam2 = Picamera2()
            
            # Cerrar inmediatamente
            picam2.close()
            
            self.logger.info("Cámara disponible")
            return True
            
        except Exception as e:
            self.logger.warning(f"Cámara no disponible: {e}")
            return False
    
    def tomar_foto(self, nombre_personalizado: str = None) -> 'InfoCaptura':
        """
        Toma una fotografía con timestamp
        """
        picam2 = None
        info_captura = InfoCaptura()
        
        try:
            # Generar nombre de archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if nombre_personalizado:
                # Limpiar nombre personalizado
                nombre_limpio = "".join(c for c in nombre_personalizado if c.isalnum() or c in "._-")
                nombre_archivo = f"{nombre_limpio}_{timestamp}.{self.formato}"
            else:
                nombre_archivo = f"{timestamp}.{self.formato}"
            
            ruta_completa = Path(self.directorio) / nombre_archivo
            
            if PICAMERA_AVAILABLE:
                # Inicializar cámara real
                picam2 = Picamera2()
                config = picam2.create_still_configuration(
                    main={"size": self.resolucion_default}
                )
                picam2.configure(config)
                picam2.start()
                
                # Pausa para estabilizar
                time.sleep(0.5)
                
                # Capturar foto
                picam2.capture_file(str(ruta_completa))
                
            else:
                # Simular captura creando archivo dummy
                self._crear_foto_simulada(ruta_completa)
            
            # Obtener información del archivo
            tamaño_bytes = ruta_completa.stat().st_size
            
            # Actualizar información de captura
            info_captura.exito = True
            info_captura.nombre_archivo = nombre_archivo
            info_captura.ruta_completa = str(ruta_completa)
            info_captura.tamaño_bytes = tamaño_bytes
            info_captura.timestamp = timestamp
            info_captura.resolucion = self.resolucion_default
            info_captura.tiempo_captura = time.time() - info_captura.tiempo_inicio
            
            # Actualizar estadísticas
            self.capturas_realizadas += 1
            self.ultima_captura = info_captura
            self.historial_capturas.append(info_captura)
            
            # Mantener historial limitado
            if len(self.historial_capturas) > 100:
                self.historial_capturas = self.historial_capturas[-50:]
            
            self.logger.info(f"Foto capturada: {nombre_archivo} ({tamaño_bytes} bytes)")
            
            return info_captura
            
        except Exception as e:
            error_msg = f"Error al tomar foto: {e}"
            self.logger.error(error_msg)
            
            info_captura.exito = False
            info_captura.error = str(e)
            info_captura.tiempo_captura = time.time() - info_captura.tiempo_inicio
            
            return info_captura
            
        finally:
            if picam2 is not None:
                try:
                    picam2.stop()
                    picam2.close()
                except:
                    pass
                time.sleep(0.2)
    
    def _crear_foto_simulada(self, ruta: Path):
        """Crea una foto simulada para testing"""
        # Crear un archivo de imagen dummy simple
        contenido_dummy = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'
        
        with open(ruta, 'wb') as f:
            f.write(contenido_dummy)
    
    def cambiar_resolucion(self, ancho: int, alto: int) -> bool:
        """Cambia la resolución por defecto"""
        try:
            # Validar resolución
            resoluciones_soportadas = [
                (640, 480), (800, 600), (1024, 768),
                (1280, 720), (1280, 1024), (1920, 1080),
                (2592, 1944)
            ]
            
            nueva_resolucion = (ancho, alto)
            if nueva_resolucion not in resoluciones_soportadas:
                self.logger.warning(f"Resolución {ancho}x{alto} no está en la lista de soportadas")
                # Pero permitir el cambio de todas formas
            
            self.resolucion_default = nueva_resolucion
            
            # Actualizar en config manager si está disponible
            if self.config_manager:
                self.config_manager.set('CAMERA', 'resolucion_ancho', str(ancho))
                self.config_manager.set('CAMERA', 'resolucion_alto', str(alto))
                self.config_manager.set('CAMERA', 'resolucion', f"{ancho}x{alto}")
            
            self.logger.info(f"Resolución cambiada a: {ancho}x{alto}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cambiando resolución: {e}")
            return False
    
    def obtener_info_resolucion_actual(self) -> Dict[str, Any]:
        """Obtiene información de la resolución actual"""
        ancho, alto = self.resolucion_default
        megapixeles = (ancho * alto) / 1000000
        
        return {
            'ancho': ancho,
            'alto': alto,
            'megapixeles': f"{megapixeles:.1f}",
            'formato': self.formato,
            'calidad': self.calidad
        }
    
    def listar_archivos(self) -> List[Dict[str, Any]]:
        """Lista archivos en el directorio de fotos"""
        try:
            archivos = []
            directorio_path = Path(self.directorio)
            
            if not directorio_path.exists():
                return archivos
            
            # Buscar archivos de imagen
            extensiones = ['*.jpg', '*.jpeg', '*.png', '*.bmp']
            for extension in extensiones:
                for archivo in directorio_path.glob(extension):
                    try:
                        stat_info = archivo.stat()
                        archivos.append({
                            'nombre': archivo.name,
                            'tamaño_bytes': stat_info.st_size,
                            'fecha_modificacion': stat_info.st_mtime,
                            'fecha_str': datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                            'ruta_completa': str(archivo)
                        })
                    except Exception as e:
                        self.logger.warning(f"Error obteniendo info de {archivo}: {e}")
            
            # Ordenar por fecha (más recientes primero)
            archivos.sort(key=lambda x: x['fecha_modificacion'], reverse=True)
            
            return archivos
            
        except Exception as e:
            self.logger.error(f"Error listando archivos: {e}")
            return []
    
    def obtener_info_archivo(self, nombre_archivo: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de un archivo específico"""
        try:
            archivo_path = Path(self.directorio) / nombre_archivo
            if not archivo_path.exists():
                return None
            
            stat_info = archivo_path.stat()
            return {
                'nombre': archivo_path.name,
                'tamaño_bytes': stat_info.st_size,
                'fecha_modificacion': stat_info.st_mtime,
                'fecha_str': datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                'ruta_completa': str(archivo_path)
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo info de archivo {nombre_archivo}: {e}")
            return None
    
    def limpiar_archivos(self, criterio: str = "antiguos") -> Dict[str, int]:
        """Limpia archivos según criterio"""
        try:
            archivos = self.listar_archivos()
            archivos_eliminados = 0
            bytes_liberados = 0
            
            if criterio == "antiguos" and len(archivos) > 50:
                # Eliminar archivos más antiguos, conservar últimos 50
                archivos_a_eliminar = archivos[50:]
                
                for archivo_info in archivos_a_eliminar:
                    try:
                        archivo_path = Path(archivo_info['ruta_completa'])
                        if archivo_path.exists():
                            bytes_liberados += archivo_info['tamaño_bytes']
                            archivo_path.unlink()
                            archivos_eliminados += 1
                    except Exception as e:
                        self.logger.warning(f"Error eliminando {archivo_info['nombre']}: {e}")
            
            elif criterio == "todos":
                # Eliminar todos los archivos
                for archivo_info in archivos:
                    try:
                        archivo_path = Path(archivo_info['ruta_completa'])
                        if archivo_path.exists():
                            bytes_liberados += archivo_info['tamaño_bytes']
                            archivo_path.unlink()
                            archivos_eliminados += 1
                    except Exception as e:
                        self.logger.warning(f"Error eliminando {archivo_info['nombre']}: {e}")
            
            self.logger.info(f"Limpieza completada: {archivos_eliminados} archivos, {bytes_liberados} bytes")
            
            return {
                'archivos_eliminados': archivos_eliminados,
                'bytes_liberados': bytes_liberados
            }
            
        except Exception as e:
            self.logger.error(f"Error en limpieza de archivos: {e}")
            return {'archivos_eliminados': 0, 'bytes_liberados': 0}
    
    def reinicializar(self) -> bool:
        """Reinicializa el sistema de cámara"""
        try:
            self.logger.info("Reinicializando sistema de cámara...")
            
            # No hay mucho que reinicializar en el controlador actual
            # pero podríamos agregar lógica aquí si fuera necesario
            
            self.logger.info("Sistema de cámara reinicializado")
            return True
            
        except Exception as e:
            self.logger.error(f"Error reinicializando cámara: {e}")
            return False
    
    def realizar_captura_test(self) -> Dict[str, Any]:
        """Realiza una captura de prueba"""
        try:
            inicio = time.time()
            info_captura = self.tomar_foto("test_captura")
            tiempo_captura = time.time() - inicio
            
            if info_captura.exito:
                return {
                    'exito': True,
                    'tiempo_captura': tiempo_captura,
                    'archivo': info_captura.nombre_archivo,
                    'tamaño': info_captura.tamaño_bytes
                }
            else:
                return {
                    'exito': False,
                    'error': info_captura.error,
                    'tiempo_captura': tiempo_captura
                }
                
        except Exception as e:
            return {
                'exito': False,
                'error': str(e),
                'tiempo_captura': 0.0
            }
    
    def obtener_estado_sistema(self) -> Dict[str, Any]:
        """Obtiene estado del sistema de cámara"""
        return {
            'estado_camara': 'disponible' if self.verificar_camara_disponible() else 'no_disponible',
            'picamera_disponible': PICAMERA_AVAILABLE,
            'configuracion': {
                'directorio': self.directorio,
                'resolucion': f"{self.resolucion_default[0]}x{self.resolucion_default[1]}",
                'calidad': self.calidad,
                'formato': self.formato
            },
            'estadisticas': {
                'capturas_realizadas': self.capturas_realizadas,
                'ultima_captura': self.ultima_captura.timestamp if self.ultima_captura else None
            },
            'archivos': {
                'directorio': self.directorio,
                'total_archivos': len(self.listar_archivos())
            }
        }
    
    def limpiar_historial(self, mantener: int = 50):
        """Limpia el historial de capturas"""
        if len(self.historial_capturas) > mantener:
            self.historial_capturas = self.historial_capturas[-mantener:]
            self.logger.debug(f"Historial de capturas limpiado, manteniendo últimas {mantener}")
    
    def establecer_callback_captura(self, callback):
        """Establece callback para capturas completadas"""
        self.callback_captura = callback
    
    def establecer_callback_error(self, callback):
        """Establece callback para errores"""
        self.callback_error = callback


class InfoCaptura:
    """Información de una captura de foto"""
    
    def __init__(self):
        self.exito = False
        self.nombre_archivo = ""
        self.ruta_completa = ""
        self.tamaño_bytes = 0
        self.timestamp = ""
        self.resolucion = (0, 0)
        self.error = ""
        self.tiempo_inicio = time.time()
        self.tiempo_captura = 0.0


# Aliases para compatibilidad
CamaraUART = CamaraController
