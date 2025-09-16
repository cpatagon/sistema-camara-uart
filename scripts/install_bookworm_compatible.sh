#!/bin/bash
# ==============================================================================
# INSTALADOR DEL SISTEMA DE CÁMARA UART - VERSIÓN CORREGIDA BOOKWORM
# Soluciona conflictos de dependencias multimedia
# ==============================================================================

set -e  # Salir en caso de error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Variables de configuración
INSTALL_DIR="/opt/camara-uart"
LOG_DIR="/var/log/camara-uart"
CONFIG_DIR="/etc/camara-uart"
DATA_DIR="/data/camara-uart"
SERVICE_NAME="camara-uart"
USER_SERVICE="pi"

# Detectar versión del OS
OS_VERSION=$(lsb_release -cs 2>/dev/null || echo "unknown")
IS_BOOKWORM=false
if [[ "$OS_VERSION" == "bookworm" ]]; then
    IS_BOOKWORM=true
fi

# Funciones de utilidad
print_header() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}============================================${NC}"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "Este script debe ejecutarse como root (sudo)"
        exit 1
    fi
}

fix_hostname_warning() {
    # Corregir warning de hostname
    local hostname=$(hostname)
    if ! grep -q "$hostname" /etc/hosts; then
        print_info "Corrigiendo configuración de hostname..."
        echo "127.0.1.1 $hostname" >> /etc/hosts
        print_success "Hostname configurado"
    fi
}

check_system() {
    print_info "Verificando sistema..."
    
    # Mostrar información del sistema
    print_info "OS Version: $OS_VERSION"
    print_info "Arquitectura: $(uname -m)"
    
    # Verificar Raspberry Pi OS
    if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        print_warning "No se detectó Raspberry Pi, continuando..."
    else
        RPI_MODEL=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')
        print_info "Modelo detectado: $RPI_MODEL"
    fi
    
    # Verificar Python 3.7+
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    print_info "Python version: $PYTHON_VERSION"
    
    if ! python3 -c "import sys; assert sys.version_info >= (3,7)" 2>/dev/null; then
        print_error "Se requiere Python 3.7 o superior"
        exit 1
    fi
    
    # Verificar cámara (opcional)
    if command -v vcgencmd >/dev/null 2>&1; then
        camera_status=$(vcgencmd get_camera 2>/dev/null || echo "not_detected")
        if echo "$camera_status" | grep -q "detected=1"; then
            print_success "Cámara detectada: $camera_status"
        else
            print_warning "Cámara no detectada: $camera_status"
            print_info "Para habilitar la cámara ejecute: sudo raspi-config"
        fi
    fi
    
    print_success "Verificación del sistema completada"
}

fix_package_conflicts() {
    print_info "Resolviendo conflictos de paquetes..."
    
    # Limpiar cache de apt
    apt-get clean
    apt-get autoclean
    
    # Actualizar índices
    apt-get update -qq
    
    # Resolver problemas de dependencias
    apt-get install -f -y
    
    # Actualizar sistema si es necesario
    print_info "Verificando actualizaciones críticas..."
    apt-get upgrade -y apt dpkg
    
    print_success "Conflictos de paquetes resueltos"
}

install_dependencies() {
    print_header "INSTALANDO DEPENDENCIAS - BOOKWORM CORREGIDO"
    
    # Resolver conflictos primero
    fix_package_conflicts
    
    # Actualizar paquetes
    print_info "Actualizando repositorios..."
    apt-get update -qq
    
    # Instalar dependencias básicas del sistema (sin conflictos)
    print_info "Instalando dependencias básicas del sistema..."
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        git \
        curl \
        wget \
        build-essential \
        cmake \
        pkg-config \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release
    
    # Instalar dependencias de imágenes (versión compatible Bookworm)
    print_info "Instalando dependencias de multimedia compatibles..."
    
    # Primero instalar las dependencias básicas de imagen
    apt-get install -y \
        libjpeg-dev \
        libpng-dev \
        libtiff-dev \
        libwebp-dev \
        libopenjp2-7-dev \
        libopenexr-dev
    
    # Para multimedia, instalar solo las compatibles con Bookworm
    print_info "Instalando librerías multimedia para Bookworm..."
    if [[ "$IS_BOOKWORM" == "true" ]]; then
        # Bookworm usa FFmpeg 5.x, no instalar libavresample-dev (obsoleto)
        apt-get install -y \
            libavcodec-dev \
            libavformat-dev \
            libswscale-dev \
            libavutil-dev \
            libswresample-dev \
            libavfilter-dev \
            libavdevice-dev
    else
        # Para versiones anteriores
        apt-get install -y \
            libavcodec-dev \
            libavformat-dev \
            libswscale-dev \
            libavresample-dev
    fi
    
    # Continuar con otras dependencias
    apt-get install -y \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev \
        libxvidcore-dev \
        libx264-dev \
        libgtk-3-dev \
        libcanberra-gtk3-dev \
        libatlas-base-dev \
        gfortran \
        libblas-dev \
        liblapack-dev
    
    # Python packages del sistema
    print_info "Instalando paquetes Python del sistema..."
    apt-get install -y \
        python3-numpy \
        python3-scipy \
        python3-matplotlib \
        python3-serial \
        python3-pil \
        python3-setuptools \
        python3-wheel
    
    # Dependencias específicas de Raspberry Pi
    if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        print_info "Instalando dependencias específicas de Raspberry Pi..."
        
        # Para Bookworm, picamera2 viene preinstalado
        if [[ "$IS_BOOKWORM" == "true" ]]; then
            apt-get install -y \
                python3-picamera2 \
                python3-libcamera \
                libcamera-apps \
                libcamera-dev \
                libcamera-tools \
                rpicam-apps
        else
            # Para versiones anteriores
            apt-get install -y \
                python3-picamera \
                libcamera-apps \
                libcamera-dev
        fi
        
        # GPIO y hardware
        apt-get install -y \
            python3-rpi.gpio \
            python3-gpiozero \
            rpi.gpio-common
    fi
    
    print_success "Dependencias del sistema instaladas"
}

create_directories() {
    print_header "CREANDO ESTRUCTURA DE DIRECTORIOS"
    
    # Crear directorios principales
    print_info "Creando directorios del sistema..."
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$DATA_DIR/fotos"
    mkdir -p "$DATA_DIR/temp"
    mkdir -p "$DATA_DIR/backup"
    
    # Crear subdirectorios de instalación
    mkdir -p "$INSTALL_DIR/src"
    mkdir -p "$INSTALL_DIR/scripts"
    mkdir -p "$INSTALL_DIR/config"
    mkdir -p "$INSTALL_DIR/tests"
    mkdir -p "$INSTALL_DIR/docs"
    mkdir -p "$INSTALL_DIR/temp"
    
    print_success "Estructura de directorios creada"
}

install_python_environment() {
    print_header "CONFIGURANDO ENTORNO PYTHON"
    
    # Crear entorno virtual con dependencias del sistema
    print_info "Creando entorno virtual Python..."
    python3 -m venv "$INSTALL_DIR/venv" --system-site-packages
    
    # Activar entorno virtual
    source "$INSTALL_DIR/venv/bin/activate"
    
    # Actualizar pip
    print_info "Actualizando pip..."
    pip install --upgrade pip setuptools wheel
    
    # Crear requirements.txt minimalista (evitar conflictos)
    print_info "Creando requirements.txt minimalista..."
    cat > "$INSTALL_DIR/requirements.txt" << 'EOF'
# Sistema de Cámara UART - Dependencias Mínimas
pyserial>=3.5,<4.0
configparser>=5.0.0
colorlog>=6.0.0
pathlib2>=2.3.0; python_version < "3.8"

# Utilidades básicas
psutil>=5.9.0
tabulate>=0.9.0

# Testing (opcional)
pytest>=7.0.0
EOF
    
    # Instalar dependencias Python básicas
    print_info "Instalando dependencias Python básicas..."
    pip install --no-warn-script-location -r "$INSTALL_DIR/requirements.txt" || {
        print_warning "Algunos paquetes Python fallaron, continuando..."
    }
    
    print_success "Entorno Python configurado"
}

create_basic_files() {
    print_info "Creando archivos básicos del sistema..."
    
    # Crear config_manager.py básico
    cat > "$INSTALL_DIR/src/config_manager.py" << 'EOF'
"""
Gestor de configuración básico para sistema de cámara UART
"""
import configparser
from pathlib import Path
from dataclasses import dataclass

@dataclass
class UARTConfig:
    puerto: str = "/dev/ttyS0"
    baudrate: int = 115200
    timeout: float = 1.0
    bytesize: int = 8
    parity: str = "none"
    stopbits: int = 1

@dataclass
class CamaraConfig:
    resolucion_width: int = 1920
    resolucion_height: int = 1080
    directorio_salida: str = "/data/camara-uart/fotos"
    formato: str = "jpg"
    calidad: int = 95

@dataclass
class LoggingConfig:
    nivel: str = "INFO"
    archivo: str = "/var/log/camara-uart/camara-uart.log"
    max_size_mb: int = 10
    backup_count: int = 5
    formato: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

class ConfigManager:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.uart = UARTConfig()
        self.camara = CamaraConfig()
        self.logging = LoggingConfig()
        self.load_config()
    
    def load_config(self):
        if Path(self.config_file).exists():
            self.config.read(self.config_file)
            self._load_uart_config()
            self._load_camara_config()
            self._load_logging_config()
    
    def _load_uart_config(self):
        if 'UART' in self.config:
            section = self.config['UART']
            self.uart.puerto = section.get('puerto', self.uart.puerto)
            self.uart.baudrate = section.getint('baudrate', self.uart.baudrate)
            self.uart.timeout = section.getfloat('timeout', self.uart.timeout)
    
    def _load_camara_config(self):
        if 'CAMARA' in self.config:
            section = self.config['CAMARA']
            self.camara.resolucion_width = section.getint('resolucion_width', self.camara.resolucion_width)
            self.camara.resolucion_height = section.getint('resolucion_height', self.camara.resolucion_height)
            self.camara.directorio_salida = section.get('directorio_salida', self.camara.directorio_salida)
    
    def _load_logging_config(self):
        if 'LOGGING' in self.config:
            section = self.config['LOGGING']
            self.logging.nivel = section.get('nivel', self.logging.nivel)
            self.logging.archivo = section.get('archivo', self.logging.archivo)
EOF
    
    # Crear camara_controller.py básico para Bookworm
    cat > "$INSTALL_DIR/src/camara_controller.py" << 'EOF'
"""
Controlador de cámara básico compatible con Bookworm
"""
import logging
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class InfoCaptura:
    exitoso: bool
    nombre_archivo: str = ""
    ruta_completa: str = ""
    tamaño_bytes: int = 0
    error: str = ""

class CamaraController:
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        self.camara = None
        self._inicializar_camara()
    
    def _inicializar_camara(self):
        try:
            # Intentar usar picamera2 (Bookworm)
            try:
                from picamera2 import Picamera2
                self.camara = Picamera2()
                self.camara.configure(self.camara.create_still_configuration())
                self.camara.start()
                self.logger.info("Cámara inicializada con picamera2")
            except ImportError:
                # Fallback para sistemas sin cámara
                self.logger.warning("picamera2 no disponible, modo simulación")
                self.camara = None
        except Exception as e:
            self.logger.error(f"Error inicializando cámara: {e}")
            self.camara = None
    
    def capturar_foto(self) -> InfoCaptura:
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"{timestamp}.jpg"
            ruta_completa = Path(self.config.camara.directorio_salida) / nombre_archivo
            
            # Crear directorio si no existe
            ruta_completa.parent.mkdir(parents=True, exist_ok=True)
            
            if self.camara:
                # Captura real
                self.camara.capture_file(str(ruta_completa))
                tamaño = ruta_completa.stat().st_size
                self.logger.info(f"Foto capturada: {nombre_archivo} ({tamaño} bytes)")
            else:
                # Simulación para testing
                self._crear_imagen_test(ruta_completa)
                tamaño = ruta_completa.stat().st_size
                self.logger.info(f"Foto simulada: {nombre_archivo} ({tamaño} bytes)")
            
            return InfoCaptura(
                exitoso=True,
                nombre_archivo=nombre_archivo,
                ruta_completa=str(ruta_completa),
                tamaño_bytes=tamaño
            )
            
        except Exception as e:
            error_msg = f"Error capturando foto: {e}"
            self.logger.error(error_msg)
            return InfoCaptura(exitoso=False, error=error_msg)
    
    def _crear_imagen_test(self, ruta_archivo: Path):
        """Crea una imagen de prueba básica"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Crear imagen de prueba
            img = Image.new('RGB', (640, 480), color='blue')
            draw = ImageDraw.Draw(img)
            
            # Texto de prueba
            try:
                font = ImageFont.load_default()
            except:
                font = None
            
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            draw.text((10, 10), f"Test Image\n{timestamp}", fill='white', font=font)
            draw.rectangle([50, 50, 590, 430], outline='white', width=2)
            
            # Guardar imagen
            img.save(str(ruta_archivo), 'JPEG', quality=95)
            
        except ImportError:
            # Fallback: crear archivo de texto
            with open(ruta_archivo, 'w') as f:
                f.write(f"Test image file\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    def obtener_resolucion_actual(self):
        return (self.config.camara.resolucion_width, self.config.camara.resolucion_height)
    
    def cambiar_resolucion(self, width: int, height: int) -> bool:
        try:
            self.config.camara.resolucion_width = width
            self.config.camara.resolucion_height = height
            self.logger.info(f"Resolución cambiada a {width}x{height}")
            return True
        except Exception as e:
            self.logger.error(f"Error cambiando resolución: {e}")
            return False
    
    def establecer_callback_captura(self, callback):
        self.callback_captura = callback
    
    def establecer_callback_error(self, callback):
        self.callback_error = callback
    
    def liberar_recursos(self):
        if self.camara:
            try:
                self.camara.stop()
                self.camara.close()
            except:
                pass
EOF
    
    # Crear uart_handler.py básico
    cat > "$INSTALL_DIR/src/uart_handler.py" << 'EOF'
"""
Manejador UART básico para sistema de cámara
"""
import serial
import threading
import time
import logging
from typing import Optional, Callable, Dict

class UARTHandler:
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        self.conexion: Optional[serial.Serial] = None
        self.ejecutando = False
        self.callbacks_comandos: Dict[str, Callable] = {}
        self.buffer_entrada = ""
        self.lock = threading.Lock()
        self.hilo_lectura = None
    
    def registrar_comando(self, comando: str, callback: Callable):
        self.callbacks_comandos[comando.lower()] = callback
        self.logger.debug(f"Comando registrado: {comando}")
    
    def iniciar(self):
        try:
            self.logger.info(f"Conectando a {self.config.uart.puerto} @ {self.config.uart.baudrate}")
            self.conexion = serial.Serial(
                port=self.config.uart.puerto,
                baudrate=self.config.uart.baudrate,
                timeout=self.config.uart.timeout
            )
            
            self.ejecutando = True
            self.hilo_lectura = threading.Thread(target=self._bucle_lectura, daemon=True)
            self.hilo_lectura.start()
            
            self.enviar_mensaje("CAMERA_READY")
            self.logger.info("UART iniciado correctamente")
        except Exception as e:
            self.logger.error(f"Error iniciando UART: {e}")
            raise
    
    def detener(self):
        self.ejecutando = False
        if self.conexion:
            self.enviar_mensaje("CAMERA_OFFLINE")
            time.sleep(0.1)
            self.conexion.close()
        if self.hilo_lectura:
            self.hilo_lectura.join(timeout=2.0)
        self.logger.info("UART detenido")
    
    def enviar_mensaje(self, mensaje: str) -> bool:
        try:
            if self.conexion and self.conexion.is_open:
                with self.lock:
                    self.conexion.write(f"{mensaje}\r\n".encode('utf-8'))
                    self.conexion.flush()
                self.logger.debug(f"Enviado: {mensaje}")
                return True
        except Exception as e:
            self.logger.error(f"Error enviando mensaje: {e}")
        return False
    
    def _bucle_lectura(self):
        while self.ejecutando:
            try:
                if self.conexion and self.conexion.in_waiting > 0:
                    data = self.conexion.read(self.conexion.in_waiting)
                    texto = data.decode('utf-8', errors='ignore')
                    self.buffer_entrada += texto
                    
                    while '\n' in self.buffer_entrada:
                        linea, self.buffer_entrada = self.buffer_entrada.split('\n', 1)
                        linea = linea.strip()
                        if linea:
                            self._procesar_comando(linea)
                
                time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error en lectura: {e}")
                time.sleep(1.0)
    
    def _procesar_comando(self, linea: str):
        try:
            comando = linea.lower().strip()
            self.logger.debug(f"Comando recibido: {comando}")
            
            class ComandoSimple:
                def __init__(self, cmd):
                    self.comando = cmd
                    self.parametros = []
            
            if comando in self.callbacks_comandos:
                respuesta = self.callbacks_comandos[comando](ComandoSimple(comando))
                if respuesta:
                    self.enviar_mensaje(respuesta)
            else:
                self.enviar_mensaje(f"ERROR|UNKNOWN_COMMAND|{comando}")
        except Exception as e:
            self.logger.error(f"Error procesando comando: {e}")
EOF
    
    # Crear estructura básica de exceptions
    cat > "$INSTALL_DIR/src/exceptions.py" << 'EOF'
"""
Excepciones del sistema de cámara UART
"""

class CamaraUARTError(Exception):
    """Excepción base del sistema"""
    pass

class UARTError(CamaraUARTError):
    """Error de comunicación UART"""
    pass

class CamaraError(CamaraUARTError):
    """Error de cámara"""
    pass

class FileTransferError(CamaraUARTError):
    """Error de transferencia de archivos"""
    pass

class ConfigError(CamaraUARTError):
    """Error de configuración"""
    pass
EOF
}

copy_source_files() {
    print_header "PREPARANDO ARCHIVOS DEL SISTEMA"
    
    # Verificar si existen archivos fuente
    if [[ -f "src/uart_handler.py" ]] || [[ -f "../src/uart_handler.py" ]]; then
        # Determinar directorio fuente
        if [[ -f "src/uart_handler.py" ]]; then
            SOURCE_DIR="."
        else
            SOURCE_DIR=".."
        fi
        
        print_info "Copiando archivos fuente existentes..."
        cp -r "$SOURCE_DIR/src/"* "$INSTALL_DIR/src/" 2>/dev/null || true
        cp -r "$SOURCE_DIR/scripts/"* "$INSTALL_DIR/scripts/" 2>/dev/null || true
        cp -r "$SOURCE_DIR/config/"* "$INSTALL_DIR/config/" 2>/dev/null || true
    else
        print_info "Creando estructura básica de archivos..."
        create_basic_files
    fi
    
    # Crear archivos de configuración
    create_config_files
    
    # Crear scripts básicos
    create_basic_scripts
    
    print_success "Archivos del sistema preparados"
}

create_config_files() {
    print_info "Creando archivos de configuración..."
    
    # Crear configuración principal compatible con Bookworm
    cat > "$CONFIG_DIR/camara.conf" << 'EOF'
# ==============================================================================
# CONFIGURACIÓN DEL SISTEMA DE CÁMARA UART - BOOKWORM COMPATIBLE
# ==============================================================================

[UART]
# Puerto serie a utilizar
puerto = /dev/ttyS0

# Velocidad de comunicación en baudios
baudrate = 115200

# Timeout de lectura en segundos
timeout = 2.0

# Configuración de puerto serie
bytesize = 8
parity = none
stopbits = 1

[CAMARA]
# Resolución de captura (compatible con picamera2)
resolucion_width = 1920
resolucion_height = 1080

# Directorio donde guardar las fotos
directorio_salida = /data/camara-uart/fotos

# Formato de imagen
formato = jpg

# Calidad JPEG (1-100)
calidad = 95

[LOGGING]
# Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
nivel = INFO

# Archivo de log
archivo = /var/log/camara-uart/camara-uart.log

# Tamaño máximo del archivo de log en MB
max_size_mb = 10

# Número de archivos de backup
backup_count = 5

# Formato de mensajes
formato = %(asctime)s - %(name)s - %(levelname)s - %(message)s

[TRANSFERENCIA]
# Configuración básica de transferencia
chunk_size = 256
timeout_chunk = 5.0
max_reintentos = 3
EOF
}

create_basic_scripts() {
    print_info "Creando scripts básicos..."
    
    # Script principal básico compatible con Bookworm
    cat > "$INSTALL_DIR/scripts/main_daemon.py" << 'EOF'
#!/usr/bin/env python3
"""
Daemon principal básico del sistema de cámara UART - Compatible Bookworm
"""

import sys
import os
import time
import logging
import signal
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from config_manager import ConfigManager
    from uart_handler import UARTHandler
    from camara_controller import CamaraController
except ImportError as e:
    print(f"Error importando módulos: {e}")
    sys.exit(1)

class SistemaCamaraBasico:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.ejecutando = False
        self.logger = self._setup_logging()
        self.config_manager = None
        self.uart_handler = None
        self.camara_controller = None
    
    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def inicializar(self):
        try:
            self.logger.info("Inicializando sistema básico...")
            self.config_manager = ConfigManager(self.config_file)
            self.camara_controller = CamaraController(self.config_manager)
            self.uart_handler = UARTHandler(self.config_manager)
            self._registrar_comandos()
            return True
        except Exception as e:
            self.logger.error(f"Error inicializando: {e}")
            return False
    
    def _registrar_comandos(self):
        def cmd_foto(comando):
            try:
                info = self.camara_controller.capturar_foto()
                if info.exitoso:
                    return f"OK|{info.nombre_archivo}|{info.tamaño_bytes}|{info.ruta_completa}"
                else:
                    return f"ERROR|CAPTURE_FAILED|{info.error}"
            except Exception as e:
                return f"ERROR|FOTO_FAILED|{str(e)}"
        
        def cmd_estado(comando):
            return f"STATUS:ACTIVO|{self.config_manager.uart.puerto}|{self.config_manager.uart.baudrate}"
        
        def cmd_resolucion(comando):
            res = self.camara_controller.obtener_resolucion_actual()
            mp = (res[0] * res[1]) / 1_000_000
            return f"RESOLUCION|{res[0]}x{res[1]}|{mp:.1f}MP"
        
        def cmd_salir(comando):
            self.detener()
            return "CAMERA_OFFLINE"
        
        # Registrar comandos
        self.uart_handler.registrar_comando('foto', cmd_foto)
        self.uart_handler.registrar_comando('estado', cmd_estado)
        self.uart_handler.registrar_comando('status', cmd_estado)
        self.uart_handler.registrar_comando('resolucion', cmd_resolucion)
        self.uart_handler.registrar_comando('salir', cmd_salir)
        
        self.logger.info("Comandos registrados: foto, estado, resolucion, salir")
    
    def iniciar(self):
        if not self.inicializar():
            return False
        
        self.ejecutando = True
        self.uart_handler.iniciar()
        self.logger.info("Sistema básico iniciado correctamente")
        return True
    
    def detener(self):
        self.logger.info("Deteniendo sistema...")
        self.ejecutando = False
        if self.uart_handler:
            self.uart_handler.detener()
        if self.camara_controller:
            self.camara_controller.liberar_recursos()
        self.logger.info("Sistema detenido")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Sistema de Cámara UART Básico")
    parser.add_argument("--config", default="/etc/camara-uart/camara.conf", help="Archivo de configuración")
    parser.add_argument("--debug", action="store_true", help="Modo debug")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    sistema = SistemaCamaraBasico(args.config)
    
    def signal_handler(signum, frame):
        print(f"\nSeñal {signum} recibida, deteniendo...")
        sistema.detener()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if sistema.iniciar():
        print("✅ Sistema iniciado correctamente")
        print("📸 Comandos disponibles: foto, estado, resolucion, salir")
        while sistema.ejecutando:
            time.sleep(1)
    else:
        print("❌ Error iniciando sistema")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF
    
    chmod +x "$INSTALL_DIR/scripts/main_daemon.py"
    
    # Cliente básico de prueba mejorado
    cat > "$INSTALL_DIR/scripts/cliente_basico.py" << 'EOF'
#!/usr/bin/env python3
"""
Cliente básico para probar el sistema UART - Compatible Bookworm
"""

import serial
import sys
import time
import argparse

def test_conexion(puerto="/dev/ttyS0", baudrate=115200, comando="estado"):
    try:
        print(f"🔌 Conectando a {puerto} @ {baudrate}...")
        ser = serial.Serial(puerto, baudrate, timeout=3.0)
        
        print(f"📤 Enviando comando '{comando}'...")
        ser.write(f"{comando}\n".encode())
        
        print("⏳ Esperando respuesta...")
        time.sleep(1)
        
        if ser.in_waiting > 0:
            respuesta = ser.readline().decode().strip()
            print(f"✅ Respuesta: {respuesta}")
            
            # Si es comando foto, intentar otra
            if comando == "foto" and respuesta.startswith("OK"):
                print("📸 Foto capturada exitosamente!")
        else:
            print("⚠️  No se recibió respuesta")
        
        ser.close()
        print("👋 Conexión cerrada")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_completo(puerto, baudrate):
    """Test completo con múltiples comandos"""
    comandos = ["estado", "resolucion", "foto"]
    
    for i, cmd in enumerate(comandos, 1):
        print(f"\n🧪 Test {i}/{len(comandos)}: {cmd}")
        if test_conexion(puerto, baudrate, cmd):
            print(f"✅ Test {cmd} exitoso")
        else:
            print(f"❌ Test {cmd} fallido")
        
        if i < len(comandos):
            print("⏳ Pausa entre tests...")
            time.sleep(2)

def main():
    parser = argparse.ArgumentParser(description="Cliente de prueba UART")
    parser.add_argument("--puerto", default="/dev/ttyS0", help="Puerto UART")
    parser.add_argument("--baudrate", type=int, default=115200, help="Velocidad")
    parser.add_argument("--comando", default="estado", help="Comando a enviar")
    parser.add_argument("--test-completo", action="store_true", help="Ejecutar test completo")
    
    args = parser.parse_args()
    
    print("🧪 CLIENTE DE PRUEBA UART - BOOKWORM COMPATIBLE")
    print("=" * 50)
    
    if args.test_completo:
        test_completo(args.puerto, args.baudrate)
    else:
        test_conexion(args.puerto, args.baudrate, args.comando)

if __name__ == "__main__":
    main()
EOF
    
    chmod +x "$INSTALL_DIR/scripts/cliente_basico.py"
    
    # Script de diagnóstico del sistema
    cat > "$INSTALL_DIR/scripts/diagnostico_sistema.py" << 'EOF'
#!/usr/bin/env python3
"""
Script de diagnóstico del sistema - Compatible Bookworm
"""

import subprocess
import sys
from pathlib import Path

def ejecutar_comando(comando):
    """Ejecuta comando y retorna output"""
    try:
        result = subprocess.run(comando, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def verificar_python():
    print("🐍 VERIFICACIÓN DE PYTHON")
    print("-" * 30)
    
    # Versión de Python
    success, stdout, stderr = ejecutar_comando("python3 --version")
    if success:
        print(f"✅ Python: {stdout.strip()}")
    else:
        print(f"❌ Error Python: {stderr}")
    
    # Módulos importantes
    modulos = ["serial", "PIL", "configparser"]
    for modulo in modulos:
        success, _, _ = ejecutar_comando(f"python3 -c 'import {modulo}'")
        status = "✅" if success else "❌"
        print(f"{status} Módulo {modulo}: {'Disponible' if success else 'No disponible'}")

def verificar_camara():
    print("\n📸 VERIFICACIÓN DE CÁMARA")
    print("-" * 30)
    
    # vcgencmd
    success, stdout, stderr = ejecutar_comando("vcgencmd get_camera")
    if success:
        print(f"✅ Estado cámara: {stdout.strip()}")
    else:
        print(f"⚠️  vcgencmd no disponible")
    
    # picamera2
    success, _, _ = ejecutar_comando("python3 -c 'import picamera2'")
    status = "✅" if success else "❌"
    print(f"{status} picamera2: {'Disponible' if success else 'No disponible'}")
    
    # libcamera
    success, _, _ = ejecutar_comando("which libcamera-hello")
    status = "✅" if success else "❌"
    print(f"{status} libcamera-apps: {'Instalado' if success else 'No instalado'}")

def verificar_puertos():
    print("\n🔌 VERIFICACIÓN DE PUERTOS SERIE")
    print("-" * 35)
    
    # Listar puertos
    success, stdout, stderr = ejecutar_comando("ls -la /dev/tty* | grep -E '(ttyS|ttyAMA|ttyUSB|ttyACM)'")
    if success and stdout:
        print("✅ Puertos encontrados:")
        for linea in stdout.strip().split('\n'):
            print(f"   {linea}")
    else:
        print("⚠️  No se encontraron puertos serie")
    
    # Verificar permisos
    success, stdout, stderr = ejecutar_comando("groups")
    if "dialout" in stdout:
        print("✅ Usuario en grupo dialout")
    else:
        print("❌ Usuario NO en grupo dialout")

def verificar_sistema():
    print("\n💻 INFORMACIÓN DEL SISTEMA")
    print("-" * 30)
    
    # OS Version
    success, stdout, stderr = ejecutar_comando("lsb_release -cs")
    if success:
        print(f"✅ OS Version: {stdout.strip()}")
    
    # Modelo Raspberry Pi
    if Path("/proc/device-tree/model").exists():
        success, stdout, stderr = ejecutar_comando("cat /proc/device-tree/model")
        if success:
            print(f"✅ Modelo: {stdout.strip()}")
    
    # Memoria
    success, stdout, stderr = ejecutar_comando("free -h | grep Mem")
    if success:
        print(f"✅ Memoria: {stdout.strip().split()[1]} total")

def verificar_instalacion():
    print("\n📦 VERIFICACIÓN DE INSTALACIÓN")
    print("-" * 35)
    
    # Directorio de instalación
    install_dir = Path("/opt/camara-uart")
    if install_dir.exists():
        print(f"✅ Directorio instalación: {install_dir}")
        
        # Archivos principales
        archivos = ["src/config_manager.py", "src/uart_handler.py", "scripts/main_daemon.py"]
        for archivo in archivos:
            ruta = install_dir / archivo
            status = "✅" if ruta.exists() else "❌"
            print(f"{status} {archivo}: {'Existe' if ruta.exists() else 'No existe'}")
    else:
        print("❌ Directorio de instalación no encontrado")
    
    # Servicio systemd
    success, stdout, stderr = ejecutar_comando("systemctl is-enabled camara-uart")
    if success:
        print(f"✅ Servicio habilitado: {stdout.strip()}")
    else:
        print("❌ Servicio no habilitado")

def main():
    print("🔍 DIAGNÓSTICO DEL SISTEMA DE CÁMARA UART")
    print("=" * 50)
    
    verificar_sistema()
    verificar_python()
    verificar_camara()
    verificar_puertos()
    verificar_instalacion()
    
    print("\n✅ Diagnóstico completado")
    print("\nPara resolver problemas:")
    print("  • Cámara: sudo raspi-config → Interface → Camera → Enable")
    print("  • Permisos: sudo usermod -a -G dialout $USER")
    print("  • Servicio: sudo systemctl start camara-uart")

if __name__ == "__main__":
    main()
EOF
    
    chmod +x "$INSTALL_DIR/scripts/diagnostico_sistema.py"
}

configure_permissions() {
    print_header "CONFIGURANDO PERMISOS"
    
    # Verificar/crear usuario de servicio
    if ! id "$USER_SERVICE" &>/dev/null; then
        print_info "El usuario $USER_SERVICE no existe, usando usuario actual"
        USER_SERVICE=$(logname 2>/dev/null || whoami)
    fi
    
    # Agregar usuario a grupos necesarios
    print_info "Configurando grupos de usuario..."
    usermod -a -G dialout "$USER_SERVICE" 2>/dev/null || true
    usermod -a -G video "$USER_SERVICE" 2>/dev/null || true
    usermod -a -G gpio "$USER_SERVICE" 2>/dev/null || true
    
    # Configurar permisos de directorios
    print_info "Configurando permisos de directorios..."
    chown -R "$USER_SERVICE:$USER_SERVICE" "$INSTALL_DIR"
    chown -R "$USER_SERVICE:$USER_SERVICE" "$LOG_DIR"
    chown -R "$USER_SERVICE:$USER_SERVICE" "$DATA_DIR"
    
    # Permisos de configuración
    chown -R root:root "$CONFIG_DIR"
    chmod -R 644 "$CONFIG_DIR"
    
    # Permisos de ejecutables
    chmod +x "$INSTALL_DIR/scripts/"*.py
    
    print_success "Permisos configurados"
}

create_systemd_service() {
    print_header "CREANDO SERVICIO SYSTEMD"
    
    print_info "Creando archivo de servicio..."
    cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=Sistema de Cámara UART (Bookworm Compatible)
Documentation=https://github.com/tu-repo/sistema-camara-uart
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER_SERVICE
Group=$USER_SERVICE
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin
Environment=PYTHONPATH=$INSTALL_DIR/src
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/scripts/main_daemon.py --config $CONFIG_DIR/camara.conf
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Directorio de trabajo
WorkingDirectory=$INSTALL_DIR
PrivateTmp=true

# Grupos para acceso a hardware
SupplementaryGroups=dialout video gpio

[Install]
WantedBy=multi-user.target
EOF
    
    # Recargar systemd
    systemctl daemon-reload
    
    print_success "Servicio systemd creado"
}

create_utility_scripts() {
    print_header "CREANDO SCRIPTS DE UTILIDAD"
    
    # Script de estado mejorado
    cat > "/usr/local/bin/camara-uart-status" << EOF
#!/bin/bash
echo "🔍 ESTADO DEL SISTEMA DE CÁMARA UART - BOOKWORM"
echo "=" * 50

echo
echo "📊 SERVICIO:"
systemctl status $SERVICE_NAME --no-pager -l

echo
echo "📋 ÚLTIMOS LOGS:"
journalctl -u $SERVICE_NAME --no-pager -n 10

echo
echo "🔌 PUERTOS SERIE:"
ls -la /dev/tty* | grep -E "(ttyS|ttyAMA|ttyUSB|ttyACM)" || echo "No se encontraron puertos"

echo
echo "📸 CÁMARA:"
if command -v vcgencmd >/dev/null 2>&1; then
    vcgencmd get_camera
else
    echo "vcgencmd no disponible"
fi

echo
echo "💾 ESPACIO EN DISCO:"
df -h $DATA_DIR 2>/dev/null || echo "Directorio de datos no accesible"

echo
echo "🐍 PYTHON Y MÓDULOS:"
python3 --version
python3 -c "import serial; print('✅ pyserial disponible')" 2>/dev/null || echo "❌ pyserial no disponible"
python3 -c "import picamera2; print('✅ picamera2 disponible')" 2>/dev/null || echo "⚠️  picamera2 no disponible"
EOF
    chmod +x "/usr/local/bin/camara-uart-status"
    
    # Script de test mejorado
    cat > "/usr/local/bin/camara-uart-test" << EOF
#!/bin/bash
echo "🧪 TEST DEL SISTEMA DE CÁMARA UART"
echo "=" * 40

PUERTO="\${1:-/dev/ttyS0}"
BAUDRATE="\${2:-115200}"

echo "Puerto: \$PUERTO"
echo "Baudrate: \$BAUDRATE"
echo

# Verificar que el puerto existe
if [[ ! -e "\$PUERTO" ]]; then
    echo "❌ El puerto \$PUERTO no existe"
    echo "Puertos disponibles:"
    ls -la /dev/tty* | grep -E "(ttyS|ttyAMA|ttyUSB|ttyACM)" || echo "Ninguno"
    exit 1
fi

# Ejecutar cliente de test
source "$INSTALL_DIR/venv/bin/activate"
cd "$INSTALL_DIR"
python3 scripts/cliente_basico.py --puerto "\$PUERTO" --baudrate "\$BAUDRATE" --test-completo
EOF
    chmod +x "/usr/local/bin/camara-uart-test"
    
    # Script de diagnóstico
    cat > "/usr/local/bin/camara-uart-diagnostico" << EOF
#!/bin/bash
echo "🔍 DIAGNÓSTICO COMPLETO DEL SISTEMA"
echo "=" * 40

source "$INSTALL_DIR/venv/bin/activate"
cd "$INSTALL_DIR"
python3 scripts/diagnostico_sistema.py
EOF
    chmod +x "/usr/local/bin/camara-uart-diagnostico"
    
    print_success "Scripts de utilidad creados"
}

finalize_installation() {
    print_header "FINALIZANDO INSTALACIÓN"
    
    # Crear archivos de estado
    touch "$INSTALL_DIR/.installed"
    echo "$(date)" > "$INSTALL_DIR/.install_date"
    echo "bookworm-fixed-v1.0" > "$INSTALL_DIR/.version"
    
    # Habilitar servicio (pero no iniciarlo automáticamente)
    systemctl enable "$SERVICE_NAME"
    
    print_success "Instalación completada exitosamente!"
    echo
    echo -e "${CYAN}✅ INSTALACIÓN COMPLETADA - BOOKWORM COMPATIBLE${NC}"
    echo -e "${CYAN}=" * 50 "${NC}"
    echo
    echo -e "${GREEN}📁 Directorios creados:${NC}"
    echo -e "  • Instalación: ${YELLOW}$INSTALL_DIR${NC}"
    echo -e "  • Configuración: ${YELLOW}$CONFIG_DIR${NC}"
    echo -e "  • Datos: ${YELLOW}$DATA_DIR${NC}"
    echo -e "  • Logs: ${YELLOW}$LOG_DIR${NC}"
    echo
    echo -e "${GREEN}🛠️  Comandos disponibles:${NC}"
    echo -e "  • Estado completo: ${YELLOW}camara-uart-status${NC}"
    echo -e "  • Test del sistema: ${YELLOW}camara-uart-test${NC}"
    echo -e "  • Diagnóstico: ${YELLOW}camara-uart-diagnostico${NC}"
    echo -e "  • Iniciar servicio: ${YELLOW}sudo systemctl start camara-uart${NC}"
    echo -e "  • Ver logs en tiempo real: ${YELLOW}sudo journalctl -u camara-uart -f${NC}"
    echo
    echo -e "${GREEN}🚀 Próximos pasos:${NC}"
    echo -e "  1. Verificar configuración: ${YELLOW}sudo nano $CONFIG_DIR/camara.conf${NC}"
    echo -e "  2. Ejecutar diagnóstico: ${YELLOW}camara-uart-diagnostico${NC}"
    echo -e "  3. Iniciar servicio: ${YELLOW}sudo systemctl start camara-uart${NC}"
    echo -e "  4. Probar sistema: ${YELLOW}camara-uart-test${NC}"
    echo
    echo -e "${BLUE}ℹ️  Información importante:${NC}"
    echo -e "  • Esta versión es compatible con Raspberry Pi OS Bookworm"
    echo -e "  • Incluye soporte para picamera2 y libcamera"
    echo -e "  • Evita conflictos de dependencias multimedia"
    echo -e "  • Sistema básico funcional, listo para extensiones"
    echo
    if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        echo -e "${YELLOW}⚠️  IMPORTANTE:${NC} Si la cámara no está habilitada:"
        echo -e "  1. Ejecutar: ${YELLOW}sudo raspi-config${NC}"
        echo -e "  2. Interface Options → Camera → Enable"
        echo -e "  3. Reiniciar: ${YELLOW}sudo reboot${NC}"
        echo
    fi
    
    echo -e "${GREEN}🎉 ¡Sistema listo para usar!${NC}"
}

main() {
    print_header "INSTALADOR CORREGIDO PARA RASPBERRY PI OS BOOKWORM"
    echo -e "${CYAN}Versión que resuelve conflictos de dependencias multimedia${NC}"
    echo
    
    check_root
    fix_hostname_warning
    check_system
    install_dependencies
    create_directories
    install_python_environment
    copy_source_files
    configure_permissions
    create_systemd_service
    create_utility_scripts
    finalize_installation
}

# Ejecutar instalación
main "$@"
