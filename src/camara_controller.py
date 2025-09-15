"""
Controlador de Cámara - Versión Actualizada para rpicam-apps
Compatible con Raspberry Pi OS Bookworm y manteniendo compatibilidad con libcamera-*
"""

import os
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

# Intentar importar picamera2, con fallback si no está disponible
try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    print("⚠️  picamera2 no disponible, usando comandos del sistema")
    PICAMERA_AVAILABLE = False
    Picamera2 = None

class CamaraController:
    """
    Controlador de cámara compatible con rpicam-apps (Raspberry Pi OS Bookworm)
    y libcamera-* (versiones anteriores), con fallback a picamera2
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
        
        # Detectar comandos de cámara disponibles
        self.cmd_still = self._detectar_comando_camara()
        self.metodo_captura = self._determinar_metodo_captura()
        
        self.logger.info(f"CamaraController inicializado")
        self.logger.info(f"Directorio: {self.directorio}")
        self.logger.info(f"Resolución: {self.resolucion_default[0]}x{self.resolucion_default[1]}")
        self.logger.info(f"Comando de cámara: {self.cmd_still}")
        self.logger.info(f"Método de captura: {self.metodo_captura}")
    
    def _detectar_comando_camara(self) -> str:
        """Detecta qué comando de cámara está disponible"""
        comandos_a_probar = [
            'rpicam-still',     # Raspberry Pi OS Bookworm+
            'libcamera-still',  # Raspberry Pi OS anteriores
            'rpicam-jpeg',      # Alternativa en Bookworm
            'libcamera-jpeg'    # Alternativa en versiones anteriores
        ]
        
        for cmd in comandos_a_probar:
            try:
                # Probar si el comando existe
                result = subprocess.run([cmd, '--help'], 
                                      capture_output=True, 
                                      timeout=5)
                if result.returncode == 0 or 'usage' in result.stderr.decode().lower():
                    self.logger.info(f"Comando de cámara detectado: {cmd}")
                    return cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        self.logger.warning("No se detectó comando de cámara del sistema")
        return None
    
    def _determinar_metodo_captura(self) -> str:
        """Determina el mejor método de captura disponible"""
        if self.cmd_still:
            return "sistema"
        elif PICAMERA_AVAILABLE:
            return "picamera2"
        else:
            return "simulacion"
    
    def verificar_camara_disponible(self) -> bool:
        """Verifica si la cámara está disponible"""
        if self.metodo_captura == "sistema":
            return self._verificar_camara_sistema()
        elif self.metodo_captura == "picamera2":
            return self._verificar_camara_picamera2()
        else:
            return True  # Simulación siempre disponible
    
    def _verificar_camara_sistema(self) -> bool:
        """Verifica cámara usando comandos del sistema"""
        try:
            # Usar comando rpicam-hello o libcamera-hello para verificar
            cmd_hello = self.cmd_still.replace('-still', '-hello').replace('-jpeg', '-hello')
            
            result = subprocess.run([
                cmd_hello, 
                '--timeout', '100',  # Timeout muy corto
                '--nopreview'
            ], capture_output=True, timeout=10)
            
            if result.returncode == 0:
                self.logger.info("Cámara disponible (verificada con comandos del sistema)")
                return True
            else:
                self.logger.warning(f"Cámara no disponible: {result.stderr.decode()}")
                return False
                
        except Exception as e:
            self.logger.warning(f"Error verificando cámara con comandos del sistema: {e}")
            return False
    
    def _verificar_camara_picamera2(self) -> bool:
        """Verifica cámara usando picamera2"""
        try:
            picam2 = Picamera2()
            picam2.close()
            self.logger.info("Cámara disponible (verificada con picamera2)")
            return True
        except Exception as e:
            self.logger.warning(f"Cámara no disponible con picamera2: {e}")
            return False
    
    def tomar_foto(self, nombre_personalizado: str = None) -> 'InfoCaptura':
        """Toma una fotografía usando el método disponible"""
        if self.metodo_captura == "sistema":
            return self._tomar_foto_sistema(nombre_personalizado)
        elif self.metodo_captura == "picamera2":
            return self._tomar_foto_picamera2(nombre_personalizado)
        else:
            return self._tomar_foto_simulada(nombre_personalizado)
    
    def _tomar_foto_sistema(self, nombre_personalizado: str = None) -> 'InfoCaptura':
        """Toma foto usando comandos del sistema (rpicam-* o libcamera-*)"""
        info_captura = InfoCaptura()
        
        try:
            # Generar nombre de archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if nombre_personalizado:
                nombre_limpio = "".join(c for c in nombre_personalizado if c.isalnum() or c in "._-")
                nombre_archivo = f"{nombre_limpio}_{timestamp}.{self.formato}"
            else:
                nombre_archivo = f"{timestamp}.{self.formato}"
            
            ruta_completa = Path(self.directorio) / nombre_archivo
            
            # Construir comando con sintaxis correcta
            ancho, alto = self.resolucion_default
            
            if 'rpicam-' in self.cmd_still:
                # Sintaxis rpicam-still (Bookworm)
                cmd = [
                    self.cmd_still,
                    '-o', str(ruta_completa),  # -o en lugar de --output
                    '--width', str(ancho),
                    '--height', str(alto),
                    '--quality', str(self.calidad),
                    '-t', '2000'  # -t en lugar de --timeout (en ms)
                ]
            else:
                # Sintaxis libcamera-still (anteriores)  
                cmd = [
                    self.cmd_still,
                    '--output', str(ruta_completa),
                    '--width', str(ancho),
                    '--height', str(alto),
                    '--quality', str(self.calidad),
                    '--timeout', '2000'  # En milisegundos
                ]
            
            # Ejecutar comando
            self.logger.debug(f"Ejecutando: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, timeout=15)
            
            if result.returncode == 0 and ruta_completa.exists():
                # Captura exitosa
                tamaño_bytes = ruta_completa.stat().st_size
                
                info_captura.exito = True
                info_captura.nombre_archivo = nombre_archivo
                info_captura.ruta_completa = str(ruta_completa)
                info_captura.tamaño_bytes = tamaño_bytes
                info_captura.timestamp = timestamp
                info_captura.resolucion = self.resolucion_default
                info_captura.tiempo_captura = time.time() - info_captura.tiempo_inicio
                
                self.logger.info(f"Foto capturada con {self.cmd_still}: {nombre_archivo} ({tamaño_bytes} bytes)")
            else:
                # Error en captura
                error_msg = result.stderr.decode() if result.stderr else "Error desconocido"
                raise Exception(f"Comando falló: {error_msg}")
            
        except Exception as e:
            self.logger.error(f"Error en captura con comandos del sistema: {e}")
            info_captura.exito = False
            info_captura.error = str(e)
            info_captura.tiempo_captura = time.time() - info_captura.tiempo_inicio
        
        # Actualizar estadísticas
        if info_captura.exito:
            self.capturas_realizadas += 1
            self.ultima_captura = info_captura
            self.historial_capturas.append(info_captura)
            self._mantener_historial_limitado()
        
        return info_captura
    
    def _tomar_foto_picamera2(self, nombre_personalizado: str = None) -> 'InfoCaptura':
        """Toma foto usando picamera2 (método de respaldo)"""
        picam2 = None
        info_captura = InfoCaptura()
        
        try:
            # Generar nombre de archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if nombre_personalizado:
                nombre_limpio = "".join(c for c in nombre_personalizado if c.isalnum() or c in "._-")
                nombre_archivo = f"{nombre_limpio}_{timestamp}.{self.formato}"
            else:
                nombre_archivo = f"{timestamp}.{self.formato}"
            
            ruta_completa = Path(self.directorio) / nombre_archivo
            
            # Inicializar cámara
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
            
            # Obtener información del archivo
            tamaño_bytes = ruta_completa.stat().st_size
            
            info_captura.exito = True
            info_captura.nombre_archivo = nombre_archivo
            info_captura.ruta_completa = str(ruta_completa)
            info_captura.tamaño_bytes = tamaño_bytes
            info_captura.timestamp = timestamp
            info_captura.resolucion = self.resolucion_default
            info_captura.tiempo_captura = time.time() - info_captura.tiempo_inicio
            
            self.logger.info(f"Foto capturada con picamera2: {nombre_archivo} ({tamaño_bytes} bytes)")
            
        except Exception as e:
            self.logger.error(f"Error en captura con picamera2: {e}")
            info_captura.exito = False
            info_captura.error = str(e)
            info_captura.tiempo_captura = time.time() - info_captura.tiempo_inicio
            
        finally:
            if picam2 is not None:
                try:
                    picam2.stop()
                    picam2.close()
                except:
                    pass
                time.sleep(0.2)
        
        # Actualizar estadísticas
        if info_captura.exito:
            self.capturas_realizadas += 1
            self.ultima_captura = info_captura
            self.historial_capturas.append(info_captura)
            self._mantener_historial_limitado()
        
        return info_captura
    
    def _tomar_foto_simulada(self, nombre_personalizado: str = None) -> 'InfoCaptura':
        """Crea una foto simulada para testing"""
        info_captura = InfoCaptura()
        
        try:
            # Generar nombre de archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if nombre_personalizado:
                nombre_limpio = "".join(c for c in nombre_personalizado if c.isalnum() or c in "._-")
                nombre_archivo = f"{nombre_limpio}_{timestamp}.{self.formato}"
            else:
                nombre_archivo = f"{timestamp}.{self.formato}"
            
            ruta_completa = Path(self.directorio) / nombre_archivo
            
            # Crear archivo de imagen dummy
            self._crear_foto_dummy(ruta_completa)
            
            # Obtener información del archivo
            tamaño_bytes = ruta_completa.stat().st_size
            
            info_captura.exito = True
            info_captura.nombre_archivo = nombre_archivo
            info_captura.ruta_completa = str(ruta_completa)
            info_captura.tamaño_bytes = tamaño_bytes
            info_captura.timestamp = timestamp
            info_captura.resolucion = self.resolucion_default
            info_captura.tiempo_captura = time.time() - info_captura.tiempo_inicio
            
            self.logger.info(f"Foto simulada creada: {nombre_archivo} ({tamaño_bytes} bytes)")
            
        except Exception as e:
            self.logger.error(f"Error creando foto simulada: {e}")
            info_captura.exito = False
            info_captura.error = str(e)
            info_captura.tiempo_captura = time.time() - info_captura.tiempo_inicio
        
        # Actualizar estadísticas
        if info_captura.exito:
            self.capturas_realizadas += 1
            self.ultima_captura = info_captura
            self.historial_capturas.append(info_captura)
            self._mantener_historial_limitado()
        
        return info_captura
    
    def _crear_foto_dummy(self, ruta: Path):
        """Crea una foto dummy simple pero válida"""
        # Header JPEG mínimo válido
        contenido_dummy = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08'
            b'\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e'
            b'\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff'
            b'\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03'
            b'\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda'
            b'\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'
        )
        
        with open(ruta, 'wb') as f:
            f.write(contenido_dummy)
    
    def _mantener_historial_limitado(self):
        """Mantiene el historial de capturas limitado"""
        if len(self.historial_capturas) > 100:
            self.historial_capturas = self.historial_capturas[-50:]
    
    def cambiar_resolucion(self, ancho: int, alto: int) -> bool:
        """Cambia la resolución por defecto"""
        try:
            # Validar resolución
            resoluciones_soportadas = [
                (640, 480), (800, 600), (1024, 768),
                (1280, 720), (1280, 1024), (1920, 1080),
                (2592, 1944), (2304, 1296), (3280, 2464)
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
            'calidad': self.calidad,
            'metodo_captura': self.metodo_captura,
            'comando_usado': self.cmd_still or 'N/A'
        }
    
    def obtener_info_sistema_camara(self) -> Dict[str, Any]:
        """Obtiene información detallada del sistema de cámara"""
        info = {
            'metodo_captura': self.metodo_captura,
            'comandos_disponibles': {},
            'picamera2_disponible': PICAMERA_AVAILABLE,
            'comando_activo': self.cmd_still
        }
        
        # Verificar disponibilidad de comandos
        comandos_a_verificar = [
            'rpicam-still', 'rpicam-vid', 'rpicam-hello', 'rpicam-jpeg',
            'libcamera-still', 'libcamera-vid', 'libcamera-hello', 'libcamera-jpeg'
        ]
        
        for cmd in comandos_a_verificar:
            try:
                result = subprocess.run([cmd, '--help'], 
                                      capture_output=True, 
                                      timeout=3)
                info['comandos_disponibles'][cmd] = result.returncode == 0
            except:
                info['comandos_disponibles'][cmd] = False
        
        return info
    
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
            
            # Re-detectar comandos disponibles
            self.cmd_still = self._detectar_comando_camara()
            self.metodo_captura = self._determinar_metodo_captura()
            
            self.logger.info(f"Sistema reinicializado - Método: {self.metodo_captura}, Comando: {self.cmd_still}")
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
            
            resultado = {
                'exito': info_captura.exito,
                'tiempo_captura': tiempo_captura,
                'metodo_usado': self.metodo_captura,
                'comando_usado': self.cmd_still or 'N/A'
            }
            
            if info_captura.exito:
                resultado.update({
                    'archivo': info_captura.nombre_archivo,
                    'tamaño': info_captura.tamaño_bytes,
                    'resolucion': f"{info_captura.resolucion[0]}x{info_captura.resolucion[1]}"
                })
            else:
                resultado['error'] = info_captura.error
            
            return resultado
                
        except Exception as e:
            return {
                'exito': False,
                'error': str(e),
                'tiempo_captura': 0.0,
                'metodo_usado': self.metodo_captura
            }
    
    def obtener_estado_sistema(self) -> Dict[str, Any]:
        """Obtiene estado del sistema de cámara"""
        return {
            'estado_camara': 'disponible' if self.verificar_camara_disponible() else 'no_disponible',
            'metodo_captura': self.metodo_captura,
            'comando_activo': self.cmd_still,
            'picamera2_disponible': PICAMERA_AVAILABLE,
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
            },
            'comandos_sistema': self.obtener_info_sistema_camara()['comandos_disponibles']
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


# Función de utilidad para crear alias de comandos
def crear_alias_compatibilidad():
    """
    Crea alias para mantener compatibilidad con libcamera-*
    cuando solo están disponibles los comandos rpicam-*
    """
    alias_map = {
        'libcamera-still': 'rpicam-still',
        'libcamera-vid': 'rpicam-vid', 
        'libcamera-hello': 'rpicam-hello',
        'libcamera-jpeg': 'rpicam-jpeg'
    }
    
    aliases_creados = []
    
    for comando_viejo, comando_nuevo in alias_map.items():
        try:
            # Verificar si el comando nuevo existe
            subprocess.run([comando_nuevo, '--help'], 
                          capture_output=True, timeout=3)
            
            # Verificar si el comando viejo NO existe
            try:
                subprocess.run([comando_viejo, '--help'], 
                              capture_output=True, timeout=3)
                continue  # El comando viejo ya existe
            except FileNotFoundError:
                pass
            
            # Crear alias usando ln -s
            alias_path = f"/usr/local/bin/{comando_viejo}"
            comando_completo = subprocess.run(['which', comando_nuevo], 
                                            capture_output=True, text=True)
            
            if comando_completo.returncode == 0:
                ruta_comando_nuevo = comando_completo.stdout.strip()
                subprocess.run(['sudo', 'ln', '-s', ruta_comando_nuevo, alias_path])
                aliases_creados.append(f"{comando_viejo} -> {comando_nuevo}")
                
        except Exception:
            continue
    
    return aliases_creados


# Aliases para compatibilidad
CamaraUART = CamaraController
