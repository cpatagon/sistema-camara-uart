# file_transfer_protocol.py
import time
from pathlib import Path

CHUNK_SIZE = 256

class FileTransferProtocol:
    def __init__(self, uart_handler, logger=None):
        self.uart = uart_handler
        self.logger = logger

    def enviar_archivo(self, ruta_archivo: str) -> bool:
        """Implementa el protocolo de transferencia chunked con ACK/DONE"""
        archivo = Path(ruta_archivo)
        if not archivo.exists():
            self.uart.enviar_mensaje(f"ERROR|FILE_NOT_FOUND|{archivo.name}")
            return False

        tamaño = archivo.stat().st_size
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # Paso 1: Enviar header
        header = f"{timestamp}|{tamaño}\n"
        self.uart.enviar_mensaje(header)
        if self.logger:
            self.logger.info(f"Header enviado: {header.strip()}")

        # Paso 2: Esperar READY
        if not self._esperar_respuesta("READY"):
            self._error("READY no recibido")
            return False

        # Paso 3: Enviar chunks con ACK
        with open(archivo, "rb") as f:
            idx = 0
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                self.uart.conexion.write(chunk)   # binario crudo
                self.uart.conexion.flush()

                if self.logger:
                    self.logger.debug(f"Chunk {idx} enviado ({len(chunk)} bytes)")

                # Confirmación ACK
                if not self._esperar_respuesta("ACK"):
                    self._error(f"ACK no recibido en chunk {idx}")
                    return False
                idx += 1

        # Paso 4: Esperar DONE
        if not self._esperar_respuesta("DONE"):
            self._error("DONE no recibido")
            return False

        # Paso 5: Confirmar fin
        self.uart.enviar_mensaje("TRANSFER_OK\n")
        if self.logger:
            self.logger.info(f"Transferencia completada de {archivo.name}")
        return True

    def _esperar_respuesta(self, esperado: str, timeout: float = 5.0) -> bool:
        """Espera que el cliente envíe una respuesta específica"""
        inicio = time.time()
        while time.time() - inicio < timeout:
            if self.uart.buffer_entrada:
                linea, _, resto = self.uart.buffer_entrada.partition("\n")
                self.uart.buffer_entrada = resto
                if linea.strip() == esperado:
                    return True
        return False

    def _error(self, msg):
        if self.logger:
            self.logger.error(msg)
        self.uart.enviar_mensaje(f"ERROR|TRANSFER|{msg}")
