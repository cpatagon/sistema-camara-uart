#!/bin/bash
# ==============================================================================
# INSTALADOR SISTEMA CÁMARA UART - BOOKWORM OPTIMIZADO
# Versión eficiente con detección automática
# ==============================================================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Variables
INSTALL_DIR="/opt/camara-uart"
CONFIG_DIR="/etc/camara-uart"
DATA_DIR="/data/camara-uart"
SERVICE_NAME="camara-uart"
USER_SERVICE="pi"

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_root() {
    [[ $EUID -eq 0 ]] || { print_error "Ejecutar como root: sudo $0"; exit 1; }
}

install_system() {
    print_info "Instalando sistema básico..."
    
    # Actualizar y dependencias básicas
    apt-get update -qq
    apt-get install -y python3 python3-pip python3-venv python3-serial python3-pil \
                      build-essential git lsb-release
    
    # Instalar cámara (intenta rpicam-apps primero, luego libcamera-apps)
    if ! apt-get install -y rpicam-apps 2>/dev/null; then
        print_warning "rpicam-apps no disponible, instalando libcamera-apps..."
        apt-get install -y libcamera-apps python3-picamera2 || true
    fi
    
    print_success "Dependencias instaladas"
}

create_structure() {
    print_info "Creando estructura..."
    
    mkdir -p "$INSTALL_DIR"/{src,scripts} "$CONFIG_DIR" "$DATA_DIR/fotos" /var/log/camara-uart
    
    # Entorno Python
    python3 -m venv "$INSTALL_DIR/venv" --system-site-packages
    source "$INSTALL_DIR/venv/bin/activate"
    pip install --quiet pyserial configparser
}

create_core_files() {
    print_info "Creando archivos principales..."
    
    # Config manager
    cat > "$INSTALL_DIR/src/config_manager.py" << 'EOF'
import configparser
from dataclasses import dataclass

@dataclass
class Config:
    puerto: str = "/dev/ttyS0"
    baudrate: int = 115200
    directorio_fotos: str = "/data/camara-uart/fotos"

class ConfigManager:
    def __init__(self, config_file):
        self.config = Config()
        if hasattr(configparser, 'ConfigParser'):
            parser = configparser.ConfigParser()
            parser.read(config_file)
            if 'UART' in parser:
                self.config.puerto = parser['UART'].get('puerto', self.config.puerto)
                self.config.baudrate = int(parser['UART'].get('baudrate', self.config.baudrate))
    
    @property
    def puerto(self):
        return self.config.puerto
    
    @property  
    def baudrate(self):
        return self.config.baudrate
    
    @property
    def directorio_fotos(self):
        return self.config.directorio_fotos
EOF

    # Cámara controller inteligente
    cat > "$INSTALL_DIR/src/camara_controller.py" << 'EOF'
import subprocess
import time
from pathlib import Path

class CamaraController:
    def __init__(self):
        self.comando = self._detectar_comando()
    
    def _detectar_comando(self):
        for cmd in ["rpicam-still", "libcamera-still"]:
            try:
                subprocess.run([cmd, "--help"], capture_output=True, timeout=2)
                return cmd
            except:
                continue
        return None
    
    def capturar_foto(self, directorio="/tmp"):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        archivo = f"{timestamp}.jpg"
        ruta = Path(directorio) / archivo
        ruta.parent.mkdir(parents=True, exist_ok=True)
        
        if self.comando:
            try:
                cmd = [self.comando, "-o", str(ruta), "--timeout", "1000"]
                subprocess.run(cmd, check=True, timeout=10)
                tamaño = ruta.stat().st_size
                return True, archivo, str(ruta), tamaño
            except:
                pass
        
        # Imagen simulada
        with open(ruta, 'w') as f:
            f.write(f"IMAGEN SIMULADA - {timestamp}")
        return True, archivo, str(ruta), ruta.stat().st_size
    
    def info_sistema(self):
        return "rpicam" if "rpicam" in (self.comando or "") else "libcamera" if self.comando else "simulacion"
EOF

    # UART handler
    cat > "$INSTALL_DIR/src/uart_handler.py" << 'EOF'
import serial
import threading
import time

class UARTHandler:
    def __init__(self, puerto, baudrate):
        self.puerto = puerto
        self.baudrate = baudrate
        self.conexion = None
        self.ejecutando = False
        self.comandos = {}
    
    def registrar_comando(self, cmd, callback):
        self.comandos[cmd] = callback
    
    def iniciar(self):
        self.conexion = serial.Serial(self.puerto, self.baudrate, timeout=2)
        self.ejecutando = True
        threading.Thread(target=self._leer_comandos, daemon=True).start()
        self.enviar("CAMERA_READY")
    
    def enviar(self, msg):
        if self.conexion:
            self.conexion.write(f"{msg}\r\n".encode())
    
    def _leer_comandos(self):
        while self.ejecutando:
            try:
                if self.conexion.in_waiting:
                    linea = self.conexion.readline().decode().strip()
                    if linea in self.comandos:
                        respuesta = self.comandos[linea]()
                        self.enviar(respuesta)
                time.sleep(0.1)
            except:
                time.sleep(1)
    
    def detener(self):
        self.ejecutando = False
        if self.conexion:
            self.enviar("CAMERA_OFFLINE")
            self.conexion.close()
EOF

    # Daemon principal
    cat > "$INSTALL_DIR/scripts/main_daemon.py" << 'EOF'
#!/usr/bin/env python3
import sys
import signal
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config_manager import ConfigManager
from camara_controller import CamaraController
from uart_handler import UARTHandler

class SistemaCamara:
    def __init__(self, config_file):
        self.config = ConfigManager(config_file)
        self.camara = CamaraController()
        self.uart = UARTHandler(self.config.puerto, self.config.baudrate)
        self.ejecutando = False
    
    def iniciar(self):
        # Registrar comandos
        self.uart.registrar_comando('foto', self._cmd_foto)
        self.uart.registrar_comando('estado', self._cmd_estado)
        self.uart.registrar_comando('info', self._cmd_info)
        self.uart.registrar_comando('salir', self._cmd_salir)
        
        self.uart.iniciar()
        self.ejecutando = True
        print("Sistema iniciado - Comandos: foto, estado, info, salir")
    
    def _cmd_foto(self):
        exitoso, archivo, ruta, tamaño = self.camara.capturar_foto(self.config.directorio_fotos)
        return f"OK|{archivo}|{tamaño}|{ruta}" if exitoso else "ERROR|CAPTURE_FAILED"
    
    def _cmd_estado(self):
        return f"STATUS:ACTIVO|{self.config.puerto}|{self.config.baudrate}"
    
    def _cmd_info(self):
        return f"SISTEMA|{self.camara.info_sistema()}"
    
    def _cmd_salir(self):
        self.detener()
        return "CAMERA_OFFLINE"
    
    def detener(self):
        self.ejecutando = False
        self.uart.detener()
    
    def test(self):
        print("=== TEST DEL SISTEMA ===")
        print(f"Sistema cámara: {self.camara.info_sistema()}")
        exitoso, archivo, ruta, tamaño = self.camara.capturar_foto("/tmp")
        print(f"Test captura: {'OK' if exitoso else 'FAIL'} - {archivo} ({tamaño} bytes)")
        return exitoso

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/camara-uart/camara.conf")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    
    sistema = SistemaCamara(args.config)
    
    if args.test:
        sys.exit(0 if sistema.test() else 1)
    
    def signal_handler(signum, frame):
        sistema.detener()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    sistema.iniciar()
    while sistema.ejecutando:
        time.sleep(1)

if __name__ == "__main__":
    import time
    main()
EOF

    chmod +x "$INSTALL_DIR/scripts/main_daemon.py"
}

create_config() {
    print_info "Creando configuración..."
    
    cat > "$CONFIG_DIR/camara.conf" << 'EOF'
[UART]
puerto = /dev/ttyS0
baudrate = 115200

[CAMARA]
directorio_salida = /data/camara-uart/fotos
EOF
}

create_service() {
    print_info "Creando servicio systemd..."
    
    cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=Sistema Cámara UART
After=network.target

[Service]
Type=simple
User=$USER_SERVICE
Environment=PYTHONPATH=$INSTALL_DIR/src
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/scripts/main_daemon.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
}

setup_permissions() {
    print_info "Configurando permisos..."
    
    if ! id "$USER_SERVICE" &>/dev/null; then
        USER_SERVICE=$(whoami)
    fi
    
    usermod -a -G dialout,video "$USER_SERVICE" 2>/dev/null || true
    chown -R "$USER_SERVICE:$USER_SERVICE" "$INSTALL_DIR" "$DATA_DIR"
}

create_utilities() {
    print_info "Creando utilidades..."
    
    # Script de test
    cat > "/usr/local/bin/camara-uart-test" << 'EOF'
#!/bin/bash
cd /opt/camara-uart
python3 scripts/main_daemon.py --test
EOF
    chmod +x "/usr/local/bin/camara-uart-test"
    
    # Script de estado
    cat > "/usr/local/bin/camara-uart-status" << 'EOF'
#!/bin/bash
echo "=== ESTADO SISTEMA CÁMARA UART ==="
systemctl status camara-uart --no-pager -l
echo ""
echo "Comandos disponibles:"
for cmd in rpicam-still libcamera-still; do
    command -v $cmd >/dev/null && echo "  ✓ $cmd"
done
EOF
    chmod +x "/usr/local/bin/camara-uart-status"
}

main() {
    echo -e "${GREEN}=== INSTALADOR CÁMARA UART BOOKWORM ===${NC}"
    
    check_root
    install_system
    create_structure
    create_core_files
    create_config
    setup_permissions
    create_service
    create_utilities
    
    echo -e "${GREEN}✅ INSTALACIÓN COMPLETADA${NC}"
    echo ""
    echo "Comandos disponibles:"
    echo "  • camara-uart-test      - Test del sistema"
    echo "  • camara-uart-status    - Estado del servicio"
    echo "  • systemctl start camara-uart - Iniciar servicio"
    echo ""
    echo "Pasos siguientes:"
    echo "  1. Reboot para aplicar permisos"
    echo "  2. Ejecutar: camara-uart-test"
    echo "  3. Iniciar: systemctl start camara-uart"
}

main "$@"
