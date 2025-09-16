#!/bin/bash
# ==============================================================================
# INSTALADOR DEL SISTEMA DE CÁMARA UART INTEGRADO - COMPATIBLE BOOKWORM
# Versión corregida para Raspberry Pi OS Bookworm y sistemas modernos
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
    if ! grep -q "$(hostname)" /etc/hosts; then
        print_info "Corrigiendo configuración de hostname..."
        echo "127.0.1.1 $(hostname)" >> /etc/hosts
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

install_dependencies() {
    print_header "INSTALANDO DEPENDENCIAS - COMPATIBLE BOOKWORM"
    
    # Corregir repositorios si es necesario
    if [[ "$IS_BOOKWORM" == "true" ]]; then
        print_info "Configurando repositorios para Bookworm..."
        
        # Actualizar keyring si es necesario
        if [[ -f /etc/apt/trusted.gpg ]] && [[ $(stat -c%s /etc/apt/trusted.gpg) -gt 0 ]]; then
            print_info "Migrando keys GPG..."
            apt-key export | gpg --dearmour -o /etc/apt/trusted.gpg.d/migrated-from-deprecated-keyring.gpg 2>/dev/null || true
        fi
    fi
    
    # Actualizar paquetes
    print_info "Actualizando repositorios..."
    apt-get update -qq || {
        print_warning "Error en apt update, intentando limpiar cache..."
        apt-get clean
        apt-get update -qq
    }
    
    # Instalar dependencias básicas del sistema
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
    
    # Dependencias de imágenes y multimedia (compatibles con Bookworm)
    print_info "Instalando dependencias de multimedia..."
    apt-get install -y \
        libjpeg-dev \
        libpng-dev \
        libtiff-dev \
        libwebp-dev \
        libopenjp2-7-dev \
        libopenexr-dev \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        libavresample-dev \
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
    
    # Python packages del sistema (evitando conflictos)
    print_info "Instalando paquetes Python del sistema..."
    apt-get install -y \
        python3-numpy \
        python3-scipy \
        python3-matplotlib \
        python3-pandas \
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
                libcamera-tools
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
    print_header "CONFIGURANDO ENTORNO PYTHON COMPATIBLE"
    
    # Crear entorno virtual con dependencias del sistema
    print_info "Creando entorno virtual Python..."
    python3 -m venv "$INSTALL_DIR/venv" --system-site-packages
    
    # Activar entorno virtual
    source "$INSTALL_DIR/venv/bin/activate"
    
    # Actualizar pip
    print_info "Actualizando pip..."
    pip install --upgrade pip setuptools wheel
    
    # Crear requirements.txt compatible con Bookworm
    print_info "Creando requirements.txt compatible..."
    cat > "$INSTALL_DIR/requirements.txt" << 'EOF'
# Sistema de Cámara UART - Dependencias Python Compatible Bookworm
pyserial>=3.5,<4.0
configparser>=5.0.0
Pillow>=9.0.0
colorlog>=6.0.0
pathlib2>=2.3.0; python_version < "3.8"

# Dependencias opcionales para testing y desarrollo
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0

# Utilidades adicionales
psutil>=5.9.0
tabulate>=0.9.0
tqdm>=4.64.0
EOF
    
    # Instalar dependencias Python (evitando conflictos)
    print_info "Instalando dependencias Python..."
    pip install --no-warn-script-location -r "$INSTALL_DIR/requirements.txt"
    
    print_success "Entorno Python configurado"
}

copy_source_files() {
    print_header "COPIANDO Y CREANDO ARCHIVOS DEL SISTEMA"
    
    # Verificar que estamos en el directorio correcto o crear archivos
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
    
    def registrar_comando(self, comando: str, callback: Callable):
        self.callbacks_comandos[comando.lower()] = callback
    
    def iniciar(self):
        try:
            self.conexion = serial.Serial(
                port=self.config.uart.puerto,
                baudrate=self.config.uart.baudrate,
                timeout=self.config.uart.timeout
            )
            self.ejecutando = True
            self.enviar_mensaje("CAMERA_READY")
            self.logger.info("UART iniciado correctamente")
        except Exception as e:
            self.logger.error(f"Error iniciando UART: {e}")
            raise
    
    def detener(self):
        self.ejecutando = False
        if self.conexion:
            self.conexion.close()
    
    def enviar_mensaje(self, mensaje: str) -> bool:
        try:
            if self.conexion and self.conexion.is_open:
                self.conexion.write(f"{mensaje}\r\n".encode('utf-8'))
                return True
        except Exception as e:
            self.logger.error(f"Error enviando mensaje: {e}")
        return False
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

create_config_files() {
    print_info "Creando archivos de configuración..."
    
    # Crear configuración principal
    cat > "$CONFIG_DIR/camara.conf" << 'EOF'
# ==============================================================================
# CONFIGURACIÓN DEL SISTEMA DE CÁMARA UART
# Compatible con Raspberry Pi OS Bookworm
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
# Resolución de captura
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
# Tamaño de chunk para transferencias
chunk_size = 256

# Timeout por chunk
timeout_chunk = 5.0

# Reintentos máximos
max_reintentos = 3
EOF
}

create_basic_scripts() {
    print_info "Creando scripts básicos..."
    
    # Script principal básico
    cat > "$INSTALL_DIR/scripts/main_daemon.py" << 'EOF'
#!/usr/bin/env python3
"""
Daemon principal básico del sistema de cámara UART
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
    
    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def inicializar(self):
        try:
            self.config_manager = ConfigManager(self.config_file)
            self.uart_handler = UARTHandler(self.config_manager)
            self._registrar_comandos()
            return True
        except Exception as e:
            self.logger.error(f"Error inicializando: {e}")
            return False
    
    def _registrar_comandos(self):
        def cmd_estado(comando):
            return f"STATUS:ACTIVO|{self.config_manager.uart.puerto}|{self.config_manager.uart.baudrate}"
        
        def cmd_salir(comando):
            self.detener()
            return "CAMERA_OFFLINE"
        
        self.uart_handler.registrar_comando('estado', cmd_estado)
        self.uart_handler.registrar_comando('salir', cmd_salir)
    
    def iniciar(self):
        if not self.inicializar():
            return False
        
        self.ejecutando = True
        self.uart_handler.iniciar()
        self.logger.info("Sistema básico iniciado")
        return True
    
    def detener(self):
        self.ejecutando = False
        if self.uart_handler:
            self.uart_handler.detener()
        self.logger.info("Sistema detenido")

def main():
    config_file = sys.argv[1] if len(sys.argv) > 1 else "/etc/camara-uart/camara.conf"
    
    sistema = SistemaCamaraBasico(config_file)
    
    def signal_handler(signum, frame):
        print(f"\nSeñal {signum} recibida, deteniendo...")
        sistema.detener()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if sistema.iniciar():
        print("Sistema iniciado correctamente")
        while sistema.ejecutando:
            time.sleep(1)
    else:
        print("Error iniciando sistema")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF
    
    chmod +x "$INSTALL_DIR/scripts/main_daemon.py"
    
    # Cliente básico de prueba
    cat > "$INSTALL_DIR/scripts/cliente_basico.py" << 'EOF'
#!/usr/bin/env python3
"""
Cliente básico para probar el sistema UART
"""

import serial
import sys
import time

def test_conexion(puerto="/dev/ttyS0", baudrate=115200):
    try:
        print(f"Conectando a {puerto} @ {baudrate}...")
        ser = serial.Serial(puerto, baudrate, timeout=2.0)
        
        print("Enviando comando 'estado'...")
        ser.write(b"estado\n")
        
        time.sleep(1)
        if ser.in_waiting > 0:
            respuesta = ser.readline().decode().strip()
            print(f"Respuesta: {respuesta}")
        else:
            print("No se recibió respuesta")
        
        ser.close()
        print("Test completado")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    puerto = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyS0"
    baudrate = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
    test_conexion(puerto, baudrate)
EOF
    
    chmod +x "$INSTALL_DIR/scripts/cliente_basico.py"
}

configure_permissions() {
    print_header "CONFIGURANDO PERMISOS"
    
    # Verificar/crear usuario de servicio
    if ! id "$USER_SERVICE" &>/dev/null; then
        print_info "El usuario $USER_SERVICE no existe, usando usuario actual"
        USER_SERVICE=$(logname 2>/dev/null || echo "pi")
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
Description=Sistema de Cámara UART (Compatible Bookworm)
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
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/scripts/main_daemon.py /etc/camara-uart/camara.conf
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
    
    # Script de estado
    cat > "/usr/local/bin/camara-uart-status" << EOF
#!/bin/bash
echo "=== ESTADO DEL SISTEMA DE CÁMARA UART ==="
echo "Servicio:"
systemctl status $SERVICE_NAME --no-pager -l
echo
echo "Últimos logs:"
journalctl -u $SERVICE_NAME --no-pager -n 10
echo
echo "Puerto serie:"
ls -la /dev/tty* | grep -E "(ttyS|ttyAMA|ttyUSB|ttyACM)" || echo "No se encontraron puertos"
EOF
    chmod +x "/usr/local/bin/camara-uart-status"
    
    # Script de test
    cat > "/usr/local/bin/camara-uart-test" << EOF
#!/bin/bash
source "$INSTALL_DIR/venv/bin/activate"
cd "$INSTALL_DIR"
python3 scripts/cliente_basico.py "\${1:-/dev/ttyS0}" "\${2:-115200}"
EOF
    chmod +x "/usr/local/bin/camara-uart-test"
    
    print_success "Scripts de utilidad creados"
}

finalize_installation() {
    print_header "FINALIZANDO INSTALACIÓN"
    
    # Crear archivos de estado
    touch "$INSTALL_DIR/.installed"
    echo "$(date)" > "$INSTALL_DIR/.install_date"
    echo "bookworm-compatible-v1.0" > "$INSTALL_DIR/.version"
    
    # Habilitar servicio (pero no iniciarlo automáticamente)
    systemctl enable "$SERVICE_NAME"
    
    print_success "Instalación completada exitosamente!"
    echo
    echo -e "${CYAN}INSTALACIÓN COMPLETADA${NC}"
    echo -e "${CYAN}=====================${NC}"
    echo
    echo -e "${GREEN}Directorios:${NC}"
    echo -e "  • Instalación: $INSTALL_DIR"
    echo -e "  • Configuración: $CONFIG_DIR"
    echo -e "  • Datos: $DATA_DIR"
    echo -e "  • Logs: $LOG_DIR"
    echo
    echo -e "${GREEN}Comandos disponibles:${NC}"
    echo -e "  • Estado: ${YELLOW}camara-uart-status${NC}"
    echo -e "  • Test: ${YELLOW}camara-uart-test${NC}"
    echo -e "  • Iniciar: ${YELLOW}sudo systemctl start $SERVICE_NAME${NC}"
    echo -e "  • Logs: ${YELLOW}sudo journalctl -u $SERVICE_NAME -f${NC}"
    echo
    echo -e "${GREEN}Próximos pasos:${NC}"
    echo -e "  1. Verificar configuración: ${YELLOW}sudo nano $CONFIG_DIR/camara.conf${NC}"
    echo -e "  2. Iniciar servicio: ${YELLOW}sudo systemctl start $SERVICE_NAME${NC}"
    echo -e "  3. Probar sistema: ${YELLOW}camara-uart-test${NC}"
    echo
    echo -e "${YELLOW}Nota:${NC} Esta es una instalación básica compatible con Bookworm."
    echo -e "Para funcionalidades avanzadas, agregue los módulos adicionales."
}

main() {
    print_header "INSTALADOR COMPATIBLE CON RASPBERRY PI OS BOOKWORM"
    echo -e "${CYAN}Versión corregida para sistemas modernos${NC}"
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
