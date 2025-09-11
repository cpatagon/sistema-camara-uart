"""
Gestor de transferencia de archivos por UART.

Este módulo implementa un protocolo robusto de transferencia de archivos
con verificación de integridad, compresión opcional y manejo de errores.
"""

import os
import time
import threading
import logging
import hashlib
import zlib
import struct
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, BinaryIO, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from queue import Queue, Empty
import tempfile

from config_manager import ConfigManager
from exceptions import (
    FileTransferError,
    FileNotFoundError,
    FileTransferTimeoutError,
    FileTransferChecksumError,
    DiskSpaceError,
    SystemError
)


class EstadoTransferencia(Enum):
    """Estados de una transferencia de archivo."""
    PENDIENTE = "pendiente"
    INICIANDO = "iniciando"
    ENVIANDO_HEADER = "enviando_header"
    ESPERANDO_CONFIRMACION = "esperando_confirmacion"
    TRANSFIRIENDO = "transfiriendo"
    VERIFICANDO = "verificando"
    COMPLETADA = "completada"
    ERROR = "error"
    CANCELADA = "cancelada"


class TipoTransferencia(Enum):
    """Tipos de transferencia soportados."""
    ENVIO = "envio"
    RECEPCION = "recepcion"


@dataclass
class InfoTransferencia:
    """Información completa de una transferencia."""
    id_transferencia: str
    tipo: TipoTransferencia
    archivo_origen: str
    archivo_destino: str
    tamaño_total: int
    estado: EstadoTransferencia
    progreso_bytes: int = 0
    progreso_chunks: int = 0
    chunks_totales: int = 0
    velocidad_bps: float = 0.0
    tiempo_inicio: float = 0.0
    tiempo_transcurrido: float = 0.0
    checksum_origen: str = ""
    checksum_destino: str = ""
    compresion_habilitada: bool = False
    tamaño_comprimido: int = 0
    error_mensaje: str = ""
    reintentos_realizados: int = 0
    
    @property
    def porcentaje_completado(self) -> float:
        """Porcentaje de transferencia completado."""
        if self.tamaño_total == 0:
            return 100.0
        return (self.progreso_bytes / self.tamaño_total) * 100.0
    
    @property
    def tiempo_estimado_restante(self) -> float:
        """Tiempo estimado restante en segundos."""
        if self.porcentaje_completado == 0 or self.velocidad_bps == 0:
            return 0.0
        
        bytes_restantes = self.tamaño_total - self.progreso_bytes
        return bytes_restantes / self.velocidad_bps
    
    @property
    def ratio_compresion(self) -> float:
        """Ratio de compresión (si aplica)."""
        if not self.compresion_habilitada or self.tamaño_comprimido == 0:
            return 1.0
        return self.tamaño_total / self.tamaño_comprimido
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para serialización."""
        return {
            'id_transferencia': self.id_transferencia,
            'tipo': self.tipo.value,
            'archivo_origen': self.archivo_origen,
            'archivo_destino': self.archivo_destino,
            'tamaño_total': self.tamaño_total,
            'estado': self.estado.value,
            'progreso_bytes': self.progreso_bytes,
            'progreso_chunks': self.progreso_chunks,
            'chunks_totales': self.chunks_totales,
            'porcentaje_completado': self.porcentaje_completado,
            'velocidad_bps': self.velocidad_bps,
            'tiempo_transcurrido': self.tiempo_transcurrido,
            'tiempo_estimado_restante': self.tiempo_estimado_restante,
            'checksum_origen': self.checksum_origen,
            'checksum_destino': self.checksum_destino,
            'compresion_habilitada': self.compresion_habilitada,
            'tamaño_comprimido': self.tamaño_comprimido,
            'ratio_compresion': self.ratio_compresion,
            'error_mensaje': self.error_mensaje,
            'reintentos_realizados': self.reintentos_realizados
        }


@dataclass
class ChunkInfo:
    """Información de un chunk de datos."""
    numero: int
    tamaño: int
    checksum: str
    datos: bytes
    comprimido: bool = False
    reintentos: int = 0


class ProtocoloTransferencia:
    """
    Implementa el protocolo de transferencia de archivos.
    
    Protocolo:
    1. HEADER: FILE|nombre|tamaño|checksum|compresion
    2. READY: Confirmación del receptor
    3. CHUNKS: Datos en bloques con ACK
    4. VERIFY: Verificación final
    5. DONE: Confirmación de completado
    """
    
    # Constantes del protocolo
    HEADER_PREFIX = "FILE"
    READY_MSG = "READY"
    ACK_MSG = "ACK"
    NACK_MSG = "NACK"
    VERIFY_MSG = "VERIFY"
    DONE_MSG = "DONE"
    ERROR_MSG = "ERROR"
    CANCEL_MSG = "CANCEL"
    
    # Separadores
    FIELD_SEP = "|"
    LINE_END = "\r\n"
    
    @classmethod
    def crear_header(cls, nombre_archivo: str, tamaño: int, checksum: str, 
                    comprimido: bool = False, tamaño_comprimido: int = 0) -> str:
        """
        Crea header de transferencia.
        
        Args:
            nombre_archivo: Nombre del archivo
            tamaño: Tamaño del archivo
            checksum: Checksum del archivo
            comprimido: Si el archivo está comprimido
            tamaño_comprimido: Tamaño después de compresión
            
        Returns:
            str: Header formateado
        """
        campos = [
            cls.HEADER_PREFIX,
            nombre_archivo,
            str(tamaño),
            checksum
        ]
        
        if comprimido:
            campos.extend(["COMPRESSED", str(tamaño_comprimido)])
        
        return cls.FIELD_SEP.join(campos) + cls.LINE_END
    
    @classmethod
    def parsear_header(cls, header_str: str) -> Dict[str, Any]:
        """
        Parsea header de transferencia.
        
        Args:
            header_str: String del header
            
        Returns:
            Dict con información parseada
        """
        try:
            header_limpio = header_str.strip()
            campos = header_limpio.split(cls.FIELD_SEP)
            
            if len(campos) < 4 or campos[0] != cls.HEADER_PREFIX:
                raise FileTransferError("Header inválido", header_str)
            
            info = {
                'nombre_archivo': campos[1],
                'tamaño': int(campos[2]),
                'checksum': campos[3],
                'comprimido': False,
                'tamaño_comprimido': 0
            }
            
            if len(campos) >= 6 and campos[4] == "COMPRESSED":
                info['comprimido'] = True
                info['tamaño_comprimido'] = int(campos[5])
            
            return info
            
        except (ValueError, IndexError) as e:
            raise FileTransferError(f"Error parseando header: {str(e)}", header_str)


class CompresorArchivos:
    """Manejador de compresión/descompresión de archivos."""
    
    @staticmethod
    def comprimir_archivo(archivo_origen: Path, archivo_destino: Path, 
                         nivel: int = 6) -> Tuple[int, int]:
        """
        Comprime un archivo usando zlib.
        
        Args:
            archivo_origen: Archivo a comprimir
            archivo_destino: Archivo comprimido de salida
            nivel: Nivel de compresión (1-9)
            
        Returns:
            Tuple[int, int]: (tamaño_original, tamaño_comprimido)
        """
        try:
            tamaño_original = archivo_origen.stat().st_size
            
            with open(archivo_origen, 'rb') as f_in:
                with open(archivo_destino, 'wb') as f_out:
                    # Header con tamaño original
                    f_out.write(struct.pack('<Q', tamaño_original))
                    
                    # Comprimir datos
                    compressor = zlib.compressobj(nivel)
                    
                    while True:
                        chunk = f_in.read(8192)
                        if not chunk:
                            break
                        
                        compressed_chunk = compressor.compress(chunk)
                        if compressed_chunk:
                            f_out.write(compressed_chunk)
                    
                    # Finalizar compresión
                    final_chunk = compressor.flush()
                    if final_chunk:
                        f_out.write(final_chunk)
            
            tamaño_comprimido = archivo_destino.stat().st_size
            return tamaño_original, tamaño_comprimido
            
        except Exception as e:
            raise FileTransferError(f"Error comprimiendo archivo: {str(e)}")
    
    @staticmethod
    def descomprimir_archivo(archivo_comprimido: Path, archivo_destino: Path) -> int:
        """
        Descomprime un archivo.
        
        Args:
            archivo_comprimido: Archivo comprimido
            archivo_destino: Archivo descomprimido de salida
            
        Returns:
            int: Tamaño del archivo descomprimido
        """
        try:
            with open(archivo_comprimido, 'rb') as f_in:
                # Leer tamaño original
                tamaño_original = struct.unpack('<Q', f_in.read(8))[0]
                
                with open(archivo_destino, 'wb') as f_out:
                    decompressor = zlib.decompressobj()
                    bytes_escritos = 0
                    
                    while bytes_escritos < tamaño_original:
                        chunk = f_in.read(8192)
                        if not chunk:
                            break
                        
                        try:
                            decompressed_chunk = decompressor.decompress(chunk)
                            if decompressed_chunk:
                                # Asegurar no escribir más bytes de los esperados
                                bytes_restantes = tamaño_original - bytes_escritos
                                if len(decompressed_chunk) > bytes_restantes:
                                    decompressed_chunk = decompressed_chunk[:bytes_restantes]
                                
                                f_out.write(decompressed_chunk)
                                bytes_escritos += len(decompressed_chunk)
                        except zlib.error as e:
                            raise FileTransferError(f"Error de descompresión: {str(e)}")
            
            return tamaño_original
            
        except Exception as e:
            raise FileTransferError(f"Error descomprimiendo archivo: {str(e)}")


class FileTransferManager:
    """
    Gestor principal de transferencias de archivos.
    
    Maneja múltiples transferencias concurrentes con protocolo robusto.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Inicializa el gestor de transferencias.
        
        Args:
            config_manager: Gestor de configuración del sistema
        """
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Estado del gestor
        self.transferencias_activas: Dict[str, InfoTransferencia] = {}
        self.historial_transferencias: List[InfoTransferencia] = []
        self.cola_transferencias = Queue()
        
        # Callbacks
        self.callback_progreso: Optional[Callable[[InfoTransferencia], None]] = None
        self.callback_completada: Optional[Callable[[InfoTransferencia], None]] = None
        self.callback_error: Optional[Callable[[InfoTransferencia, Exception], None]] = None
        
        # Control de hilos
        self.ejecutando = False
        self.hilo_procesador: Optional[threading.Thread] = None
        
        # Estadísticas
        self.transferencias_exitosas = 0
        self.transferencias_fallidas = 0
        self.bytes_totales_transferidos = 0
        
        # Locks
        self.lock_transferencias = threading.Lock()
        
        # Directorio temporal
        self.directorio_temp = Path(self.config.sistema.directorio_temp)
        self.directorio_temp.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("FileTransferManager inicializado")
    
    def iniciar(self):
        """Inicia el gestor de transferencias."""
        if self.ejecutando:
            self.logger.warning("Gestor de transferencias ya está ejecutándose")
            return
        
        self.ejecutando = True
        self.hilo_procesador = threading.Thread(target=self._bucle_procesador, daemon=True)
        self.hilo_procesador.start()
        
        self.logger.info("Gestor de transferencias iniciado")
    
    def detener(self):
        """Detiene el gestor de transferencias."""
        self.logger.info("Deteniendo gestor de transferencias...")
        
        self.ejecutando = False
        
        # Cancelar transferencias activas
        with self.lock_transferencias:
            for transferencia in self.transferencias_activas.values():
                if transferencia.estado not in [EstadoTransferencia.COMPLETADA, 
                                               EstadoTransferencia.ERROR,
                                               EstadoTransferencia.CANCELADA]:
                    transferencia.estado = EstadoTransferencia.CANCELADA
        
        # Esperar que termine el hilo procesador
        if self.hilo_procesador and self.hilo_procesador.is_alive():
            self.hilo_procesador.join(timeout=5.0)
        
        self.logger.info("Gestor de transferencias detenido")
    
    def programar_envio(self, archivo_origen: str, conexion_uart, 
                       nombre_destino: str = None) -> str:
        """
        Programa el envío de un archivo.
        
        Args:
            archivo_origen: Ruta del archivo a enviar
            conexion_uart: Conexión UART para envío
            nombre_destino: Nombre del archivo en destino (opcional)
            
        Returns:
            str: ID de la transferencia
        """
        try:
            archivo_path = Path(archivo_origen)
            
            if not archivo_path.exists():
                raise FileNotFoundError(str(archivo_path))
            
            # Generar ID único
            import uuid
            id_transferencia = str(uuid.uuid4())[:8]
            
            # Información del archivo
            tamaño_archivo = archivo_path.stat().st_size
            nombre_archivo = nombre_destino or archivo_path.name
            
            # Crear info de transferencia
            info = InfoTransferencia(
                id_transferencia=id_transferencia,
                tipo=TipoTransferencia.ENVIO,
                archivo_origen=str(archivo_path),
                archivo_destino=nombre_archivo,
                tamaño_total=tamaño_archivo,
                estado=EstadoTransferencia.PENDIENTE,
                compresion_habilitada=self.config.transferencia.compresion_habilitada
            )
            
            # Agregar a transferencias activas
            with self.lock_transferencias:
                self.transferencias_activas[id_transferencia] = info
            
            # Agregar a cola de procesamiento
            self.cola_transferencias.put({
                'id': id_transferencia,
                'tipo': 'envio',
                'conexion': conexion_uart
            })
            
            self.logger.info(f"Transferencia programada: {id_transferencia} - {archivo_origen}")
            return id_transferencia
            
        except Exception as e:
            self.logger.error(f"Error programando envío: {e}")
            raise
    
    def _bucle_procesador(self):
        """Bucle principal de procesamiento de transferencias."""
        self.logger.debug("Iniciando bucle procesador de transferencias")
        
        while self.ejecutando:
            try:
                # Obtener tarea de la cola
                try:
                    tarea = self.cola_transferencias.get(timeout=1.0)
                except Empty:
                    continue
                
                # Procesar tarea
                try:
                    self._procesar_tarea(tarea)
                except Exception as e:
                    self.logger.error(f"Error procesando tarea: {e}")
                finally:
                    self.cola_transferencias.task_done()
                
            except Exception as e:
                self.logger.error(f"Error en bucle procesador: {e}")
                time.sleep(1.0)
    
    def _procesar_tarea(self, tarea: Dict[str, Any]):
        """
        Procesa una tarea de transferencia.
        
        Args:
            tarea: Información de la tarea
        """
        id_transferencia = tarea['id']
        tipo_tarea = tarea['tipo']
        
        with self.lock_transferencias:
            if id_transferencia not in self.transferencias_activas:
                self.logger.error(f"Transferencia no encontrada: {id_transferencia}")
                return
            
            info = self.transferencias_activas[id_transferencia]
        
        try:
            if tipo_tarea == 'envio':
                self._ejecutar_envio(info, tarea['conexion'])
            else:
                self.logger.error(f"Tipo de tarea no soportado: {tipo_tarea}")
                
        except Exception as e:
            self._manejar_error_transferencia(info, e)
    
    def _ejecutar_envio(self, info: InfoTransferencia, conexion_uart):
        """
        Ejecuta el envío de un archivo.
        
        Args:
            info: Información de la transferencia
            conexion_uart: Conexión UART
        """
        try:
            info.estado = EstadoTransferencia.INICIANDO
            info.tiempo_inicio = time.time()
            
            archivo_origen = Path(info.archivo_origen)
            
            # Preparar archivo para envío
            archivo_a_enviar, es_temporal = self._preparar_archivo_envio(archivo_origen, info)
            
            try:
                # Calcular checksum del archivo a enviar
                info.checksum_origen = self._calcular_checksum(archivo_a_enviar)
                
                # Enviar header
                self._enviar_header(info, archivo_a_enviar, conexion_uart)
                
                # Transferir archivo
                self._transferir_archivo(info, archivo_a_enviar, conexion_uart)
                
                # Verificar integridad
                if self.config.transferencia.verificar_checksum:
                    self._verificar_integridad(info, conexion_uart)
                
                # Marcar como completada
                info.estado = EstadoTransferencia.COMPLETADA
                info.tiempo_transcurrido = time.time() - info.tiempo_inicio
                
                # Actualizar estadísticas
                self.transferencias_exitosas += 1
                self.bytes_totales_transferidos += info.tamaño_total
                
                # Callback de completada
                if self.callback_completada:
                    self.callback_completada(info)
                
                self.logger.info(f"Transferencia completada: {info.id_transferencia}")
                
            finally:
                # Limpiar archivo temporal si se creó
                if es_temporal and archivo_a_enviar.exists():
                    try:
                        archivo_a_enviar.unlink()
                    except Exception as e:
                        self.logger.warning(f"Error eliminando archivo temporal: {e}")
        
        except Exception as e:
            self._manejar_error_transferencia(info, e)
        finally:
            # Mover a historial
            self._mover_a_historial(info)
    
    def _preparar_archivo_envio(self, archivo_origen: Path, 
                               info: InfoTransferencia) -> Tuple[Path, bool]:
        """
        Prepara archivo para envío (compresión si está habilitada).
        
        Args:
            archivo_origen: Archivo original
            info: Información de transferencia
            
        Returns:
            Tuple[Path, bool]: (archivo_preparado, es_temporal)
        """
        if not info.compresion_habilitada:
            return archivo_origen, False
        
        try:
            # Crear archivo temporal comprimido
            archivo_temp = self.directorio_temp / f"{info.id_transferencia}_compressed.tmp"
            
            # Comprimir archivo
            tamaño_original, tamaño_comprimido = CompresorArchivos.comprimir_archivo(
                archivo_origen, 
                archivo_temp, 
                self.config.transferencia.compresion_nivel
            )
            
            info.tamaño_comprimido = tamaño_comprimido
            
            self.logger.debug(f"Archivo comprimido: {tamaño_original} -> {tamaño_comprimido} bytes "
                            f"(ratio: {info.ratio_compresion:.2f})")
            
            return archivo_temp, True
            
        except Exception as e:
            self.logger.warning(f"Error comprimiendo archivo, enviando sin comprimir: {e}")
            info.compresion_habilitada = False
            return archivo_origen, False
    
    def _enviar_header(self, info: InfoTransferencia, archivo: Path, conexion_uart):
        """
        Envía header de transferencia.
        
        Args:
            info: Información de transferencia
            archivo: Archivo a transferir
            conexion_uart: Conexión UART
        """
        info.estado = EstadoTransferencia.ENVIANDO_HEADER
        
        tamaño_envio = info.tamaño_comprimido if info.compresion_habilitada else info.tamaño_total
        
        header = ProtocoloTransferencia.crear_header(
            info.archivo_destino,
            info.tamaño_total,
            info.checksum_origen,
            info.compresion_habilitada,
            tamaño_envio
        )
        
        if not conexion_uart.enviar_mensaje(header.rstrip()):
            raise FileTransferError("No se pudo enviar header", info.archivo_origen)
        
        # Esperar confirmación
        info.estado = EstadoTransferencia.ESPERANDO_CONFIRMACION
        if not self._esperar_confirmacion(conexion_uart, ProtocoloTransferencia.READY_MSG):
            raise FileTransferTimeoutError(info.archivo_origen, 0, info.tamaño_total)
    
    def _transferir_archivo(self, info: InfoTransferencia, archivo: Path, conexion_uart):
        """
        Transfiere el archivo por chunks.
        
        Args:
            info: Información de transferencia
            archivo: Archivo a transferir
            conexion_uart: Conexión UART
        """
        info.estado = EstadoTransferencia.TRANSFIRIENDO
        
        tamaño_archivo = archivo.stat().st_size
        chunk_size = self.config.transferencia.chunk_size
        chunks_totales = (tamaño_archivo + chunk_size - 1) // chunk_size
        
        info.chunks_totales = chunks_totales
        
        with open(archivo, 'rb') as f:
            for chunk_num in range(chunks_totales):
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break
                
                # Enviar chunk con reintentos
                chunk_enviado = False
                for intento in range(self.config.transferencia.max_reintentos):
                    try:
                        if self._enviar_chunk(chunk_data, chunk_num, conexion_uart):
                            chunk_enviado = True
                            break
                    except Exception as e:
                        self.logger.warning(f"Intento {intento + 1} fallido para chunk {chunk_num}: {e}")
                        time.sleep(0.5)
                
                if not chunk_enviado:
                    raise FileTransferError(f"No se pudo enviar chunk {chunk_num}", info.archivo_origen)
                
                # Actualizar progreso
                info.progreso_bytes += len(chunk_data)
                info.progreso_chunks += 1
                info.tiempo_transcurrido = time.time() - info.tiempo_inicio
                
                if info.tiempo_transcurrido > 0:
                    info.velocidad_bps = info.progreso_bytes / info.tiempo_transcurrido
                
                # Callback de progreso
                if self.callback_progreso:
                    self.callback_progreso(info)
    
    def _enviar_chunk(self, data: bytes, chunk_num: int, conexion_uart) -> bool:
        """
        Envía un chunk de datos.
        
        Args:
            data: Datos del chunk
            chunk_num: Número del chunk
            conexion_uart: Conexión UART
            
        Returns:
            bool: True si el chunk fue enviado y confirmado
        """
        try:
            # Enviar datos
            if not conexion_uart.conexion or not conexion_uart.conexion.is_open:
                return False
            
            with conexion_uart.lock:
                bytes_enviados = conexion_uart.conexion.write(data)
                conexion_uart.conexion.flush()
                
                conexion_uart.bytes_enviados += bytes_enviados
                conexion_uart.ultima_actividad = time.time()
            
            # Esperar ACK
            return self._esperar_confirmacion(
                conexion_uart, 
                ProtocoloTransferencia.ACK_MSG,
                self.config.transferencia.timeout_chunk
            )
            
        except Exception as e:
            self.logger.error(f"Error enviando chunk {chunk_num}: {e}")
            return False
    
    def _verificar_integridad(self, info: InfoTransferencia, conexion_uart):
        """
        Verifica la integridad del archivo transferido.
        
        Args:
            info: Información de transferencia
            conexion_uart: Conexión UART
        """
        info.estado = EstadoTransferencia.VERIFICANDO
        
        # Enviar solicitud de verificación
        verify_msg = f"{ProtocoloTransferencia.VERIFY_MSG}|{info.checksum_origen}"
        if not conexion_uart.enviar_mensaje(verify_msg):
            raise FileTransferError("No se pudo enviar solicitud de verificación")
        
        # Esperar confirmación de integridad
        if not self._esperar_confirmacion(conexion_uart, ProtocoloTransferencia.DONE_MSG, 30.0):
            raise FileTransferChecksumError(
                info.archivo_origen,
                info.checksum_origen,
                "No se recibió confirmación de integridad"
            )
    
    def _esperar_confirmacion(self, conexion_uart, confirmacion_esperada: str, 
                             timeout: float = 10.0) -> bool:
        """
        Espera una confirmación específica.
        
        Args:
            conexion_uart: Conexión UART
            confirmacion_esperada: Mensaje esperado
            timeout: Timeout en segundos
            
        Returns:
            bool: True si se recibió la confirmación
        """
        inicio = time.time()
        buffer_temp = ""
        
        while (time.time() - inicio) < timeout:
            try:
                if conexion_uart.conexion and conexion_uart.conexion.in_waiting > 0:
                    data = conexion_uart.conexion.read(conexion_uart.conexion.in_waiting)
                    buffer_temp += data.decode('utf-8', errors='ignore')
                    
                    # Buscar confirmación
                    if confirmacion_esperada.upper() in buffer_temp.upper():
                        return True
                    
                    # Verificar si hay error
                    if ProtocoloTransferencia.ERROR_MSG in buffer_temp.upper():
                        return False
                
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error esperando confirmación: {e}")
                break
        
        return False
    
    def _calcular_checksum(self, archivo: Path) -> str:
        """
        Calcula checksum MD5 de un archivo.
        
        Args:
            archivo: Archivo a procesar
            
        Returns:
            str: Checksum MD5
        """
        hash_md5 = hashlib.md5()
        
        with open(archivo, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()
    
    def _manejar_error_transferencia(self, info: InfoTransferencia, error: Exception):
        """
        Maneja errores en transferencias.
        
        Args:
            info: Información de transferencia
            error: Error ocurrido
        """
        info.estado = EstadoTransferencia.ERROR
        info.error_mensaje = str(error)
        info.tiempo_transcurrido = time.time() - info.tiempo_inicio if info.tiempo_inicio > 0 else 0
        
        self.transferencias_fallidas += 1
        
        # Callback de error
        if self.callback_error:
            self.callback_error(info, error)
        
        self.logger.error(f"Error en transferencia {info.id_transferencia}: {error}")
    
    def _mover_a_historial(self, info: InfoTransferencia):
        """
        Mueve transferencia completada al historial.
        
        Args:
            info: Información de transferencia
        """
        with self.lock_transferencias:
            if info.id_transferencia in self.transferencias_activas:
                del self.transferencias_activas[info.id_transferencia]
            
            self.historial_transferencias.append(info)
            
            # Mantener historial limitado
            max_historial = 100
            if len(self.historial_transferencias) > max_historial:
                self.historial_transferencias = self.historial_transferencias[-max_historial:]
    
    def cancelar_transferencia(self, id_transferencia: str) -> bool:
        """
        Cancela una transferencia activa.
        
        Args:
            id_transferencia: ID de la transferencia a cancelar
            
        Returns:
            bool: True si la transferencia fue cancelada
        """
        with self.lock_transferencias:
            if id_transferencia not in self.transferencias_activas:
                return False
            
            info = self.transferencias_activas[id_transferencia]
            
            if info.estado in [EstadoTransferencia.COMPLETADA, 
                              EstadoTransferencia.ERROR,
                              EstadoTransferencia.CANCELADA]:
                return False
            
            info.estado = EstadoTransferencia.CANCELADA
            info.tiempo_transcurrido = time.time() - info.tiempo_inicio if info.tiempo_inicio > 0 else 0
            
            self.logger.info(f"Transferencia cancelada: {id_transferencia}")
            return True
    
    def obtener_transferencia(self, id_transferencia: str) -> Optional[InfoTransferencia]:
        """
        Obtiene información de una transferencia específica.
        
        Args:
            id_transferencia: ID de la transferencia
            
        Returns:
            InfoTransferencia o None si no existe
        """
        with self.lock_transferencias:
            # Buscar en transferencias activas
            if id_transferencia in self.transferencias_activas:
                return self.transferencias_activas[id_transferencia]
            
            # Buscar en historial
            for transferencia in self.historial_transferencias:
                if transferencia.id_transferencia == id_transferencia:
                    return transferencia
            
            return None
    
    def listar_transferencias_activas(self) -> List[InfoTransferencia]:
        """
        Lista todas las transferencias activas.
        
        Returns:
            List[InfoTransferencia]: Lista de transferencias activas
        """
        with self.lock_transferencias:
            return list(self.transferencias_activas.values())
    
    def listar_historial(self, cantidad: int = 50) -> List[InfoTransferencia]:
        """
        Lista el historial de transferencias.
        
        Args:
            cantidad: Número máximo de transferencias a retornar
            
        Returns:
            List[InfoTransferencia]: Lista de transferencias históricas
        """
        with self.lock_transferencias:
            return self.historial_transferencias[-cantidad:]
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del gestor de transferencias.
        
        Returns:
            Dict con estadísticas completas
        """
        with self.lock_transferencias:
            transferencias_activas = len(self.transferencias_activas)
            
            # Calcular estadísticas de velocidad
            velocidades = []
            for info in self.historial_transferencias:
                if info.estado == EstadoTransferencia.COMPLETADA and info.velocidad_bps > 0:
                    velocidades.append(info.velocidad_bps)
            
            velocidad_promedio = sum(velocidades) / len(velocidades) if velocidades else 0
            velocidad_maxima = max(velocidades) if velocidades else 0
            
            return {
                'transferencias_activas': transferencias_activas,
                'transferencias_exitosas': self.transferencias_exitosas,
                'transferencias_fallidas': self.transferencias_fallidas,
                'bytes_totales_transferidos': self.bytes_totales_transferidos,
                'historial_total': len(self.historial_transferencias),
                'velocidad_promedio_bps': velocidad_promedio,
                'velocidad_maxima_bps': velocidad_maxima,
                'tasa_exito': (self.transferencias_exitosas / 
                              max(1, self.transferencias_exitosas + self.transferencias_fallidas)) * 100
            }
    
    def limpiar_historial(self):
        """Limpia el historial de transferencias."""
        with self.lock_transferencias:
            self.historial_transferencias.clear()
            self.logger.info("Historial de transferencias limpiado")
    
    def exportar_estadisticas(self, archivo_destino: str) -> bool:
        """
        Exporta estadísticas y historial a archivo JSON.
        
        Args:
            archivo_destino: Ruta del archivo de destino
            
        Returns:
            bool: True si la exportación fue exitosa
        """
        try:
            from datetime import datetime
            
            data = {
                'metadata': {
                    'version': '1.0',
                    'exportado': datetime.now().isoformat(),
                    'configuracion': self.config.transferencia.to_dict()
                },
                'estadisticas': self.obtener_estadisticas(),
                'transferencias_activas': [info.to_dict() for info in self.listar_transferencias_activas()],
                'historial': [info.to_dict() for info in self.historial_transferencias]
            }
            
            with open(archivo_destino, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Estadísticas exportadas a: {archivo_destino}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exportando estadísticas: {e}")
            return False
    
    def establecer_callbacks(self, 
                           callback_progreso: Optional[Callable[[InfoTransferencia], None]] = None,
                           callback_completada: Optional[Callable[[InfoTransferencia], None]] = None,
                           callback_error: Optional[Callable[[InfoTransferencia, Exception], None]] = None):
        """
        Establece callbacks para eventos de transferencia.
        
        Args:
            callback_progreso: Callback para progreso de transferencia
            callback_completada: Callback para transferencia completada
            callback_error: Callback para errores de transferencia
        """
        if callback_progreso:
            self.callback_progreso = callback_progreso
        if callback_completada:
            self.callback_completada = callback_completada
        if callback_error:
            self.callback_error = callback_error
    
    def verificar_espacio_temporal(self, tamaño_requerido: int) -> bool:
        """
        Verifica si hay suficiente espacio en directorio temporal.
        
        Args:
            tamaño_requerido: Espacio requerido en bytes
            
        Returns:
            bool: True si hay suficiente espacio
        """
        try:
            import shutil
            espacio_libre = shutil.disk_usage(self.directorio_temp).free
            return espacio_libre >= tamaño_requerido
        except Exception as e:
            self.logger.error(f"Error verificando espacio temporal: {e}")
            return False
    
    def limpiar_archivos_temporales(self) -> Dict[str, int]:
        """
        Limpia archivos temporales antiguos.
        
        Returns:
            Dict con estadísticas de limpieza
        """
        archivos_eliminados = 0
        bytes_liberados = 0
        errores = 0
        
        try:
            # Buscar archivos temporales
            for archivo in self.directorio_temp.glob("*.tmp"):
                try:
                    # Eliminar archivos temporales de más de 1 hora
                    tiempo_archivo = archivo.stat().st_mtime
                    if time.time() - tiempo_archivo > 3600:  # 1 hora
                        tamaño = archivo.stat().st_size
                        archivo.unlink()
                        archivos_eliminados += 1
                        bytes_liberados += tamaño
                except Exception as e:
                    errores += 1
                    self.logger.warning(f"Error eliminando archivo temporal {archivo}: {e}")
            
            if archivos_eliminados > 0:
                self.logger.info(f"Limpieza temporal: {archivos_eliminados} archivos, {bytes_liberados} bytes")
            
            return {
                'archivos_eliminados': archivos_eliminados,
                'bytes_liberados': bytes_liberados,
                'errores': errores
            }
            
        except Exception as e:
            self.logger.error(f"Error en limpieza de archivos temporales: {e}")
            return {'archivos_eliminados': 0, 'bytes_liberados': 0, 'errores': 1}


class FileReceiver:
    """
    Receptor de archivos por UART.
    
    Complementa al FileTransferManager para recepción de archivos.
    """
    
    def __init__(self, config_manager: ConfigManager, directorio_destino: str):
        """
        Inicializa el receptor de archivos.
        
        Args:
            config_manager: Gestor de configuración
            directorio_destino: Directorio donde guardar archivos recibidos
        """
        self.config = config_manager
        self.directorio_destino = Path(directorio_destino)
        self.directorio_destino.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        
        # Estado de recepción
        self.recibiendo = False
        self.info_archivo_actual: Optional[Dict[str, Any]] = None
        self.archivo_temporal: Optional[Path] = None
        self.bytes_recibidos = 0
        self.chunks_recibidos = 0
        
        # Callback para progreso
        self.callback_progreso: Optional[Callable[[Dict[str, Any]], None]] = None
        
    def procesar_header(self, header_str: str) -> Dict[str, Any]:
        """
        Procesa header de archivo entrante.
        
        Args:
            header_str: String del header
            
        Returns:
            Dict con respuesta para enviar
        """
        try:
            # Verificar que no hay recepción en progreso
            if self.recibiendo:
                return {
                    'respuesta': ProtocoloTransferencia.ERROR_MSG + "|Recepción ya en progreso",
                    'exito': False
                }
            
            # Parsear header
            info_archivo = ProtocoloTransferencia.parsear_header(header_str)
            
            # Verificar espacio disponible
            tamaño_requerido = info_archivo.get('tamaño_comprimido', info_archivo['tamaño'])
            if not self._verificar_espacio_disponible(tamaño_requerido):
                return {
                    'respuesta': ProtocoloTransferencia.ERROR_MSG + "|Espacio insuficiente",
                    'exito': False
                }
            
            # Preparar recepción
            self.info_archivo_actual = info_archivo
            self.archivo_temporal = self.directorio_destino / f"temp_{info_archivo['nombre_archivo']}"
            self.bytes_recibidos = 0
            self.chunks_recibidos = 0
            self.recibiendo = True
            
            self.logger.info(f"Iniciando recepción: {info_archivo['nombre_archivo']} "
                           f"({info_archivo['tamaño']} bytes)")
            
            return {
                'respuesta': ProtocoloTransferencia.READY_MSG,
                'exito': True
            }
            
        except Exception as e:
            self.logger.error(f"Error procesando header: {e}")
            return {
                'respuesta': ProtocoloTransferencia.ERROR_MSG + f"|{str(e)}",
                'exito': False
            }
    
    def recibir_chunk(self, datos: bytes) -> Dict[str, Any]:
        """
        Recibe un chunk de datos.
        
        Args:
            datos: Datos del chunk
            
        Returns:
            Dict con respuesta
        """
        try:
            if not self.recibiendo or not self.info_archivo_actual:
                return {
                    'respuesta': ProtocoloTransferencia.NACK_MSG,
                    'exito': False
                }
            
            # Escribir datos al archivo temporal
            with open(self.archivo_temporal, 'ab') as f:
                f.write(datos)
            
            self.bytes_recibidos += len(datos)
            self.chunks_recibidos += 1
            
            # Callback de progreso
            if self.callback_progreso:
                progreso = {
                    'archivo': self.info_archivo_actual['nombre_archivo'],
                    'bytes_recibidos': self.bytes_recibidos,
                    'bytes_totales': self.info_archivo_actual.get('tamaño_comprimido', 
                                                                self.info_archivo_actual['tamaño']),
                    'chunks_recibidos': self.chunks_recibidos,
                    'porcentaje': (self.bytes_recibidos / self.info_archivo_actual.get('tamaño_comprimido', 
                                                                                      self.info_archivo_actual['tamaño'])) * 100
                }
                self.callback_progreso(progreso)
            
            return {
                'respuesta': ProtocoloTransferencia.ACK_MSG,
                'exito': True
            }
            
        except Exception as e:
            self.logger.error(f"Error recibiendo chunk: {e}")
            self._limpiar_recepcion()
            return {
                'respuesta': ProtocoloTransferencia.NACK_MSG,
                'exito': False
            }
    
    def finalizar_recepcion(self) -> Dict[str, Any]:
        """
        Finaliza la recepción y verifica el archivo.
        
        Returns:
            Dict con resultado de la finalización
        """
        try:
            if not self.recibiendo or not self.info_archivo_actual:
                return {
                    'respuesta': ProtocoloTransferencia.ERROR_MSG + "|No hay recepción activa",
                    'exito': False
                }
            
            # Procesar archivo recibido
            archivo_final = self.directorio_destino / self.info_archivo_actual['nombre_archivo']
            
            if self.info_archivo_actual.get('comprimido', False):
                # Descomprimir archivo
                CompresorArchivos.descomprimir_archivo(self.archivo_temporal, archivo_final)
                self.archivo_temporal.unlink()  # Eliminar temporal comprimido
            else:
                # Mover archivo temporal a final
                self.archivo_temporal.rename(archivo_final)
            
            # Verificar checksum si está disponible
            if self.config.transferencia.verificar_checksum and self.info_archivo_actual.get('checksum'):
                checksum_calculado = self._calcular_checksum(archivo_final)
                if checksum_calculado != self.info_archivo_actual['checksum']:
                    archivo_final.unlink()  # Eliminar archivo corrupto
                    self._limpiar_recepcion()
                    return {
                        'respuesta': ProtocoloTransferencia.ERROR_MSG + "|Checksum inválido",
                        'exito': False
                    }
            
            self.logger.info(f"Archivo recibido exitosamente: {archivo_final.name}")
            self._limpiar_recepcion()
            
            return {
                'respuesta': ProtocoloTransferencia.DONE_MSG,
                'exito': True,
                'archivo_final': str(archivo_final)
            }
            
        except Exception as e:
            self.logger.error(f"Error finalizando recepción: {e}")
            self._limpiar_recepcion()
            return {
                'respuesta': ProtocoloTransferencia.ERROR_MSG + f"|{str(e)}",
                'exito': False
            }
    
    def cancelar_recepcion(self) -> bool:
        """
        Cancela la recepción actual.
        
        Returns:
            bool: True si se canceló exitosamente
        """
        try:
            if self.recibiendo:
                self._limpiar_recepcion()
                self.logger.info("Recepción cancelada")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error cancelando recepción: {e}")
            return False
    
    def _verificar_espacio_disponible(self, tamaño_requerido: int) -> bool:
        """
        Verifica si hay suficiente espacio disponible.
        
        Args:
            tamaño_requerido: Espacio requerido en bytes
            
        Returns:
            bool: True si hay suficiente espacio
        """
        try:
            import shutil
            espacio_libre = shutil.disk_usage(self.directorio_destino).free
            # Reservar 100MB adicionales como margen de seguridad
            return espacio_libre >= (tamaño_requerido + 100 * 1024 * 1024)
        except Exception:
            return False
    
    def _calcular_checksum(self, archivo: Path) -> str:
        """
        Calcula checksum MD5 de un archivo.
        
        Args:
            archivo: Archivo a procesar
            
        Returns:
            str: Checksum MD5
        """
        hash_md5 = hashlib.md5()
        
        with open(archivo, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()
    
    def _limpiar_recepcion(self):
        """Limpia estado de recepción actual."""
        self.recibiendo = False
        self.info_archivo_actual = None
        self.bytes_recibidos = 0
        self.chunks_recibidos = 0
        
        # Eliminar archivo temporal si existe
        if self.archivo_temporal and self.archivo_temporal.exists():
            try:
                self.archivo_temporal.unlink()
            except Exception as e:
                self.logger.warning(f"Error eliminando archivo temporal: {e}")
        
        self.archivo_temporal = None
    
    def obtener_estado(self) -> Dict[str, Any]:
        """
        Obtiene estado actual del receptor.
        
        Returns:
            Dict con estado del receptor
        """
        estado = {
            'recibiendo': self.recibiendo,
            'directorio_destino': str(self.directorio_destino)
        }
        
        if self.recibiendo and self.info_archivo_actual:
            estado.update({
                'archivo_actual': self.info_archivo_actual['nombre_archivo'],
                'bytes_recibidos': self.bytes_recibidos,
                'bytes_totales': self.info_archivo_actual.get('tamaño_comprimido', 
                                                            self.info_archivo_actual['tamaño']),
                'chunks_recibidos': self.chunks_recibidos,
                'porcentaje_completado': (self.bytes_recibidos / 
                                        self.info_archivo_actual.get('tamaño_comprimido', 
                                                                    self.info_archivo_actual['tamaño'])) * 100
            })
        
        return estado
