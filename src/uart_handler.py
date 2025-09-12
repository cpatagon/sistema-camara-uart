"""
Manejador UART Simplificado - Compatible con main_daemon.py
"""

import serial
import threading
import time
import logging
from typing import Optional, Callable, Dict, Any
from pathlib import Path

class UARTHandler:
    """
    Manejador UART simplificado que implementa la interfaz esperada por main_daemon.py
    """
    
    def __init__(self, config_manager):
        """Inicializa el manejador UART"""
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Estado de conexión
        self.conexion: Optional[serial.Serial] = None
        self.ejecutando = False
        self.hilo_lectura: Optional[threading.Thread] = None
        
        # Callbacks para comandos
        self.callbacks_comandos: Dict[str, Callable] = {}
        
        # Buffer de comunicación
        self.buffer_entrada = ""
        
        # Estadísticas básicas
        self.comandos_procesados = 0
        self.bytes_enviados = 0
        self.bytes_recibidos = 0
        self.ultima_actividad = time.time()
        
        # Lock para thread safety
        self.lock = threading.Lock()
        
        self.logger.info(f"UARTHandler inicializado para puerto {self.config.uart.puerto}")
    
    def registrar_comando(self, comando: str, callback: Callable):
        """Registra un callback para un comando"""
        self.callbacks_comandos[comando.lower()] = callback
        self.logger.debug(f"Comando registrado: {comando}")
    
    def iniciar(self):
        """Inicia el sistema UART"""
        try:
            if self.ejecutando:
                self.logger.warning("Sistema UART ya está ejecutándose")
                return
            
            # Conectar
            self.logger.info(f"Conectando a {self.config.uart.puerto} @ {self.config.uart.baudrate} baudios")
            
            self.conexion = serial.Serial(
                port=self.config.uart.puerto,
                baudrate=self.config.uart.baudrate,
                timeout=self.config.uart.timeout,
                bytesize=self.config.uart.bytesize,
                parity=self._convert_parity(self.config.uart.parity),
                stopbits=self.config.uart.stopbits
            )
            
            if not self.conexion.is_open:
                raise Exception("Puerto no se pudo abrir")
            
            # Limpiar buffers
            self.conexion.flush()
            self.conexion.reset_input_buffer()
            self.conexion.reset_output_buffer()
            
            # Iniciar hilos
            self.ejecutando = True
            self.hilo_lectura = threading.Thread(target=self._bucle_lectura, daemon=True)
            self.hilo_lectura.start()
            
            # Enviar mensaje de inicio
            self.enviar_mensaje("CAMERA_READY")
            
            self.logger.info("Sistema UART iniciado correctamente")
            
        except Exception as e:
            self.ejecutando = False
            self.logger.error(f"Error iniciando sistema UART: {e}")
            raise
    
    def detener(self):
        """Detiene el sistema UART"""
        self.logger.info("Deteniendo sistema UART...")
        
        self.ejecutando = False
        
        # Enviar mensaje de cierre
        if self.conexion and self.conexion.is_open:
            try:
                self.enviar_mensaje("CAMERA_OFFLINE")
                time.sleep(0.1)
            except:
                pass
        
        # Esperar hilo de lectura
        if self.hilo_lectura and self.hilo_lectura.is_alive():
            self.hilo_lectura.join(timeout=5.0)
        
        # Cerrar conexión
        if self.conexion:
            try:
                self.conexion.close()
            except:
                pass
        
        self.logger.info("Sistema UART detenido")
    
    def enviar_mensaje(self, mensaje: str) -> bool:
        """Envía mensaje por UART"""
        try:
            if not self.conexion or not self.conexion.is_open:
                return False
            
            with self.lock:
                if not mensaje.endswith(('\r\n', '\n')):
                    mensaje += '\r\n'
                
                bytes_enviados = self.conexion.write(mensaje.encode('utf-8'))
                self.conexion.flush()
                
                self.bytes_enviados += bytes_enviados
                self.ultima_actividad = time.time()
                
            self.logger.debug(f"Enviado: {mensaje.strip()}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error enviando mensaje: {e}")
            return False
    
    def _bucle_lectura(self):
        """Bucle principal de lectura UART"""
        self.logger.debug("Iniciando bucle de lectura UART")
        
        while self.ejecutando:
            try:
                if not self.conexion or not self.conexion.is_open:
                    time.sleep(1.0)
                    continue
                
                # Leer datos disponibles
                if self.conexion.in_waiting > 0:
                    data = self.conexion.read(self.conexion.in_waiting)
                    if data:
                        self._procesar_datos_recibidos(data)
                
                time.sleep(0.05)
                
            except Exception as e:
                self.logger.error(f"Error en bucle de lectura: {e}")
                time.sleep(1.0)
    
    def _procesar_datos_recibidos(self, data: bytes):
        """Procesa datos recibidos"""
        try:
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
                    
        except Exception as e:
            self.logger.error(f"Error procesando datos: {e}")
    
    def _procesar_comando(self, linea: str):
        """Procesa un comando recibido"""
        try:
            # Parsear comando
            if ':' in linea:
                partes = linea.split(':', 1)
                comando = partes[0].lower().strip()
                parametros = [partes[1]] if len(partes) > 1 else []
            else:
                comando = linea.lower().strip()
                parametros = []
            
            self.logger.debug(f"Comando recibido: {comando} {parametros}")
            
            # Crear objeto comando simple
            class ComandoUART:
                def __init__(self, cmd, params):
                    self.comando = cmd
                    self.parametros = params
                    self.timestamp = time.time()
            
            cmd_obj = ComandoUART(comando, parametros)
            
            # Buscar callback
            if comando in self.callbacks_comandos:
                try:
                    respuesta = self.callbacks_comandos[comando](cmd_obj)
                    if respuesta:
                        self.enviar_mensaje(respuesta)
                    
                    self.comandos_procesados += 1
                    
                except Exception as e:
                    error_msg = f"ERROR|PROCESSING|Error procesando '{comando}': {str(e)}"
                    self.enviar_mensaje(error_msg)
                    self.logger.error(f"Error en callback '{comando}': {e}")
            else:
                # Comando no reconocido
                comandos_disponibles = list(self.callbacks_comandos.keys())
                error_msg = f"ERROR|UNKNOWN_COMMAND|Comando '{comando}' no reconocido. Disponibles: {', '.join(comandos_disponibles)}"
                self.enviar_mensaje(error_msg)
                self.logger.warning(f"Comando no reconocido: {comando}")
                
        except Exception as e:
            self.logger.error(f"Error procesando comando: {e}")
    
    def cambiar_baudrate(self, nuevo_baudrate: int) -> bool:
        """Cambia la velocidad UART"""
        try:
            velocidades_validas = [9600, 19200, 38400, 57600, 115200, 230400]
            
            if nuevo_baudrate not in velocidades_validas:
                self.logger.error(f"Velocidad {nuevo_baudrate} no válida")
                return False
            
            self.logger.info(f"Cambiando velocidad de {self.config.uart.baudrate} a {nuevo_baudrate}")
            
            # Notificar cambio
            self.enviar_mensaje(f"OK:Cambiando a {nuevo_baudrate} en 3 segundos")
            time.sleep(1.0)
            
            # Actualizar configuración
            self.config.actualizar_baudrate(nuevo_baudrate)
            
            # Reconectar con nueva velocidad
            if self.conexion:
                self.conexion.close()
            
            time.sleep(2.0)
            
            self.conexion = serial.Serial(
                port=self.config.uart.puerto,
                baudrate=nuevo_baudrate,
                timeout=self.config.uart.timeout,
                bytesize=self.config.uart.bytesize,
                parity=self._convert_parity(self.config.uart.parity),
                stopbits=self.config.uart.stopbits
            )
            
            if self.conexion.is_open:
                self.enviar_mensaje(f"BAUDRATE_CHANGED|{nuevo_baudrate}")
                self.logger.info(f"Velocidad cambiada exitosamente a {nuevo_baudrate}")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Error cambiando velocidad: {e}")
            return False
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la conexión UART"""
        return {
            'puerto': self.config.uart.puerto,
            'baudrate': self.config.uart.baudrate,
            'comandos_procesados': self.comandos_procesados,
            'bytes_enviados': self.bytes_enviados,
            'bytes_recibidos': self.bytes_recibidos,
            'conexion_activa': self.conexion is not None and self.conexion.is_open
        }
    
    def _convert_parity(self, parity_str: str) -> str:
        """Convierte string de paridad a constante serial"""
        parity_map = {
            'N': serial.PARITY_NONE,
            'E': serial.PARITY_EVEN,
            'O': serial.PARITY_ODD
        }
        return parity_map.get(parity_str.upper(), serial.PARITY_NONE)
