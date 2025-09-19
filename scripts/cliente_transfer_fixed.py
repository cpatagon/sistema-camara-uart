#!/usr/bin/env python3
"""
Cliente de Transferencia CORREGIDO - Compatible con el servidor
Corrige los errores de comandos en cliente_transfer_robust.py
"""

import serial
import time
import argparse
import sys
from pathlib import Path
from typing import Optional

class ClienteTransferCorregido:
    """Cliente corregido para transferencia de archivos UART"""
    
    def __init__(self, puerto: str = "/dev/ttyS0", baudrate: int = 115200):
        self.puerto = puerto
        self.baudrate = baudrate
        self.conexion: Optional[serial.Serial] = None
        self.chunks_recibidos = 0
        
    def conectar(self) -> bool:
        """Establece conexión UART"""
        try:
            print(f"🔌 Conectando a {self.puerto} @ {self.baudrate} baudios...")
            self.conexion = serial.Serial(
                port=self.puerto,
                baudrate=self.baudrate,
                timeout=2.0,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            time.sleep(1)  # Estabilizar conexión
            print("✅ Conexión establecida")
            return True
            
        except Exception as e:
            print(f"❌ Error conectando: {e}")
            return False
    
    def desconectar(self):
        """Cierra la conexión"""
        if self.conexion and self.conexion.is_open:
            self.conexion.close()
        print("👋 Conexión cerrada")
    
    def solicitar_fotodescarga_completo(self, comando="fotodescarga", archivo_destino=None) -> bool:
        """
        PROCESO COMPLETO CORREGIDO:
        1. Enviar comando 'fotodescarga' (NO 'foto' + 'transfer')
        2. Recibir respuesta 'FOTODESCARGA_OK|...'
        3. El servidor inicia transferencia automáticamente
        """
        try:
            print(f"📸 Enviando comando: {comando}")
            
            # PASO 1: Enviar comando fotodescarga (CORREGIDO)
            if not self._enviar_comando(comando):
                return False
            
            # PASO 2: Esperar respuesta FOTODESCARGA_OK (CORREGIDO)
            respuesta = self._leer_respuesta(timeout=20.0)
            if not respuesta:
                print("❌ No se recibió respuesta del servidor")
                return False
                
            print(f"📨 Respuesta recibida: {respuesta}")
            
            # PASO 3: Verificar respuesta exitosa
            if respuesta.startswith("FOTODESCARGA_OK"):
                info = self._procesar_respuesta_fotodescarga(respuesta)
                if info:
                    print(f"✅ Foto capturada exitosamente:")
                    print(f"   📄 Archivo: {info['archivo']}")
                    print(f"   📏 Tamaño: {info['tamaño']:,} bytes")
                    
                    # PASO 4: El servidor inicia transferencia automáticamente
                    print("📦 Esperando inicio de transferencia automática...")
                    return self._recibir_transferencia_automatica(archivo_destino or info['archivo'])
                else:
                    print("❌ Error procesando respuesta de foto")
                    return False
                    
            elif respuesta.startswith("ERROR"):
                print(f"❌ Error del servidor: {respuesta}")
                return False
            else:
                print(f"⚠️ Respuesta inesperada: {respuesta}")
                return False
                
        except Exception as e:
            print(f"❌ Error en proceso completo: {e}")
            return False
    
    def _procesar_respuesta_fotodescarga(self, respuesta: str) -> dict:
        """Procesa respuesta FOTODESCARGA_OK|archivo|tamaño|id|ruta"""
        try:
            partes = respuesta.split("|")
            if len(partes) >= 4:
                return {
                    'archivo': partes[1],
                    'tamaño': int(partes[2]),
                    'id_transferencia': partes[3],
                    'ruta': partes[4] if len(partes) > 4 else None
                }
            return None
        except Exception as e:
            print(f"❌ Error procesando respuesta: {e}")
            return None
    
    def _recibir_transferencia_automatica(self, archivo_destino: str) -> bool:
        """
        Recibe transferencia automática del servidor.
        El servidor envía automáticamente después de FOTODESCARGA_OK
        """
        try:
            # PASO 1: Esperar header de transferencia del servidor
            print("🔍 Esperando header de transferencia...")
            header = self._leer_respuesta(timeout=15.0)
            
            if not header:
                print("❌ No se recibió header de transferencia")
                return False
                
            print(f"📋 Header recibido: {header}")
            
            # El header puede ser diferente según la implementación del servidor
            # Intentar diferentes formatos posibles:
            if "|" in header:
                partes = header.split("|")
                
                # Formato posible: "timestamp|tamaño"
                if len(partes) == 2:
                    timestamp, tamaño_str = partes
                    try:
                        tamaño_archivo = int(tamaño_str)
                        print(f"📁 Archivo: {timestamp} ({tamaño_archivo:,} bytes)")
                    except ValueError:
                        print(f"❌ Formato de header inválido: {header}")
                        return False
                        
                # Formato posible: "TRANSFER_START|timestamp|tamaño"  
                elif header.startswith("TRANSFER_START") and len(partes) >= 3:
                    timestamp = partes[1]
                    tamaño_archivo = int(partes[2])
                    print(f"📁 Archivo: {timestamp} ({tamaño_archivo:,} bytes)")
                else:
                    print(f"❌ Formato de header no reconocido: {header}")
                    return False
            else:
                print(f"❌ Header sin formato válido: {header}")
                return False
            
            # PASO 2: Confirmar que estamos listos para recibir
            print("✅ Enviando confirmación READY...")
            if not self._enviar_comando("READY"):
                return False
            
            # PASO 3: Recibir datos
            archivo_final = f"descarga_{archivo_destino}"
            print(f"💾 Guardando como: {archivo_final}")
            
            datos_recibidos = self._recibir_datos_chunked(tamaño_archivo)
            
            if datos_recibidos and len(datos_recibidos) == tamaño_archivo:
                # Guardar archivo
                with open(archivo_final, "wb") as f:
                    f.write(datos_recibidos)
                
                print(f"🎉 ¡Descarga completada exitosamente!")
                print(f"   📄 Archivo guardado: {archivo_final}")
                print(f"   📏 Bytes recibidos: {len(datos_recibidos):,}")
                
                # PASO 4: Confirmar descarga completa
                self._enviar_comando("DONE")
                
                # Esperar confirmación final (opcional)
                confirmacion = self._leer_respuesta(timeout=5.0)
                if confirmacion:
                    print(f"📨 Confirmación final: {confirmacion}")
                
                return True
            else:
                print(f"❌ Error: recibido {len(datos_recibidos) if datos_recibidos else 0} de {tamaño_archivo} bytes")
                return False
                
        except Exception as e:
            print(f"❌ Error en transferencia: {e}")
            return False
    
    def _recibir_datos_chunked(self, tamaño_total: int) -> Optional[bytes]:
        """Recibe datos en chunks con confirmación ACK"""
        datos_completos = b""
        chunk_num = 0
        
        try:
            while len(datos_completos) < tamaño_total:
                # Leer chunk (máximo 256 bytes según el protocolo)
                restante = tamaño_total - len(datos_completos)
                tamaño_chunk = min(restante, 256)
                
                chunk_data = self.conexion.read(tamaño_chunk)
                if not chunk_data:
                    print(f"⚠️ No se recibieron datos para chunk {chunk_num}")
                    break
                
                datos_completos += chunk_data
                chunk_num += 1
                
                # Enviar ACK después de cada chunk
                if not self._enviar_comando("ACK"):
                    print(f"❌ Error enviando ACK para chunk {chunk_num}")
                    break
                
                # Mostrar progreso cada 50 chunks
                if chunk_num % 50 == 0:
                    progreso = (len(datos_completos) / tamaño_total) * 100
                    print(f"📈 Progreso: {progreso:.1f}% ({chunk_num} chunks)")
            
            return datos_completos
            
        except Exception as e:
            print(f"❌ Error recibiendo chunks: {e}")
            return None
    
    def _enviar_comando(self, comando: str) -> bool:
        """Envía un comando por UART"""
        try:
            if not self.conexion or not self.conexion.is_open:
                return False
            
            mensaje = f"{comando}\r\n"
            self.conexion.write(mensaje.encode('utf-8'))
            self.conexion.flush()
            return True
            
        except Exception as e:
            print(f"❌ Error enviando comando '{comando}': {e}")
            return False
    
    def _leer_respuesta(self, timeout: float = 5.0) -> Optional[str]:
        """Lee una respuesta de texto con timeout"""
        try:
            tiempo_anterior = self.conexion.timeout
            self.conexion.timeout = timeout
            
            linea = self.conexion.readline()
            self.conexion.timeout = tiempo_anterior
            
            if linea:
                return linea.decode('utf-8', errors='ignore').strip()
            return None
            
        except Exception as e:
            print(f"❌ Error leyendo respuesta: {e}")
            return None

def main():
    """Función principal del cliente corregido"""
    parser = argparse.ArgumentParser(description="Cliente de transferencia UART corregido")
    parser.add_argument("--puerto", default="/dev/ttyS0", help="Puerto UART")
    parser.add_argument("--baudrate", type=int, default=115200, help="Velocidad UART")
    parser.add_argument("--comando", default="fotodescarga", help="Comando a enviar")
    parser.add_argument("--archivo", help="Nombre del archivo destino")
    parser.add_argument("--test", action="store_true", help="Ejecutar test completo")
    
    args = parser.parse_args()
    
    print("📸 CLIENTE DE TRANSFERENCIA UART - VERSIÓN CORREGIDA")
    print("=" * 60)
    print(f"Puerto: {args.puerto}")
    print(f"Baudrate: {args.baudrate}")
    print(f"Comando: {args.comando}")
    print()
    
    # Crear cliente
    cliente = ClienteTransferCorregido(args.puerto, args.baudrate)
    
    try:
        # Conectar
        if not cliente.conectar():
            sys.exit(1)
        
        if args.test:
            # Test con múltiples comandos
            comandos_test = [
                "fotodescarga",
                "fotodescarga:test_imagen", 
                "fotosize:1280x720",
                "fotoinmediata"
            ]
            
            for i, cmd in enumerate(comandos_test):
                print(f"\n🧪 Test {i+1}/{len(comandos_test)}: {cmd}")
                
                if cliente.solicitar_fotodescarga_completo(cmd, args.archivo):
                    print(f"✅ Test {i+1} exitoso")
                else:
                    print(f"❌ Test {i+1} falló")
                
                if i < len(comandos_test) - 1:
                    print("⏳ Pausa entre tests...")
                    time.sleep(3)
        else:
            # Ejecutar comando único
            if cliente.solicitar_fotodescarga_completo(args.comando, args.archivo):
                print("✅ Operación completada exitosamente")
            else:
                print("❌ Operación falló")
        
    except KeyboardInterrupt:
        print("\n🛑 Interrumpido por usuario")
    
    finally:
        cliente.desconectar()

if __name__ == "__main__":
    main()
