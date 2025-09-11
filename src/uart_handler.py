"""
Manejador de comunicación UART para el sistema de cámara.

Este módulo implementa el protocolo de comunicación serie con capacidades
de reconexión automática, manejo de errores y transferencia de archivos.
"""

import serial
import threading
import time
import logging
import hashlib
import os
from typing import Optional, Callable, Dict, Any, List, Tuple
from pathlib import Path
from queue import Queue, Empty
from dataclasses import dataclass
from enum import Enum

from .config_manager import ConfigManager
from .exceptions import (
    UARTError,
    UARTConnectionError, 
    UARTTimeoutError,
    UARTDataError,
    FileTransferError,
    FileNotFoundError,
    FileTransferTimeoutError,
    FileTransferChecksumError
)


class EstadoConexion(Enum):
    """Estados de la conexión UART."""
    DESCONECTADO = "desconectado"
    CONECTANDO = "conectando"
    CONECTADO = "conectado"
    ERROR = "error"
    RECONECTANDO = "reconectando"


@dataclass
class ComandoUART:
    """Estructura para comandos UART."""
    comando: str
    parametros: List[str]
    timestamp: float
    
    @classmethod
    def from_string(cls, linea: str) -> 'ComandoUART':
        """Crea comando desde string recibido."""
        partes = linea.strip().split(':') if ':' in linea else [linea.strip()]
        comando = partes[0].lower()
        parametros = partes[1:] if len(partes) > 1 else []
        
        return cls(
            comando=comando,
            parametros=parametros,
            timestamp=time.time()
        )


@dataclass
class TransferStats:
    """Estadísticas de transferencia de archivos."""
    archivo: str
    bytes_totales: int
    bytes_enviados: int
    chunks_enviados: int
    chunks_totales: int
    inicio: float
    tiempo_transcurrido: float
    velocidad_bps: float
    
    @property
    def porcentaje_completado(self) -> float:
        """Porcentaje de transferencia completado."""
        if self.bytes_totales == 0:
            return 100.0
        return (self.bytes_enviados / self.bytes_totales) * 100.0
    
    @property
    def tiempo_estimado_restante(self) -> float:
        """Tiempo estimado restante en segundos."""
        if self.porcentaje_completado == 0 or self.velocidad_bps == 0:
            return 0.0
        
        bytes_restantes = self.bytes_totales - self.bytes_enviados
        return bytes_restantes / self.velocidad_bps


class UARTHandler:
    """
    Manejador de comunicación UART con protocolo robusto.
    
    Implementa comunicación bidireccional, transferencia de archivos,
    reconexión automática y manejo de errores.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Inicializa el manejador UART.
        
        Args:
            config_manager: Gestor de configuración del sistema
        """
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Estado de conexión
        self.conexion: Optional[serial.Serial] = None
        self.estado = EstadoConexion.DESCONECTADO
        self.ejecutando = False
        self.hilo_lectura: Optional[threading.Thread] = None
        self.hilo_heartbeat: Optional[threading.Thread] = None
        
        # Callbacks para comandos
        self.callbacks_comandos: Dict[str, Callable[[ComandoUART], str]] = {}
        
        # Buffer de comunicación
        self.buffer_entrada = ""
        self.cola_salida = Queue()
        
        # Estadísticas
        self.comandos_procesados = 0
        self.bytes_enviados = 0
        self.bytes_recibidos = 0
        self.ultima_actividad = time.time()
        self.errores_consecutivos = 0
        
        # Configuración de reconexión
        self.max_errores_consecutivos = 5
        self.intervalo_reconexion = 5.0
        self.timeout_reconexion = 30.0
        
        # Lock para operaciones thread-safe
        self.lock = threading.Lock()
        
        self.logger.info(f"UARTHandler inicializado para puerto {self.config.uart.puerto}")
    
    def registrar_comando(self, comando: str, callback: Callable[[ComandoUART], str]):
        """
        Registra un callback para un comando específico.
        
        Args:
            comando: Nombre del comando (ej: 'foto', 'estado')
            callback: Función que procesa el comando y retorna respuesta
        """
        self.callbacks_comandos[comando.lower()] = callback
        self.logger.debug(f"Comando registrado: {comando}")
    
    def conectar(self) -> bool:
        """
        Establece conexión UART.
        
        Returns:
            bool: True si la conexión fue exitosa
        """
        try:
            self.estado = EstadoConexion.CONECTANDO
            self.logger.info(f"Conectando a {self.config.uart.puerto} @ {self.config.uart.baudrate} baudios")
            
            # Cerrar conexión previa si existe
            if self.conexion and self.conexion.is_open:
                self.conexion.close()
            
            # Crear nueva conexión
            self.conexion = serial.Serial(
                port=self.config.uart.puerto,
                baudrate=self.config.uart.baudrate,
                timeout=self.config.uart.timeout,
                bytesize=self.config.uart.bytesize,
                parity=self._convert_parity(self.config.uart.parity),
                stopbits=self.config.uart.stopbits,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            
            # Verificar conexión
            if not self.conexion.is_open:
                raise UARTConnectionError(self.config.uart.puerto, "Puerto no se pudo abrir")
            
            # Limpiar buffers
            self.conexion.flush()
            self.conexion.reset_input_buffer()
            self.conexion.reset_output_buffer()
            
            self.estado = EstadoConexion.CONECTADO
            self.errores_consecutivos = 0
            self.ultima_actividad = time.time()
            
            # Enviar mensaje de inicio
            self.enviar_mensaje("CAMERA_READY")
            
            self.logger.info("Conexión UART establecida exitosamente")
            return True
            
        except serial.SerialException as e:
            self.estado = EstadoConexion.ERROR
            error_msg = f"Error de puerto serie: {str(e)}"
            self.logger.error(error_msg)
            raise UARTConnectionError(self.config.uart.puerto, error_msg)
            
        except Exception as e:
            self.estado = EstadoConexion.ERROR
            error_msg = f"Error inesperado: {str(e)}"
            self.logger.error(error_msg)
            raise UARTConnectionError(self.config.uart.puerto, error_msg)
    
    def desconectar(self):
        """Cierra la conexión UART."""
        try:
            if self.conexion and self.conexion.is_open:
                self.enviar_mensaje("CAMERA_OFFLINE")
                time.sleep(0.1)  # Dar tiempo para enviar el mensaje
                self.conexion.close()
                
            self.estado = EstadoConexion.DESCONECTADO
            self.logger.info("Conexión UART cerrada")
            
        except Exception as e:
            self.logger.error(f"Error al cerrar conexión: {e}")
    
    def iniciar(self):
        """Inicia el sistema de comunicación UART."""
        if self.ejecutando:
            self.logger.warning("Sistema UART ya está ejecutándose")
            return
        
        try:
            # Conectar
            if not self.conectar():
                raise UARTConnectionError(self.config.uart.puerto, "No se pudo establecer conexión inicial")
            
            # Iniciar hilos
            self.ejecutando = True
            
            self.hilo_lectura = threading.Thread(target=self._bucle_lectura, daemon=True)
            self.hilo_lectura.start()
            
            self.hilo_heartbeat = threading.Thread(target=self._bucle_heartbeat, daemon=True)
            self.hilo_heartbeat.start()
            
            self.logger.info("Sistema UART iniciado correctamente")
            
        except Exception as e:
            self.ejecutando = False
            self.logger.error(f"Error al iniciar sistema UART: {e}")
            raise
    
    def detener(self):
        """Detiene el sistema de comunicación UART."""
        self.logger.info("Deteniendo sistema UART...")
        
        self.ejecutando = False
        
        # Esperar que terminen los hilos
        if self.hilo_lectura and self.hilo_lectura.is_alive():
            self.hilo_lectura.join(timeout=5.0)
        
        if self.hilo_heartbeat and self.hilo_heartbeat.is_alive():
            self.hilo_heartbeat.join(timeout=5.0)
        
        # Cerrar conexión
        self.desconectar()
        
        self.logger.info("Sistema UART detenido")
    
    def enviar_mensaje(self, mensaje: str) -> bool:
        """
        Envía mensaje por UART.
        
        Args:
            mensaje: Mensaje a enviar
            
        Returns:
            bool: True si se envió correctamente
        """
        try:
            if not self.conexion or not self.conexion.is_open:
                self.logger.error("Conexión UART no disponible")
                return False
            
            with self.lock:
                # Agregar terminador si no lo tiene
                if not mensaje.endswith(('\r\n', '\n')):
                    mensaje += '\r\n'
                
                # Enviar mensaje
                bytes_enviados = self.conexion.write(mensaje.encode('utf-8'))
                self.conexion.flush()
                
                # Actualizar estadísticas
                self.bytes_enviados += bytes_enviados
                self.ultima_actividad = time.time()
                
                self.logger.debug(f"Enviado: {mensaje.strip()}")
                return True
                
        except serial.SerialException as e:
            self.logger.error(f"Error al enviar mensaje: {e}")
            self._marcar_error_conexion()
            return False
        except Exception as e:
            self.logger.error(f"Error inesperado al enviar: {e}")
            return False
    
    def _bucle_lectura(self):
        """Bucle principal de lectura UART."""
        self.logger.debug("Iniciando bucle de lectura UART")
        
        while self.ejecutando:
            try:
                if not self.conexion or not self.conexion.is_open:
                    self._intentar_reconexion()
                    continue
                
                # Leer datos disponibles
                if self.conexion.in_waiting > 0:
                    data = self.conexion.read(self.conexion.in_waiting)
                    if data:
                        self._procesar_datos_recibidos(data)
                
                time.sleep(0.05)  # Pequeña pausa para no sobrecargar CPU
                
            except serial.SerialException as e:
                self.logger.error(f"Error en bucle de lectura: {e}")
                self._marcar_error_conexion()
                time.sleep(1.0)
                
            except Exception as e:
                self.logger.error(f"Error inesperado en lectura: {e}")
                time.sleep(1.0)
    
    def _procesar_datos_recibidos(self, data: bytes):
        """
        Procesa datos recibidos por UART.
        
        Args:
            data: Bytes recibidos
        """
        try:
            # Decodificar y agregar al buffer
            texto = data.decode('utf-8', errors='ignore')
            self.buffer_entrada += texto
            self.bytes_recibidos += len(data)
            self.ultima_actividad = time.time()
            
            # Procesar líneas completas
            while '\n' in self.buffer_entrada or '\r' in self.buffer_entrada:
                if '\n' in self.buffer_entrada:
                    linea, self.buffer_entrada = self.buffer_entrada.split('\n', 1)
                else:
                    linea, self.buffer_entrada = self.buffer_entrada.split('\r', 1)
                
                linea = linea.strip()
                if linea:
                    self._procesar_comando(linea)
        
        except UnicodeDecodeError as e:
            self.logger.warning(f"Error de decodificación UTF-8: {e}")
        except Exception as e:
            self.logger.error(f"Error procesando datos recibidos: {e}")
    
    def _procesar_comando(self, linea: str):
        """
        Procesa un comando recibido.
        
        Args:
            linea: Línea de comando recibida
        """
        try:
            comando = ComandoUART.from_string(linea)
            self.logger.debug(f"Comando recibido: {comando.comando} {comando.parametros}")
            
            # Buscar callback para el comando
            if comando.comando in self.callbacks_comandos:
                try:
                    respuesta = self.callbacks_comandos[comando.comando](comando)
                    if respuesta:
                        self.enviar_mensaje(respuesta)
                    
                    self.comandos_procesados += 1
                    
                except Exception as e:
                    error_msg = f"ERROR|PROCESSING|Error procesando comando '{comando.comando}': {str(e)}"
                    self.enviar_mensaje(error_msg)
                    self.logger.error(f"Error en callback de comando '{comando.comando}': {e}")
            else:
                # Comando no reconocido
                comandos_disponibles = list(self.callbacks_comandos.keys())
                error_msg = f"ERROR|UNKNOWN_COMMAND|Comando '{comando.comando}' no reconocido. Disponibles: {', '.join(comandos_disponibles)}"
                self.enviar_mensaje(error_msg)
                self.logger.warning(f"Comando no reconocido: {comando.comando}")
        
        except Exception as e:
            self.logger.error(f"Error procesando comando: {e}")
    
    def _bucle_heartbeat(self):
        """Bucle de heartbeat para mantener conexión viva."""
        intervalo = 30.0  # segundos entre heartbeats
        
        while self.ejecutando:
            try:
                time.sleep(intervalo)
                
                if self.ejecutando and self.estado == EstadoConexion.CONECTADO:
                    # Verificar si ha habido actividad reciente
                    tiempo_inactivo = time.time() - self.ultima_actividad
                    
                    if tiempo_inactivo > (intervalo * 2):
                        self.logger.debug("Enviando heartbeat")
                        if not self.enviar_mensaje("HEARTBEAT"):
                            self._marcar_error_conexion()
                
            except Exception as e:
                self.logger.error(f"Error en heartbeat: {e}")
    
    def _marcar_error_conexion(self):
        """Marca error en la conexión para intentar reconexión."""
        self.errores_consecutivos += 1
        self.estado = EstadoConexion.ERROR
        
        if self.errores_consecutivos >= self.max_errores_consecutivos:
            self.logger.warning(f"Demasiados errores consecutivos ({self.errores_consecutivos}), iniciando reconexión")
    
    def _intentar_reconexion(self):
        """Intenta reconectar la conexión UART."""
        if self.estado != EstadoConexion.RECONECTANDO:
            self.estado = EstadoConexion.RECONECTANDO
            self.logger.info("Iniciando proceso de reconexión...")
        
        try:
            # Cerrar conexión actual
            if self.conexion:
                try:
                    self.conexion.close()
                except:
                    pass
            
            # Pausa antes de reconectar
            time.sleep(self.intervalo_reconexion)
            
            # Intentar reconectar
            if self.conectar():
                self.logger.info("Reconexión exitosa")
                return True
            
        except Exception as e:
            self.logger.error(f"Error en reconexión: {e}")
        
        return False
    
    def cambiar_baudrate(self, nuevo_baudrate: int) -> bool:
        """
        Cambia la velocidad UART dinámicamente.
        
        Args:
            nuevo_baudrate: Nueva velocidad en baudios
            
        Returns:
            bool: True si el cambio fue exitoso
        """
        try:
            # Validar velocidad
            if nuevo_baudrate not in self.config.obtener_velocidades_disponibles():
                raise UARTDataError(
                    self.config.uart.puerto,
                    str(nuevo_baudrate),
                    f"Velocidad no válida. Soportadas: {self.config.obtener_velocidades_disponibles()}"
                )
            
            self.logger.info(f"Cambiando velocidad UART de {self.config.uart.baudrate} a {nuevo_baudrate}")
            
            # Enviar notificación antes del cambio
            self.enviar_mensaje(f"OK:Cambiando a {nuevo_baudrate} en 3 segundos")
            time.sleep(1.0)
            
            # Actualizar configuración
            self.config.actualizar_baudrate(nuevo_baudrate)
            
            # Reconectar con nueva velocidad
            self.desconectar()
            time.sleep(2.0)
            
            if self.conectar():
                self.enviar_mensaje(f"BAUDRATE_CHANGED|{nuevo_baudrate}")
                self.logger.info(f"Velocidad UART cambiada exitosamente a {nuevo_baudrate}")
                return True
            else:
                self.logger.error("No se pudo reconectar con nueva velocidad")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cambiando velocidad UART: {e}")
            return False
    
    def transferir_archivo(self, ruta_archivo: str, callback_progreso: Optional[Callable[[TransferStats], None]] = None) -> bool:
        """
        Transfiere un archivo por UART usando protocolo de chunks.
        
        Args:
            ruta_archivo: Ruta del archivo a transferir
            callback_progreso: Función llamada para reportar progreso
            
        Returns:
            bool: True si la transferencia fue exitosa
        """
        archivo_path = Path(ruta_archivo)
        
        if not archivo_path.exists():
            raise FileNotFoundError(str(archivo_path))
        
        try:
            # Información del archivo
            tamaño_archivo = archivo_path.stat().st_size
            nombre_archivo = archivo_path.name
            chunk_size = self.config.transferencia.chunk_size
            chunks_totales = (tamaño_archivo + chunk_size - 1) // chunk_size
            
            # Calcular checksum si está habilitado
            checksum = ""
            if self.config.transferencia.verificar_checksum:
                checksum = self._calcular_checksum(archivo_path)
            
            self.logger.info(f"Iniciando transferencia de {nombre_archivo} ({tamaño_archivo} bytes, {chunks_totales} chunks)")
            
            # Enviar header de transferencia
            header = f"FILE|{nombre_archivo}|{tamaño_archivo}"
            if checksum:
                header += f"|{checksum}"
            
            if not self.enviar_mensaje(header):
                raise FileTransferError("No se pudo enviar header de transferencia", nombre_archivo)
            
            # Esperar confirmación
            if not self._esperar_confirmacion("READY", timeout=10.0):
                raise FileTransferTimeoutError(nombre_archivo, 0, tamaño_archivo)
            
            # Estadísticas de transferencia
            stats = TransferStats(
                archivo=nombre_archivo,
                bytes_totales=tamaño_archivo,
                bytes_enviados=0,
                chunks_enviados=0,
                chunks_totales=chunks_totales,
                inicio=time.time(),
                tiempo_transcurrido=0.0,
                velocidad_bps=0.0
            )
            
            # Transferir archivo por chunks
            with open(archivo_path, 'rb') as f:
                for chunk_num in range(chunks_totales):
                    chunk_data = f.read(chunk_size)
                    if not chunk_data:
                        break
                    
                    # Intentar enviar chunk con reintentos
                    chunk_enviado = False
                    for intento in range(self.config.transferencia.max_reintentos):
                        if self._enviar_chunk(chunk_data, chunk_num, chunks_totales):
                            chunk_enviado = True
                            break
                        else:
                            self.logger.warning(f"Reintento {intento + 1} para chunk {chunk_num}")
                            time.sleep(0.5)
                    
                    if not chunk_enviado:
                        raise FileTransferError(f"No se pudo enviar chunk {chunk_num}", nombre_archivo)
                    
                    # Actualizar estadísticas
                    stats.bytes_enviados += len(chunk_data)
                    stats.chunks_enviados += 1
                    stats.tiempo_transcurrido = time.time() - stats.inicio
                    
                    if stats.tiempo_transcurrido > 0:
                        stats.velocidad_bps = stats.bytes_enviados / stats.tiempo_transcurrido
                    
                    # Callback de progreso
                    if callback_progreso:
                        callback_progreso(stats)
            
            # Esperar confirmación final
            if not self._esperar_confirmacion("DONE", timeout=10.0):
                self.logger.warning("No se recibió confirmación final, pero transferencia aparentemente completa")
            
            self.logger.info(f"Transferencia de {nombre_archivo} completada exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error en transferencia de archivo: {e}")
            raise
    
    def _enviar_chunk(self, data: bytes, chunk_num: int, total_chunks: int) -> bool:
        """
        Envía un chunk de datos.
        
        Args:
            data: Datos del chunk
            chunk_num: Número del chunk
            total_chunks: Total de chunks
            
        Returns:
            bool: True si el chunk fue enviado y confirmado
        """
        try:
            # Enviar datos del chunk
            if not self.conexion or not self.conexion.is_open:
                return False
            
            with self.lock:
                bytes_enviados = self.conexion.write(data)
                self.conexion.flush()
                
                self.bytes_enviados += bytes_enviados
                self.ultima_actividad = time.time()
            
            # Esperar ACK
            return self._esperar_confirmacion("ACK", timeout=self.config.transferencia.timeout_chunk)
            
        except Exception as e:
            self.logger.error(f"Error enviando chunk {chunk_num}: {e}")
            return False
    
    def _esperar_confirmacion(self, confirmacion_esperada: str, timeout: float = 5.0) -> bool:
        """
        Espera una confirmación específica.
        
        Args:
            confirmacion_esperada: Texto de confirmación esperado
            timeout: Timeout en segundos
            
        Returns:
            bool: True si se recibió la confirmación
        """
        inicio = time.time()
        buffer_temp = ""
        
        while (time.time() - inicio) < timeout:
            try:
                if self.conexion and self.conexion.in_waiting > 0:
                    data = self.conexion.read(self.conexion.in_waiting)
                    buffer_temp += data.decode('utf-8', errors='ignore')
                    
                    # Buscar confirmación en el buffer
                    if confirmacion_esperada.upper() in buffer_temp.upper():
                        return True
                
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error esperando confirmación: {e}")
                break
        
        return False
    
    def _calcular_checksum(self, archivo_path: Path) -> str:
        """
        Calcula checksum MD5 de un archivo.
        
        Args:
            archivo_path: Ruta del archivo
            
        Returns:
            str: Checksum MD5 en hexadecimal
        """
        hash_md5 = hashlib.md5()
        
        with open(archivo_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()
    
    def _convert_parity(self, parity_str: str) -> str:
        """
        Convierte string de paridad a constante serial.
        
        Args:
            parity_str: 'N', 'E', 'O'
            
        Returns:
            str: Constante de paridad para pyserial
        """
        parity_map = {
            'N': serial.PARITY_NONE,
            'E': serial.PARITY_EVEN,
            'O': serial.PARITY_ODD
        }
        return parity_map.get(parity_str.upper(), serial.PARITY_NONE)
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de la conexión UART.
        
        Returns:
            Dict con estadísticas del sistema
        """
        tiempo_activo = time.time() - self.ultima_actividad if self.ultima_actividad else 0
        
        return {
            'estado': self.estado.value,
            'puerto': self.config.uart.puerto,
            'baudrate': self.config.uart.baudrate,
            'comandos_procesados': self.comandos_procesados,
            'bytes_enviados': self.bytes_enviados,
            'bytes_recibidos': self.bytes_recibidos,
            'errores_consecutivos': self.errores_consecutivos,
            'tiempo_inactivo': tiempo_activo,
            'conexion_activa': self.conexion is not None and self.conexion.is_open
        }
    
    def __del__(self):
        """Destructor para limpiar recursos."""
        try:
            self.detener()
        except:
            pass
