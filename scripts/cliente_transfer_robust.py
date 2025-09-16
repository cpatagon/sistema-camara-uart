#!/usr/bin/env python3
"""
Cliente de Transferencia Robusto para Sistema de Cámara UART
Implementa el protocolo completo con manejo de errores y reintentos
"""

import serial
import time
import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple
import hashlib

class ClienteTransferenciaRobusto:
    """Cliente robusto para transferencia de archivos por UART"""
    
    def __init__(self, puerto: str = "/dev/ttyS0", baudrate: int = 115200):
        self.puerto = puerto
        self.baudrate = baudrate
        self.conexion: Optional[serial.Serial] = None
        self.archivo_actual = None
        self.bytes_recibidos = 0
        self.chunks_recibidos = 0
        
    def conectar(self) -> bool:
        """Establece conexión UART"""
        try:
            print(f"🔌 Conectando a {self.puerto} @ {self.baudrate} baudios...")
            
            self.conexion = serial.Serial(
                port=self.puerto,
                baudrate=self.baudrate,
                timeout=2.0,
                bytesize=8,
                parity=serial.PARITY_NONE,
                stopbits=1
            )
            
            if not self.conexion.is_open:
                print("❌ No se pudo abrir el puerto")
                return False
            
            # Limpiar buffers
            self.conexion.flush()
            self.conexion.reset_input_buffer()
            self.conexion.reset_output_buffer()
            
            print("✅ Conexión establecida")
            
            # Esperar mensaje de bienvenida
            self._esperar_mensaje("CAMERA_READY", timeout=5.0)
            
            return True
            
        except Exception as e:
            print(f"❌ Error conectando: {e}")
            return False
    
    def desconectar(self):
        """Cierra la conexión"""
        if self.conexion and self.conexion.is_open:
            try:
                self._enviar_comando("salir")
                time.sleep(0.5)
                self.conexion.close()
                print("👋 Conexión cerrada")
            except:
                pass
    
    def solicitar_foto_y_recibir(self, archivo_destino: str = None) -> bool:
        """Solicita una foto y la recibe usando el protocolo robusto"""
        try:
            print("📸 Solicitando captura de foto...")
            
            # Paso 1: Solicitar foto
            if not self._enviar_comando("foto"):
                return False
            
            # Paso 2: Esperar confirmación de foto tomada
            respuesta = self._leer_respuesta(timeout=15.0)  # Tiempo generoso para captura
            if not respuesta or not respuesta.startswith("OK|"):
                print(f"❌ Error en captura: {respuesta}")
                return False
            
            print(f"✅ Foto capturada: {respuesta}")
            
            # Paso 3: Solicitar transferencia
            print("📦 Iniciando transferencia de archivo...")
            return self._recibir_archivo_robusto(archivo_destino)
            
        except Exception as e:
            print(f"❌ Error en proceso completo: {e}")
            return False
    
    def _recibir_archivo_robusto(self, archivo_destino: str = None) -> bool:
        """Recibe archivo usando protocolo robusto con verificación"""
        try:
            # Paso 1: Solicitar inicio de transferencia
            if not self._enviar_comando("transfer"):
                return False
            
            # Paso 2: Leer header de transferencia
            header = self._leer_respuesta(timeout=10.0)
            if not header or not header.startswith("TRANSFER_START|"):
                print(f"❌ Header inválido: {header}")
                return False
            
            # Parsear header: TRANSFER_START|timestamp|size
            partes = header.split("|")
            if len(partes) < 3:
                print(f"❌ Formato de header inválido: {header}")
                return False
            
            timestamp = partes[1]
            tamaño_archivo = int(partes[2])
            
            print(f"📁 Archivo: {timestamp}.jpg ({tamaño_archivo} bytes)")
            
            # Paso 3: Preparar archivo destino
            if not archivo_destino:
                archivo_destino = f"recibido_{timestamp}.jpg"
            
            # Paso 4: Confirmar listo para recibir
            if not self._enviar_comando("READY"):
                return False
            
            # Paso 5: Recibir chunks con verificación
            datos_completos = b""
            chunk_esperado = 0
            
            with open(archivo_destino, "wb") as f:
                while len(datos_completos) < tamaño_archivo:
                    # Leer header del chunk
                    chunk_header = self._leer_respuesta(timeout=5.0)
                    if not chunk_header or not chunk_header.startswith("CHUNK|"):
                        print(f"❌ Header de chunk inválido: {chunk_header}")
                        return False
                    
                    # Parsear: CHUNK|num|size
                    header_partes = chunk_header.split("|")
                    chunk_num = int(header_partes[1])
                    chunk_size = int(header_partes[2])
                    
                    # Verificar secuencia
                    if chunk_num != chunk_esperado:
                        print(f"❌ Chunk fuera de secuencia: esperado {chunk_esperado}, recibido {chunk_num}")
                        self._enviar_comando("NACK")
                        continue
                    
                    # Confirmar listo para chunk
                    if not self._enviar_comando("CHUNK_READY"):
                        return False
                    
                    # Leer datos binarios del chunk
                    chunk_data = self._leer_datos_binarios(chunk_size, timeout=5.0)
                    if not chunk_data or len(chunk_data) != chunk_size:
                        print(f"❌ Error leyendo chunk {chunk_num}: {len(chunk_data) if chunk_data else 0}/{chunk_size} bytes")
                        self._enviar_comando("NACK")
                        continue
                    
                    # Escribir chunk al archivo
                    f.write(chunk_data)
                    datos_completos += chunk_data
                    
                    # Confirmar chunk recibido
                    if not self._enviar_comando("ACK"):
                        return False
                    
                    chunk_esperado += 1
                    self.chunks_recibidos += 1
                    
                    # Mostrar progreso cada 50 chunks
                    if chunk_esperado % 50 == 0:
                        progreso = (len(datos_completos) / tamaño_archivo) * 100
                        print(f"📈 Progreso: {progreso:.1f}% ({chunk_esperado} chunks)")
            
            # Paso 6: Confirmar transferencia completa
            if not self._enviar_comando("DONE"):
                return False
            
            # Paso 7: Esperar confirmación final
            confirmacion = self._leer_respuesta(timeout=5.0)
            if confirmacion != "TRANSFER_OK":
                print(f"⚠️ Confirmación inesperada: {confirmacion}")
            
            # Paso 8: Verificar integridad
            if len(datos_completos) == tamaño_archivo:
                print(f"✅ Archivo recibido exitosamente: {archivo_destino}")
                print(f"📊 Estadísticas: {len(datos_completos)} bytes, {self.chunks_recibidos} chunks")
                return True
            else:
                print(f"❌ Error de tamaño: esperado {tamaño_archivo}, recibido {len(datos_completos)}")
                return False
                
        except Exception as e:
            print(f"❌ Error en transferencia: {e}")
            return False
    
    def _enviar_comando(self, comando: str) -> bool:
        """Envía un comando y verifica el envío"""
        try:
            if not self.conexion or not self.conexion.is_open:
                return False
            
            mensaje = f"{comando}\n"
            bytes_enviados = self.conexion.write(mensaje.encode('utf-8'))
            self.conexion.flush()
            
            return bytes_enviados > 0
            
        except Exception as e:
            print(f"❌ Error enviando comando '{comando}': {e}")
            return False
    
    def _leer_respuesta(self, timeout: float = 5.0) -> Optional[str]:
        """Lee una respuesta de texto con timeout"""
        try:
            self.conexion.timeout = timeout
            linea = self.conexion.readline()
            
            if linea:
                return linea.decode('utf-8', errors='ignore').strip()
            return None
            
        except Exception as e:
            print(f"❌ Error leyendo respuesta: {e}")
            return None
    
    def _leer_datos_binarios(self, tamaño: int, timeout: float = 5.0) -> Optional[bytes]:
        """Lee datos binarios con timeout y verificación de tamaño"""
        try:
            self.conexion.timeout = timeout
            datos = b""
            inicio = time.time()
            
            while len(datos) < tamaño and (time.time() - inicio) < timeout:
                restante = tamaño - len(datos)
                chunk = self.conexion.read(min(restante, 256))
                
                if not chunk:
                    break
                
                datos += chunk
            
            return datos if len(datos) == tamaño else None
            
        except Exception as e:
            print(f"❌ Error leyendo datos binarios: {e}")
            return None
    
    def _esperar_mensaje(self, esperado: str, timeout: float = 5.0) -> bool:
        """Espera un mensaje específico"""
        inicio = time.time()
        
        while time.time() - inicio < timeout:
            respuesta = self._leer_respuesta(timeout=1.0)
            if respuesta and esperado in respuesta:
                print(f"📨 {respuesta}")
                return True
        
        return False

def main():
    """Función principal del cliente"""
    parser = argparse.ArgumentParser(description="Cliente de transferencia de archivos UART")
    parser.add_argument("--puerto", default="/dev/ttyS0", help="Puerto UART")
    parser.add_argument("--baudrate", type=int, default=115200, help="Velocidad UART")
    parser.add_argument("--archivo", help="Nombre del archivo destino")
    parser.add_argument("--cantidad", type=int, default=1, help="Número de fotos a capturar")
    
    args = parser.parse_args()
    
    # Crear cliente
    cliente = ClienteTransferenciaRobusto(args.puerto, args.baudrate)
    
    try:
        # Conectar
        if not cliente.conectar():
            sys.exit(1)
        
        # Procesar fotos
        for i in range(args.cantidad):
            print(f"\n🔄 Captura {i + 1}/{args.cantidad}")
            
            archivo_destino = args.archivo
            if args.cantidad > 1 and archivo_destino:
                # Agregar número de secuencia
                path = Path(archivo_destino)
                archivo_destino = f"{path.stem}_{i+1:03d}{path.suffix}"
            
            if cliente.solicitar_foto_y_recibir(archivo_destino):
                print(f"✅ Captura {i + 1} completada")
            else:
                print(f"❌ Error en captura {i + 1}")
                break
            
            # Pausa entre capturas
            if i < args.cantidad - 1:
                print("⏳ Pausa entre capturas...")
                time.sleep(2.0)
        
    except KeyboardInterrupt:
        print("\n🛑 Interrumpido por usuario")
    
    finally:
        cliente.desconectar()

if __name__ == "__main__":
    main()
