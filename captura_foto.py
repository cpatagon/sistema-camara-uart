import serial
import threading
from picamera2 import Picamera2
from datetime import datetime
import os
import time

class CamaraUART:
    def __init__(self, puerto='/dev/ttyS0', baudrate=9600, directorio="fotos"):
        """
        Inicializa el sistema de cámara con control UART
        
        Parámetros:
        - puerto: puerto UART (por defecto /dev/ttyS0)
        - baudrate: velocidad de comunicación
        - directorio: carpeta donde guardar fotos
        """
        self.puerto = puerto
        self.baudrate = baudrate
        self.directorio = directorio
        self.ejecutando = False
        self.serial_conn = None
        
        # Crear directorio si no existe
        if not os.path.exists(self.directorio):
            os.makedirs(self.directorio)
        
        print(f"Sistema de cámara UART iniciado")
        print(f"Puerto: {self.puerto}, Baudrate: {self.baudrate}")
        print(f"Directorio: {self.directorio}")
        print("Envía 'foto' por UART para tomar una fotografía")
        print("Envía 'salir' para terminar el programa")

    def tomar_foto(self, resolucion=(1280, 720)):
        """
        Toma una foto con timestamp
        """
        picam2 = None
        
        try:
            # Generar nombre con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"{timestamp}.jpg"
            ruta_completa = os.path.join(self.directorio, nombre_archivo)
            
            # Inicializar cámara
            picam2 = Picamera2()
            config = picam2.create_still_configuration(main={"size": resolucion})
            picam2.configure(config)
            picam2.start()
            
            # Pausa para estabilizar
            time.sleep(0.5)
            
            # Capturar foto
            picam2.capture_file(ruta_completa)
            
            print(f"📸 Foto guardada: {ruta_completa}")
            
            # Enviar confirmación por UART
            if self.serial_conn:
                tamano_bytes = os.path.getsize(ruta_completa)
                self.serial_conn.write(f"OK|{nombre_archivo}|{tamano_bytes}|{ruta_completa}\r\n".encode())
            
            return ruta_completa
            
        except Exception as e:
            error_msg = f"Error al tomar foto: {e}"
            print(f"❌ {error_msg}")
            
            # Enviar error por UART
            if self.serial_conn:
                self.serial_conn.write(f"ERROR:{str(e)}\r\n".encode())
            
            return None
            
        finally:
            if picam2 is not None:
                try:
                    picam2.stop()
                    picam2.close()
                except:
                    pass
                time.sleep(0.2)

    def procesar_comando(self, comando):
        """
        Procesa los comandos recibidos por UART
        """
        comando = comando.strip().lower()
        
        if comando == "foto":
            print(f"📨 Comando recibido: {comando}")
            self.tomar_foto()
            
        elif comando == "salir" or comando == "exit":
            print("🛑 Comando de salida recibido")
            self.detener()
            
        elif comando == "estado" or comando == "status":
            estado_sistema = "ACTIVO"
            estado_msg = f"{estado_sistema}|{self.puerto}|{self.baudrate}"
            print(f"ℹ️  Estado: {estado_msg}")
            if self.serial_conn:
                self.serial_conn.write(f"STATUS:{estado_msg}\r\n".encode())
                
        elif comando.startswith("res:"):
            # Comando para cambiar resolución: "res:1920x1080"
            try:
                res_str = comando.replace("res:", "")
                ancho, alto = map(int, res_str.split("x"))
                print(f"🔧 Resolución cambiada a: {ancho}x{alto}")
                if self.serial_conn:
                    self.serial_conn.write(f"OK:Resolucion {ancho}x{alto}\r\n".encode())
            except:
                print("❌ Formato de resolución inválido. Usar: res:1920x1080")
                
        elif comando == "resolucion" or comando == "resolucion foto":
            # Obtener la resolución actual configurada
            try:
                # Crear una instancia temporal de la cámara para obtener la resolución
                picam2_temp = Picamera2()
                config_temp = picam2_temp.create_still_configuration()
                resolucion_actual = config_temp["main"]["size"]
                ancho, alto = resolucion_actual
        
                resolucion_msg = f"RESOLUCION|{ancho}x{alto}|{ancho * alto}"
                print(f"📐 Resolución actual: {ancho}x{alto}")
        
                if self.serial_conn:
                    self.serial_conn.write(f"{resolucion_msg}\r\n".encode())
            
                # Cerrar la instancia temporal
                picam2_temp.close()
        
            except Exception as e:
                error_msg = f"ERROR:No se pudo obtener resolucion - {str(e)}"
                print(f"❌ {error_msg}")
                if self.serial_conn:
                    self.serial_conn.write(f"{error_msg}\r\n".encode())
        elif comando != "":
            print(f"❓ Comando desconocido: {comando}")
            if self.serial_conn:
                comandos_disponibles = "foto, salir, estado, resolucion, res:WIDTHxHEIGHT"
                self.serial_conn.write(f"ERROR:Comando desconocido. Disponibles: {comandos_disponibles}\r\n".encode())

    def escuchar_uart(self):
        """
        Hilo que escucha constantemente el puerto UART
        """
        buffer = ""
        
        while self.ejecutando:
            try:
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    # Leer datos disponibles
                    data = self.serial_conn.read(self.serial_conn.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    # Procesar líneas completas
                    while '\n' in buffer or '\r' in buffer:
                        if '\n' in buffer:
                            linea, buffer = buffer.split('\n', 1)
                        else:
                            linea, buffer = buffer.split('\r', 1)
                        
                        if linea.strip():
                            self.procesar_comando(linea.strip())
                
                time.sleep(0.1)  # Pequeña pausa para no sobrecargar CPU
                
            except serial.SerialException as e:
                print(f"❌ Error de comunicación UART: {e}")
                time.sleep(1)
            except Exception as e:
                print(f"❌ Error inesperado: {e}")
                time.sleep(1)

    def iniciar(self):
        """
        Inicia el sistema de monitoreo UART
        """
        try:
            # Configurar conexión serial
            self.serial_conn = serial.Serial(
                port=self.puerto,
                baudrate=self.baudrate,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            
            print(f"✅ Conexión UART establecida en {self.puerto}")
            
            # Enviar mensaje de inicio
            self.serial_conn.write("CAMERA_READY\r\n".encode())
            
            # Iniciar hilo de escucha
            self.ejecutando = True
            hilo_uart = threading.Thread(target=self.escuchar_uart, daemon=True)
            hilo_uart.start()
            
            print("🎯 Sistema listo. Esperando comandos...")
            
            # Mantener el programa ejecutándose
            try:
                while self.ejecutando:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Interrupción por teclado")
                self.detener()
                
        except serial.SerialException as e:
            print(f"❌ Error al abrir puerto UART: {e}")
            print("💡 Verifica que el puerto esté disponible y tengas permisos")
        except Exception as e:
            print(f"❌ Error inesperado: {e}")

    def detener(self):
        """
        Detiene el sistema
        """
        print("🛑 Deteniendo sistema...")
        self.ejecutando = False
        
        if self.serial_conn:
            try:
                self.serial_conn.write("CAMERA_OFFLINE\r\n".encode())
                self.serial_conn.close()
            except:
                pass
        
        print("✅ Sistema detenido")

# Función para uso directo
def iniciar_camara_uart(puerto='/dev/ttyS0', baudrate=9600, directorio="fotos"):
    """
    Función simplificada para iniciar el sistema
    """
    camara = CamaraUART(puerto, baudrate, directorio)
    camara.iniciar()

# Ejemplo de uso
if __name__ == "__main__":
    # Configuración por defecto
    # Para Raspberry Pi Zero: /dev/ttyS0 (GPIO 14/15)
    # Para USB: /dev/ttyUSB0 o /dev/ttyACM0
    
    iniciar_camara_uart(
        puerto='/dev/ttyS0',    # Puerto UART
        baudrate=9600,          # Velocidad
        directorio="fotos"      # Carpeta de fotos
    )
