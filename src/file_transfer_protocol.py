# file_transfer_protocol_fixed.py
import time
import threading
from pathlib import Path
from queue import Queue, Empty

CHUNK_SIZE = 256

class FileTransferProtocol:
    def __init__(self, uart_handler, logger=None):
        self.uart = uart_handler
        self.logger = logger
        # Cola para respuestas de control
        self.respuestas_control = Queue()
        self.transfer_lock = threading.Lock()

    def enviar_archivo(self, ruta_archivo: str) -> bool:
        """Implementa el protocolo de transferencia chunked con ACK/DONE corregido"""
        archivo = Path(ruta_archivo)
        if not archivo.exists():
            self.uart.enviar_mensaje(f"ERROR|FILE_NOT_FOUND|{archivo.name}")
            return False

        with self.transfer_lock:  # Evitar transferencias concurrentes
            return self._enviar_archivo_interno(archivo)

    def _enviar_archivo_interno(self, archivo: Path) -> bool:
        """Implementación interna de transferencia"""
        tamaño = archivo.stat().st_size
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        try:
            # Paso 1: Limpiar cola de respuestas
            self._limpiar_cola_respuestas()
            
            # Paso 2: Enviar header
            header = f"TRANSFER_START|{timestamp}|{tamaño}"
            self.uart.enviar_mensaje(header)
            if self.logger:
                self.logger.info(f"Header enviado: {header}")

            # Paso 3: Esperar READY con timeout mejorado
            if not self._esperar_respuesta_control("READY", timeout=10.0):
                self._error("READY no recibido en tiempo")
                return False

            # Paso 4: Enviar chunks con verificación robusta
            with open(archivo, "rb") as f:
                chunk_num = 0
                bytes_enviados = 0
                
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    
                    # Enviar chunk con número de secuencia
                    if not self._enviar_chunk_con_verificacion(chunk, chunk_num):
                        self._error(f"Error enviando chunk {chunk_num}")
                        return False
                    
                    bytes_enviados += len(chunk)
                    chunk_num += 1
                    
                    if self.logger and chunk_num % 50 == 0:
                        progreso = (bytes_enviados / tamaño) * 100
                        self.logger.debug(f"Progreso: {progreso:.1f}% ({chunk_num} chunks)")

            # Paso 5: Esperar DONE final
            if not self._esperar_respuesta_control("DONE", timeout=10.0):
                self._error("DONE no recibido")
                return False

            # Paso 6: Confirmar fin exitoso
            self.uart.enviar_mensaje("TRANSFER_OK")
            if self.logger:
                self.logger.info(f"Transferencia completada: {archivo.name} ({tamaño} bytes)")
            return True

        except Exception as e:
            self._error(f"Excepción durante transferencia: {e}")
            return False

    def _enviar_chunk_con_verificacion(self, chunk: bytes, chunk_num: int) -> bool:
        """Envía un chunk con verificación y reintentos"""
        MAX_REINTENTOS = 3
        
        for intento in range(MAX_REINTENTOS):
            try:
                # Enviar header del chunk
                chunk_header = f"CHUNK|{chunk_num}|{len(chunk)}"
                self.uart.enviar_mensaje(chunk_header)
                
                # Esperar confirmación de header
                if not self._esperar_respuesta_control("CHUNK_READY", timeout=5.0):
                    if intento < MAX_REINTENTOS - 1:
                        self.logger.warning(f"Reintentando chunk {chunk_num} (intento {intento + 1})")
                        time.sleep(0.5)
                        continue
                    return False
                
                # Enviar datos binarios
                self.uart.conexion.write(chunk)
                self.uart.conexion.flush()
                
                # Esperar ACK
                if self._esperar_respuesta_control("ACK", timeout=5.0):
                    return True
                
                if intento < MAX_REINTENTOS - 1:
                    self.logger.warning(f"ACK no recibido para chunk {chunk_num}, reintentando...")
                    time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error enviando chunk {chunk_num}: {e}")
                if intento == MAX_REINTENTOS - 1:
                    return False
                time.sleep(1.0)
        
        return False

    def _esperar_respuesta_control(self, esperado: str, timeout: float = 5.0) -> bool:
        """Espera respuesta usando cola dedicada - SIN busy waiting"""
        inicio = time.time()
        
        while time.time() - inicio < timeout:
            try:
                # Usar timeout corto para permitir verificación de tiempo
                respuesta = self.respuestas_control.get(timeout=0.1)
                
                if respuesta.strip() == esperado:
                    return True
                else:
                    # Respuesta inesperada
                    self.logger.warning(f"Respuesta inesperada: esperaba '{esperado}', recibido '{respuesta}'")
                    
            except Empty:
                continue  # Timeout de cola, continuar esperando
        
        self.logger.error(f"Timeout esperando '{esperado}' ({timeout}s)")
        return False

    def _limpiar_cola_respuestas(self):
        """Limpia la cola de respuestas antes de iniciar transferencia"""
        while not self.respuestas_control.empty():
            try:
                self.respuestas_control.get_nowait()
            except Empty:
                break

    def procesar_mensaje_control(self, mensaje: str):
        """Método para que el UART handler inyecte mensajes de control"""
        # Filtrar solo mensajes de transferencia
        mensajes_transferencia = ["READY", "CHUNK_READY", "ACK", "DONE", "NACK", "ERROR"]
        
        mensaje_clean = mensaje.strip()
        for msg_tipo in mensajes_transferencia:
            if mensaje_clean == msg_tipo or mensaje_clean.startswith(f"{msg_tipo}|"):
                self.respuestas_control.put(mensaje_clean)
                break

    def _error(self, msg):
        """Log de error y notificación al cliente"""
        if self.logger:
            self.logger.error(f"Transfer error: {msg}")
        self.uart.enviar_mensaje(f"ERROR|TRANSFER|{msg}")

# CLASE AUXILIAR: Manejador UART Mejorado para Transferencias
class UARTHandlerWithTransfer:
    """Extensión del UARTHandler que separa control y datos binarios"""
    
    def __init__(self, uart_handler_original):
        self.uart_original = uart_handler_original
        self.transfer_protocol = None
        
    def configurar_transferencia(self, logger=None):
        """Configura el protocolo de transferencia"""
        self.transfer_protocol = FileTransferProtocol(self.uart_original, logger)
        
        # Interceptar mensajes de control para transferencias
        self._hook_mensaje_processor()
        
    def _hook_mensaje_processor(self):
        """Intercepta el procesador de mensajes original"""
        original_procesar = self.uart_original._procesar_datos_recibidos
        
        def procesar_con_transferencia(data: bytes):
            # Procesar normalmente
            original_procesar(data)
            
            # Si hay transferencia activa, procesar mensajes de control
            if self.transfer_protocol:
                try:
                    texto = data.decode('utf-8', errors='ignore')
                    for linea in texto.split('\n'):
                        if linea.strip():
                            self.transfer_protocol.procesar_mensaje_control(linea.strip())
                except:
                    pass  # Ignorar errores de decodificación
        
        # Reemplazar método
        self.uart_original._procesar_datos_recibidos = procesar_con_transferencia
    
    def enviar_archivo(self, ruta_archivo: str) -> bool:
        """Proxy al protocolo de transferencia"""
        if not self.transfer_protocol:
            raise Exception("Transfer protocol not configured")
        return self.transfer_protocol.enviar_archivo(ruta_archivo)
