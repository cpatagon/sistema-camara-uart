#!/usr/bin/env python3
"""
Cliente de pruebas para el sistema de cámara UART.

Este script permite probar todos los comandos del sistema de manera interactiva
o automatizada, útil para desarrollo y diagnóstico.
"""

import sys
import os
import serial
import time
import threading
import argparse
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import readline  # Para historial de comandos
import re

# Colores para terminal
class Colores:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'


def imprimir_color(texto: str, color: str = Colores.WHITE):
    """Imprime texto con color."""
    print(f"{color}{texto}{Colores.RESET}")


def imprimir_banner():
    """Imprime banner del cliente."""
    banner = f"""
{Colores.CYAN}╔══════════════════════════════════════════════════════╗
║              📸 CLIENTE CÁMARA UART v1.0            ║
║                                                      ║
║     Cliente de pruebas para sistema de cámara       ║
║           Raspberry Pi con control UART             ║
╚══════════════════════════════════════════════════════╝{Colores.RESET}
"""
    print(banner)


class ClienteUART:
    """
    Cliente UART para comunicación con el sistema de cámara.
    
    Permite enviar comandos y recibir respuestas de manera interactiva.
    """
    
    def __init__(self, puerto: str = "/dev/ttyUSB0", baudrate: int = 115200):
        """
        Inicializa el cliente UART.
        
        Args:
            puerto: Puerto serie a utilizar
            baudrate: Velocidad de comunicación
        """
        self.puerto = puerto
        self.baudrate = baudrate
        self.conexion: Optional[serial.Serial] = None
        self.ejecutando = False
        self.hilo_lectura: Optional[threading.Thread] = None
        
        # Buffer para respuestas
        self.buffer_respuesta = ""
        self.ultima_respuesta = ""
        self.esperando_respuesta = False
        
        # Estadísticas
        self.comandos_enviados = 0
        self.respuestas_recibidas = 0
        self.tiempo_conexion = 0.0
        
        # Historial de comandos
        self.historial_comandos: List[str] = []
        self.cargar_historial()
    
    def conectar(self) -> bool:
        """
        Establece conexión con el puerto UART.
        
        Returns:
            bool: True si la conexión fue exitosa
        """
        try:
            imprimir_color(f"🔌 Conectando a {self.puerto} @ {self.baudrate} baudios...", Colores.CYAN)
            
            self.conexion = serial.Serial(
                port=self.puerto,
                baudrate=self.baudrate,
                timeout=1.0,
                bytesize=8,
                parity=serial.PARITY_NONE,
                stopbits=1
            )
            
            if not self.conexion.is_open:
                imprimir_color("❌ No se pudo abrir el puerto", Colores.RED)
                return False
            
            # Limpiar buffers
            self.conexion.flush()
            self.conexion.reset_input_buffer()
            self.conexion.reset_output_buffer()
            
            # Iniciar hilo de lectura
            self.ejecutando = True
            self.hilo_lectura = threading.Thread(target=self._bucle_lectura, daemon=True)
            self.hilo_lectura.start()
            
            self.tiempo_conexion = time.time()
            
            imprimir_color("✅ Conexión establecida exitosamente", Colores.GREEN)
            
            # Esperar mensaje de bienvenida
            time.sleep(1.0)
            if "CAMERA_READY" in self.buffer_respuesta:
                imprimir_color("📸 Sistema de cámara listo", Colores.GREEN)
            
            return True
            
        except serial.SerialException as e:
            imprimir_color(f"❌ Error de puerto serie: {e}", Colores.RED)
            return False
        except Exception as e:
            imprimir_color(f"❌ Error inesperado: {e}", Colores.RED)
            return False
    
    def desconectar(self):
        """Cierra la conexión UART."""
        try:
            self.ejecutando = False
            
            if self.conexion and self.conexion.is_open:
                self.conexion.close()
            
            if self.hilo_lectura and self.hilo_lectura.is_alive():
                self.hilo_lectura.join(timeout=2.0)
            
            tiempo_total = time.time() - self.tiempo_conexion if self.tiempo_conexion > 0 else 0
            
            imprimir_color(f"👋 Conexión cerrada (activa {tiempo_total:.1f}s)", Colores.YELLOW)
            
        except Exception as e:
            imprimir_color(f"⚠️  Error cerrando conexión: {e}", Colores.YELLOW)
    
    def _bucle_lectura(self):
        """Bucle de lectura de respuestas UART."""
        while self.ejecutando:
            try:
                if self.conexion and self.conexion.in_waiting > 0:
                    data = self.conexion.read(self.conexion.in_waiting)
                    texto = data.decode('utf-8', errors='ignore')
                    self.buffer_respuesta += texto
                    
                    # Procesar líneas completas
                    while '\n' in self.buffer_respuesta:
                        linea, self.buffer_respuesta = self.buffer_respuesta.split('\n', 1)
                        linea = linea.strip()
                        
                        if linea:
                            self._procesar_respuesta(linea)
                
                time.sleep(0.05)
                
            except Exception as e:
                if self.ejecutando:
                    imprimir_color(f"❌ Error en lectura: {e}", Colores.RED)
                time.sleep(0.5)
    
    def _procesar_respuesta(self, respuesta: str):
        """
        Procesa una respuesta recibida.
        
        Args:
            respuesta: Respuesta recibida del sistema
        """
        self.ultima_respuesta = respuesta
        self.respuestas_recibidas += 1
        
        # Formatear respuesta según tipo
        if respuesta.startswith("OK"):
            imprimir_color(f"✅ {respuesta}", Colores.GREEN)
        elif respuesta.startswith("ERROR"):
            imprimir_color(f"❌ {respuesta}", Colores.RED)
        elif respuesta.startswith("STATUS"):
            imprimir_color(f"📊 {respuesta}", Colores.BLUE)
        elif respuesta.startswith("CAMERA_"):
            imprimir_color(f"📸 {respuesta}", Colores.MAGENTA)
        elif respuesta.startswith("FILES"):
            imprimir_color(f"📁 {respuesta}", Colores.CYAN)
        elif respuesta.startswith("STATS"):
            imprimir_color(f"📈 {respuesta}", Colores.YELLOW)
        else:
            imprimir_color(f"📨 {respuesta}", Colores.WHITE)
        
        # Analizar respuestas especiales
        self._analizar_respuesta_especial(respuesta)
    
    def _analizar_respuesta_especial(self, respuesta: str):
        """
        Analiza respuestas especiales para mostrar información adicional.
        
        Args:
            respuesta: Respuesta a analizar
        """
        try:
            # Analizar respuesta de foto
            if respuesta.startswith("OK") and "|" in respuesta:
                partes = respuesta.split("|")
                if len(partes) >= 4:
                    nombre = partes[1]
                    tamaño = int(partes[2])
                    ruta = partes[3]
                    
                    print(f"   📄 Archivo: {nombre}")
                    print(f"   📏 Tamaño: {tamaño:,} bytes ({tamaño/1024:.1f} KB)")
                    print(f"   📂 Ruta: {ruta}")
            
            # Analizar estado del sistema
            elif respuesta.startswith("STATUS:ACTIVO"):
                partes = respuesta.split("|")
                if len(partes) >= 5:
                    puerto = partes[1]
                    velocidad = partes[2]
                    fotos = partes[3]
                    comandos = partes[4]
                    
                    print(f"   🔌 Puerto: {puerto}")
                    print(f"   ⚡ Velocidad: {velocidad} baudios")
                    print(f"   📸 Fotos tomadas: {fotos}")
                    print(f"   ⌨️  Comandos procesados: {comandos}")
            
            # Analizar información de resolución
            elif respuesta.startswith("RESOLUCION"):
                partes = respuesta.split("|")
                if len(partes) >= 4:
                    resolucion = partes[1]
                    megapixeles = partes[2]
                    formato = partes[3]
                    
                    print(f"   📐 Resolución: {resolucion}")
                    print(f"   🎯 Megapíxeles: {megapixeles}")
                    print(f"   🖼️  Formato: {formato}")
            
            # Analizar lista de archivos
            elif respuesta.startswith("FILES"):
                partes = respuesta.split("|")
                if len(partes) >= 3:
                    total = partes[1]
                    bytes_total = int(partes[2])
                    
                    print(f"   📁 Total archivos: {total}")
                    print(f"   💾 Espacio usado: {bytes_total:,} bytes ({bytes_total/1024/1024:.1f} MB)")
                    
                    # Mostrar archivos individuales
                    for i in range(3, len(partes)):
                        if ":" in partes[i]:
                            nombre, tamaño = partes[i].split(":")
                            print(f"   📄 {nombre} ({int(tamaño):,} bytes)")
            
            # Analizar estadísticas
            elif respuesta.startswith("STATS"):
                partes = respuesta.split("|")
                for parte in partes[1:]:
                    if ":" in parte:
                        clave, valor = parte.split(":", 1)
                        print(f"   📊 {clave}: {valor}")
        
        except Exception as e:
            # Error en análisis no es crítico
            pass
    
    def enviar_comando(self, comando: str) -> bool:
        """
        Envía un comando por UART.
        
        Args:
            comando: Comando a enviar
            
        Returns:
            bool: True si el comando fue enviado
        """
        try:
            if not self.conexion or not self.conexion.is_open:
                imprimir_color("❌ No hay conexión UART", Colores.RED)
                return False
            
            # Limpiar comando
            comando = comando.strip()
            if not comando:
                return False
            
            # Enviar comando
            comando_bytes = (comando + '\r\n').encode('utf-8')
            self.conexion.write(comando_bytes)
            self.conexion.flush()
            
            self.comandos_enviados += 1
            self.historial_comandos.append(comando)
            
            imprimir_color(f"➤ {comando}", Colores.CYAN)
            
            return True
            
        except Exception as e:
            imprimir_color(f"❌ Error enviando comando: {e}", Colores.RED)
            return False
    
    def esperar_respuesta(self, timeout: float = 5.0) -> Optional[str]:
        """
        Espera una respuesta específica.
        
        Args:
            timeout: Timeout en segundos
            
        Returns:
            str: Última respuesta recibida o None
        """
        inicio = time.time()
        respuesta_inicial = self.respuestas_recibidas
        
        while (time.time() - inicio) < timeout:
            if self.respuestas_recibidas > respuesta_inicial:
                return self.ultima_respuesta
            time.sleep(0.1)
        
        return None
    
    def cargar_historial(self):
        """Carga historial de comandos desde archivo."""
        try:
            archivo_historial = Path.home() / ".camara_uart_historial"
            if archivo_historial.exists():
                with open(archivo_historial, 'r') as f:
                    self.historial_comandos = [linea.strip() for linea in f.readlines()]
        except:
            pass
    
    def guardar_historial(self):
        """Guarda historial de comandos a archivo."""
        try:
            archivo_historial = Path.home() / ".camara_uart_historial"
            with open(archivo_historial, 'w') as f:
                # Guardar últimos 100 comandos
                for comando in self.historial_comandos[-100:]:
                    f.write(f"{comando}\n")
        except:
            pass
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cliente."""
        tiempo_conexion = time.time() - self.tiempo_conexion if self.tiempo_conexion > 0 else 0
        
        return {
            'puerto': self.puerto,
            'baudrate': self.baudrate,
            'conectado': self.conexion is not None and self.conexion.is_open,
            'tiempo_conexion': tiempo_conexion,
            'comandos_enviados': self.comandos_enviados,
            'respuestas_recibidas': self.respuestas_recibidas,
            'ultima_respuesta': self.ultima_respuesta
        }


class InterfazInteractiva:
    """Interfaz interactiva para el cliente UART."""
    
    def __init__(self, cliente: ClienteUART):
        """
        Inicializa la interfaz interactiva.
        
        Args:
            cliente: Cliente UART a utilizar
        """
        self.cliente = cliente
        self.comandos_disponibles = {
            'foto': 'Tomar una fotografía',
            'foto:nombre': 'Tomar foto con nombre personalizado',
            'estado': 'Obtener estado del sistema',
            'resolucion': 'Obtener información de resolución',
            'res:1920x1080': 'Cambiar resolución',
            'baudrate:115200': 'Cambiar velocidad UART',
            'listar': 'Listar archivos disponibles',
            'descargar:archivo.jpg': 'Descargar archivo específico',
            'limpiar': 'Limpiar archivos antiguos',
            'estadisticas': 'Obtener estadísticas del sistema',
            'reiniciar': 'Reinicializar cámara',
            'test': 'Realizar test de captura',
            'salir': 'Salir del sistema',
        }
        
        self.comandos_cliente = {
            'help': 'Mostrar esta ayuda',
            'cls': 'Limpiar pantalla',
            'stats': 'Estadísticas del cliente',
            'quit': 'Salir del cliente',
            'auto': 'Modo automático de pruebas',
            'batch': 'Ejecutar comandos desde archivo'
        }
    
    def ejecutar(self):
        """Ejecuta la interfaz interactiva."""
        imprimir_color("🎮 Modo interactivo iniciado", Colores.GREEN)
        imprimir_color("💡 Escribe 'help' para ver comandos disponibles", Colores.YELLOW)
        imprimir_color("💡 Usa Tab para autocompletar, ↑↓ para historial", Colores.YELLOW)
        print()
        
        # Configurar autocompletado
        self._configurar_autocompletado()
        
        try:
            while True:
                try:
                    # Prompt con estado
                    estado = "🟢" if self.cliente.conexion and self.cliente.conexion.is_open else "🔴"
                    prompt = f"{estado} camara-uart> "
                    
                    comando = input(prompt).strip()
                    
                    if not comando:
                        continue
                    
                    if not self._procesar_comando_cliente(comando):
                        # Enviar al sistema de cámara
                        self.cliente.enviar_comando(comando)
                
                except KeyboardInterrupt:
                    print()
                    imprimir_color("👋 Saliendo del modo interactivo...", Colores.YELLOW)
                    break
                except EOFError:
                    print()
                    break
        
        finally:
            self.cliente.guardar_historial()
    
    def _configurar_autocompletado(self):
        """Configura autocompletado de comandos."""
        todos_comandos = list(self.comandos_disponibles.keys()) + list(self.comandos_cliente.keys())
        
        def completar(texto, estado):
            opciones = [cmd for cmd in todos_comandos if cmd.startswith(texto)]
            if estado < len(opciones):
                return opciones[estado]
            return None
        
        readline.set_completer(completar)
        readline.parse_and_bind("tab: complete")
    
    def _procesar_comando_cliente(self, comando: str) -> bool:
        """
        Procesa comandos específicos del cliente.
        
        Args:
            comando: Comando a procesar
            
        Returns:
            bool: True si fue procesado por el cliente
        """
        comando_lower = comando.lower()
        
        if comando_lower in ['help', 'ayuda', '?']:
            self._mostrar_ayuda()
            return True
        
        elif comando_lower in ['cls', 'clear']:
            os.system('clear' if os.name == 'posix' else 'cls')
            return True
        
        elif comando_lower in ['stats', 'estadisticas-cliente']:
            self._mostrar_estadisticas_cliente()
            return True
        
        elif comando_lower in ['quit', 'exit', 'salir-cliente']:
            return False  # Esto causará que se salga del bucle
        
        elif comando_lower == 'auto':
            self._ejecutar_modo_automatico()
            return True
        
        elif comando_lower.startswith('batch:'):
            archivo = comando[6:].strip()
            self._ejecutar_batch(archivo)
            return True
        
        return False
    
    def _mostrar_ayuda(self):
        """Muestra ayuda de comandos."""
        imprimir_color("📚 COMANDOS DISPONIBLES", Colores.BOLD)
        print()
        
        imprimir_color("🎮 Comandos del Cliente:", Colores.CYAN)
        for cmd, desc in self.comandos_cliente.items():
            print(f"   {cmd:<20} - {desc}")
        
        print()
        imprimir_color("📸 Comandos del Sistema de Cámara:", Colores.MAGENTA)
        for cmd, desc in self.comandos_disponibles.items():
            print(f"   {cmd:<20} - {desc}")
        
        print()
        imprimir_color("💡 Ejemplos de uso:", Colores.YELLOW)
        ejemplos = [
            "foto                 # Tomar foto con timestamp",
            "foto:mi_foto         # Tomar foto con nombre personalizado",
            "res:1280x720        # Cambiar a resolución HD",
            "baudrate:57600      # Cambiar velocidad a 57600",
            "listar              # Ver archivos disponibles",
            "descargar:foto.jpg  # Descargar archivo específico"
        ]
        
        for ejemplo in ejemplos:
            print(f"   {ejemplo}")
        print()
    
    def _mostrar_estadisticas_cliente(self):
        """Muestra estadísticas del cliente."""
        stats = self.cliente.obtener_estadisticas()
        
        imprimir_color("📊 ESTADÍSTICAS DEL CLIENTE", Colores.BOLD)
        print()
        
        print(f"🔌 Puerto: {stats['puerto']}")
        print(f"⚡ Velocidad: {stats['baudrate']} baudios")
        print(f"📡 Estado: {'Conectado' if stats['conectado'] else 'Desconectado'}")
        print(f"⏱️  Tiempo conexión: {stats['tiempo_conexion']:.1f} segundos")
        print(f"📤 Comandos enviados: {stats['comandos_enviados']}")
        print(f"📥 Respuestas recibidas: {stats['respuestas_recibidas']}")
        print(f"💬 Última respuesta: {stats['ultima_respuesta']}")
        print()
    
    def _ejecutar_modo_automatico(self):
        """Ejecuta una secuencia automática de pruebas."""
        imprimir_color("🤖 MODO AUTOMÁTICO DE PRUEBAS", Colores.BOLD)
        print()
        
        secuencia_comandos = [
            ("estado", "Verificando estado del sistema"),
            ("resolucion", "Obteniendo información de resolución"),
            ("test", "Realizando test de captura"),
            ("listar", "Listando archivos disponibles"),
            ("estadisticas", "Obteniendo estadísticas")
        ]
        
        for comando, descripcion in secuencia_comandos:
            imprimir_color(f"🔄 {descripcion}...", Colores.CYAN)
            self.cliente.enviar_comando(comando)
            time.sleep(2)  # Pausa entre comandos
        
        print()
        respuesta = input("¿Tomar una foto de prueba? (s/N): ").strip().lower()
        if respuesta in ['s', 'si', 'y', 'yes']:
            imprimir_color("📸 Tomando foto de prueba...", Colores.CYAN)
            self.cliente.enviar_comando("foto:test_automatico")
            time.sleep(3)
        
        imprimir_color("✅ Modo automático completado", Colores.GREEN)
    
    def _ejecutar_batch(self, archivo: str):
        """
        Ejecuta comandos desde un archivo.
        
        Args:
            archivo: Ruta del archivo con comandos
        """
        try:
            archivo_path = Path(archivo)
            if not archivo_path.exists():
                imprimir_color(f"❌ Archivo no encontrado: {archivo}", Colores.RED)
                return
            
            imprimir_color(f"📄 Ejecutando comandos desde: {archivo}", Colores.CYAN)
            
            with open(archivo_path, 'r') as f:
                comandos = [linea.strip() for linea in f.readlines() if linea.strip() and not linea.startswith('#')]
            
            for i, comando in enumerate(comandos, 1):
                imprimir_color(f"📤 [{i}/{len(comandos)}] {comando}", Colores.CYAN)
                self.cliente.enviar_comando(comando)
                time.sleep(1.5)  # Pausa entre comandos
            
            imprimir_color("✅ Batch completado", Colores.GREEN)
            
        except Exception as e:
            imprimir_color(f"❌ Error ejecutando batch: {e}", Colores.RED)


def crear_archivo_batch_ejemplo():
    """Crea un archivo de ejemplo para modo batch."""
    contenido_batch = """# Archivo de ejemplo para modo batch
# Líneas que empiezan con # son comentarios

# Verificar estado del sistema
estado

# Obtener información de resolución
resolucion

# Realizar test de captura
test

# Tomar una foto con nombre personalizado
foto:batch_test

# Listar archivos
listar

# Obtener estadísticas
estadisticas
"""
    
    archivo_batch = Path("ejemplo_batch.txt")
    archivo_batch.write_text(contenido_batch)
    imprimir_color(f"📄 Archivo de ejemplo creado: {archivo_batch}", Colores.GREEN)


def detectar_puertos_disponibles() -> List[str]:
    """
    Detecta puertos serie disponibles.
    
    Returns:
        List[str]: Lista de puertos disponibles
    """
    puertos = []
    
    # Puertos comunes en sistemas Unix
    puertos_unix = [
        '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2',
        '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2',
        '/dev/ttyS0', '/dev/ttyS1', '/dev/ttyAMA0'
    ]
    
    for puerto in puertos_unix:
        if Path(puerto).exists():
            puertos.append(puerto)
    
    # En Windows, usar pyserial para detectar
    try:
        import serial.tools.list_ports
        for port_info in serial.tools.list_ports.comports():
            puertos.append(port_info.device)
    except ImportError:
        pass
    
    return puertos


def configurar_argumentos():
    """Configura argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Cliente de pruebas para sistema de cámara UART",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python cliente_foto.py                                    # Modo interactivo por defecto
  python cliente_foto.py -p /dev/ttyUSB0 -b 57600         # Puerto y velocidad específicos
  python cliente_foto.py -c "foto;estado;listar"          # Comandos específicos
  python cliente_foto.py --auto                           # Modo automático de pruebas
  python cliente_foto.py --batch ejemplo_batch.txt        # Ejecutar desde archivo
        """
    )
    
    parser.add_argument(
        '-p', '--puerto',
        help='Puerto serie a utilizar (default: detectar automáticamente)'
    )
    
    parser.add_argument(
        '-b', '--baudrate',
        type=int,
        default=115200,
        help='Velocidad de comunicación (default: 115200)'
    )
    
    parser.add_argument(
        '-c', '--comandos',
        help='Comandos a ejecutar separados por ; (ej: "foto;estado;listar")'
    )
    
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Ejecutar secuencia automática de pruebas'
    )
    
    parser.add_argument(
        '--batch',
        help='Ejecutar comandos desde archivo'
    )
    
    parser.add_argument(
        '--timeout',
        type=float,
        default=5.0,
        help='Timeout para comandos (default: 5.0 segundos)'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Deshabilitar colores en salida'
    )
    
    parser.add_argument(
        '--crear-batch-ejemplo',
        action='store_true',
        help='Crear archivo de ejemplo para modo batch'
    )
    
    return parser.parse_args()


def main():
    """Función principal del cliente."""
    # Banner
    imprimir_banner()
    
    # Argumentos
    args = configurar_argumentos()
    
    # Deshabilitar colores si se solicita
    if args.no_color:
        for attr in dir(Colores):
            if not attr.startswith('_'):
                setattr(Colores, attr, '')
    
    # Crear archivo batch de ejemplo si se solicita
    if args.crear_batch_ejemplo:
        crear_archivo_batch_ejemplo()
        return 0
    
    # Detectar puerto si no se especifica
    puerto = args.puerto
    if not puerto:
        puertos_disponibles = detectar_puertos_disponibles()
        if puertos_disponibles:
            puerto = puertos_disponibles[0]
            imprimir_color(f"🔍 Puerto detectado automáticamente: {puerto}", Colores.CYAN)
        else:
            imprimir_color("❌ No se detectaron puertos serie disponibles", Colores.RED)
            print("💡 Especifica un puerto manualmente con -p /dev/ttyUSB0")
            return 1
    
    # Mostrar configuración
    print(f"🔌 Puerto: {puerto}")
    print(f"⚡ Velocidad: {args.baudrate} baudios")
    print()
    
    try:
        # Crear cliente
        cliente = ClienteUART(puerto, args.baudrate)
        
        # Conectar
        if not cliente.conectar():
            imprimir_color("❌ No se pudo establecer conexión", Colores.RED)
            return 1
        
        # Ejecutar según modo
        if args.comandos:
            # Modo comandos específicos
            comandos = args.comandos.split(';')
            imprimir_color(f"🚀 Ejecutando {len(comandos)} comandos...", Colores.CYAN)
            
            for comando in comandos:
                comando = comando.strip()
        # Ejecutar según modo
        if args.comandos:
            # Modo comandos específicos
            comandos = args.comandos.split(';')
            imprimir_color(f"🚀 Ejecutando {len(comandos)} comandos...", Colores.CYAN)
            
            for comando in comandos:
                comando = comando.strip()
                if comando:
                    cliente.enviar_comando(comando)
                    time.sleep(2.0)  # Pausa entre comandos
            
            # Esperar respuestas finales
            time.sleep(3.0)
        
        elif args.auto:
            # Modo automático
            interfaz = InterfazInteractiva(cliente)
            interfaz._ejecutar_modo_automatico()
        
        elif args.batch:
            # Modo batch
            interfaz = InterfazInteractiva(cliente)
            interfaz._ejecutar_batch(args.batch)
        
        else:
            # Modo interactivo
            interfaz = InterfazInteractiva(cliente)
            interfaz.ejecutar()
        
    except KeyboardInterrupt:
        imprimir_color("\n👋 Interrumpido por usuario", Colores.YELLOW)
    except Exception as e:
        imprimir_color(f"❌ Error: {e}", Colores.RED)
        return 1
    finally:
        try:
            cliente.desconectar()
        except:
            pass
    
    return 0


if __name__ == "__main__":
    try:
        codigo_salida = main()
        sys.exit(codigo_salida)
    except Exception as e:
        imprimir_color(f"❌ Error fatal: {e}", Colores.RED)
        sys.exit(1)
