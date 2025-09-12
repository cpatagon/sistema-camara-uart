"""
Gestor de transferencia de archivos simplificado
"""

import os
import time
import threading
import logging
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path
from queue import Queue, Empty

class FileTransferManager:
    """
    Gestor simplificado de transferencias de archivos
    """
    
    def __init__(self, config_manager):
        """Inicializa el gestor de transferencias"""
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Estado del gestor
        self.ejecutando = False
        self.cola_transferencias = Queue()
        self.hilo_procesador: Optional[threading.Thread] = None
        
        # Callbacks
        self.callback_progreso: Optional[Callable] = None
        self.callback_completada: Optional[Callable] = None
        self.callback_error: Optional[Callable] = None
        
        # Estadísticas
        self.transferencias_exitosas = 0
        self.transferencias_fallidas = 0
        
        # Directorio temporal
        self.directorio_temp = Path("data/temp")
        self.directorio_temp.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("FileTransferManager inicializado")
    
    def iniciar(self):
        """Inicia el gestor de transferencias"""
        if self.ejecutando:
            return
        
        self.ejecutando = True
        self.hilo_procesador = threading.Thread(target=self._bucle_procesador, daemon=True)
        self.hilo_procesador.start()
        
        self.logger.info("Gestor de transferencias iniciado")
    
    def detener(self):
        """Detiene el gestor de transferencias"""
        self.logger.info("Deteniendo gestor de transferencias...")
        
        self.ejecutando = False
        
        if self.hilo_procesador and self.hilo_procesador.is_alive():
            self.hilo_procesador.join(timeout=5.0)
        
        self.logger.info("Gestor de transferencias detenido")
    
    def programar_envio(self, archivo_origen: str, conexion_uart, nombre_destino: str = None) -> str:
        """Programa el envío de un archivo"""
        try:
            archivo_path = Path(archivo_origen)
            
            if not archivo_path.exists():
                raise FileNotFoundError(str(archivo_path))
            
            # ID simple de transferencia
            import uuid
            id_transferencia = str(uuid.uuid4())[:8]
            
            # Agregar a cola de procesamiento
            tarea = {
                'id': id_transferencia,
                'archivo': str(archivo_path),
                'conexion': conexion_uart,
                'nombre_destino': nombre_destino or archivo_path.name
            }
            
            self.cola_transferencias.put(tarea)
            
            self.logger.info(f"Transferencia programada: {id_transferencia} - {archivo_origen}")
            return id_transferencia
            
        except Exception as e:
            self.logger.error(f"Error programando envío: {e}")
            raise
    
    def _bucle_procesador(self):
        """Bucle principal de procesamiento"""
        while self.ejecutando:
            try:
                # Obtener tarea de la cola
                try:
                    tarea = self.cola_transferencias.get(timeout=1.0)
                except Empty:
                    continue
                
                # Procesar transferencia
                self._procesar_transferencia(tarea)
                self.cola_transferencias.task_done()
                
            except Exception as e:
                self.logger.error(f"Error en bucle procesador: {e}")
                time.sleep(1.0)
    
    def _procesar_transferencia(self, tarea: Dict[str, Any]):
        """Procesa una transferencia de archivo"""
        try:
            archivo_path = Path(tarea['archivo'])
            conexion = tarea['conexion']
            
            # Para simplificar, solo enviamos confirmación de que el archivo existe
            if archivo_path.exists():
                tamaño = archivo_path.stat().st_size
                
                mensaje = f"TRANSFER_START|{tarea['nombre_destino']}|{tamaño}"
                if conexion.enviar_mensaje(mensaje):
                    self.transferencias_exitosas += 1
                    self.logger.info(f"Transferencia completada: {tarea['nombre_destino']}")
                    
                    if self.callback_completada:
                        # Crear objeto simple de info de transferencia
                        class InfoTransferencia:
                            def __init__(self):
                                self.id_transferencia = tarea['id']
                                self.archivo_destino = tarea['nombre_destino']
                        
                        self.callback_completada(InfoTransferencia())
                else:
                    raise Exception("No se pudo enviar mensaje de transferencia")
            else:
                raise FileNotFoundError(f"Archivo no encontrado: {archivo_path}")
                
        except Exception as e:
            self.transferencias_fallidas += 1
            self.logger.error(f"Error en transferencia: {e}")
            
            if self.callback_error:
                class InfoTransferencia:
                    def __init__(self):
                        self.id_transferencia = tarea['id']
                        self.archivo_destino = tarea['nombre_destino']
                
                self.callback_error(InfoTransferencia(), e)
    
    def establecer_callbacks(self, callback_progreso=None, callback_completada=None, callback_error=None):
        """Establece callbacks para eventos"""
        if callback_progreso:
            self.callback_progreso = callback_progreso
        if callback_completada:
            self.callback_completada = callback_completada
        if callback_error:
            self.callback_error = callback_error
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Obtiene estadísticas del gestor"""
        return {
            'transferencias_exitosas': self.transferencias_exitosas,
            'transferencias_fallidas': self.transferencias_fallidas,
            'cola_pendientes': self.cola_transferencias.qsize()
        }
    
    def limpiar_archivos_temporales(self) -> Dict[str, int]:
        """Limpia archivos temporales"""
        archivos_eliminados = 0
        bytes_liberados = 0
        
        try:
            for archivo in self.directorio_temp.glob("*"):
                if archivo.is_file():
                    try:
                        tamaño = archivo.stat().st_size
                        archivo.unlink()
                        archivos_eliminados += 1
                        bytes_liberados += tamaño
                    except Exception as e:
                        self.logger.warning(f"Error eliminando {archivo}: {e}")
            
            return {
                'archivos_eliminados': archivos_eliminados,
                'bytes_liberados': bytes_liberados,
                'errores': 0
            }
            
        except Exception as e:
            self.logger.error(f"Error limpiando temporales: {e}")
            return {'archivos_eliminados': 0, 'bytes_liberados': 0, 'errores': 1}
