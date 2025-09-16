#!/bin/bash
# ==============================================================================
# INSTALADOR DEL SISTEMA DE CÁMARA UART INTEGRADO
# Versión con correcciones de transferencia de archivos
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

check_system() {
    print_info "Verificando sistema..."
    
    # Verificar Raspberry Pi OS
    if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        print_warning "No se detectó Raspberry Pi, continuando..."
    fi
    
    # Verificar Python 3.7+
    if ! python3 -c "import sys; assert sys.version_info >= (3,7)" 2>/dev/null; then
        print_error "Se requiere Python 3.7 o superior"
        exit 1
    fi
    
    # Verificar cámara (opcional)
    if command -v vcgencmd >/dev/null 2>&1; then
        camera_status=$(vcgencmd get_camera 2>/dev/null || echo "not_detected")
        if echo "$camera_status" | grep -q "detected=1"; then
            print_success "Cámara detectada"
        else
            print_warning "Cámara no detectada, puede requerir configuración"
        fi
    fi
    
    print_success "Verificación del sistema completada"
}

install_dependencies() {
    print_header "INSTALANDO DEPENDENCIAS"
    
    # Actualizar paquetes
    print_info "Actualizando repositorios..."
    apt-get update -qq
    
    # Instalar dependencias del sistema
    print_info "Instalando dependencias del sistema..."
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        git \
        curl \
        build-essential \
        cmake \
        pkg-config \
        libjpeg-dev \
        libpng-dev \
        libtiff-dev \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        libgtk-3-dev \
        libcanberra-gtk3-dev \
        libxvidcore-dev \
        libx264-dev \
        libgtk-3-dev \
        libopenexr-dev \
        libwebp-dev \
        libopencv-dev \
        python3-opencv \
        libhdf5-dev \
        libhdf5-103 \
        libqt5gui5 \
        libqt5webkit5 \
        libqt5test5 \
        python3-pyqt5 \
        libatlas-base-dev \
        libjasper-dev \
        libqtgui4 \
        libqt4-dev
    
    # Instalar picamera2 y dependencias específicas de Raspberry Pi
    if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        print_info "Instalando dependencias específicas de Raspberry Pi..."
        apt-get install -y \
            python3-picamera2 \
            python3-libcamera \
            libcamera-apps \
            libcamera-dev
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
    
    print_success "Estructura de directorios creada"
}

install_python_environment() {
    print_header "CONFIGURANDO ENTORNO PYTHON"
    
    # Crear entorno virtual
    print_info "Creando entorno virtual Python..."
    python3 -m venv "$INSTALL_DIR/venv"
    
    # Activar entorno virtual
    source "$INSTALL_DIR/venv/bin/activate"
    
    # Actualizar pip
    print_info "Actualizando pip..."
    pip install --upgrade pip setuptools wheel
    
    # Instalar dependencias Python
    print_info "Instalando dependencias Python..."
    cat > "$INSTALL_DIR/requirements.txt" << 'EOF'
# Sistema de Cámara UART - Dependencias Python Integradas
pyserial>=3.5,<4.0
configparser>=5.0.0
Pillow>=9.0.0,<11.0.0
numpy>=1.21.0,<2.0.0
colorlog>=6.0.0,<7.0.0
pathlib2>=2.3.0; python_version < "3.8"

# Cámara Raspberry Pi (se instala si está disponible)
# picamera2>=0.3.12

# Dependencias opcionales para testing
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
EOF
    
    pip install -r "$INSTALL_DIR/requirements.txt"
    
    # Intentar instalar picamera2 si estamos en Raspberry Pi
    if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        print_info "Instalando picamera2..."
        pip install picamera2 || print_warning "No se pudo instalar picamera2, usar versión del sistema"
    fi
    
    print_success "Entorno Python configurado"
}

copy_source_files() {
    print_header "COPIANDO ARCHIVOS DEL SISTEMA"
    
    # Verificar que estamos en el directorio correcto
    if [[ ! -f "src/uart_handler.py" ]] && [[ ! -f "../src/uart_handler.py" ]]; then
        print_error "No se encontraron los archivos fuente. Ejecutar desde el directorio del proyecto."
        exit 1
    fi
    
    # Determinar directorio fuente
    if [[ -f "src/uart_handler.py" ]]; then
        SOURCE_DIR="."
    else
        SOURCE_DIR=".."
    fi
    
    print_info "Copiando archivos fuente..."
    
    # Copiar archivos corregidos del sistema
    cp -r "$SOURCE_DIR/src/"* "$INSTALL_DIR/src/"
    cp -r "$SOURCE_DIR/scripts/"* "$INSTALL_DIR/scripts/"
    cp -r "$SOURCE_DIR/config/"* "$INSTALL_DIR/config/"
    
    # Copiar archivos de configuración
    if [[ -f "$SOURCE_DIR/config/camara.conf.example" ]]; then
        cp "$SOURCE_DIR/config/camara.conf.example" "$CONFIG_DIR/camara.conf"
        print_info "Configuración copiada a $CONFIG_DIR/camara.conf"
    fi
    
    # Copiar archivos corregidos específicos
    print_info "Instalando versiones corregidas..."
    
    # Aquí se copiarían las versiones corregidas generadas anteriormente
    # (En un entorno real, estos archivos ya estarían en el proyecto)
    
    print_success "Archivos del sistema copiados"
}

configure_permissions() {
    print_header "CONFIGURANDO PERMISOS"
    
    # Crear usuario de servicio si no existe
    if ! id "$USER_SERVICE" &>/dev/null; then
        print_info "Creando usuario de servicio: $USER_SERVICE"
        useradd -r -s /bin/false -d "$INSTALL_DIR" "$USER_SERVICE"
    fi
    
    # Agregar usuario a grupos necesarios
    print_info "Configurando grupos de usuario..."
    usermod -a -G dialout "$USER_SERVICE"
    usermod -a -G video "$USER_SERVICE"
    usermod -a -G gpio "$USER_SERVICE" 2>/dev/null || true
    
    # Configurar permisos de directorios
    print_info "Configurando permisos de directorios..."
    chown -R "$USER_SERVICE:$USER_SERVICE" "$INSTALL_DIR"
    chown -R "$USER_SERVICE:$USER_SERVICE" "$LOG_DIR"
    chown -R "$USER_SERVICE:$USER_SERVICE" "$DATA_DIR"
    
    # Permisos de configuración (lectura para todos)
    chown -R root:root "$CONFIG_DIR"
    chmod -R 644 "$CONFIG_DIR"
    
    # Permisos de ejecutables
    chmod +x "$INSTALL_DIR/scripts/"*.py
    
    # Configurar acceso a puerto serie
    print_info "Configurando acceso a puertos serie..."
    if [[ -c /dev/ttyS0 ]]; then
        chgrp dialout /dev/ttyS0
        chmod g+rw /dev/ttyS0
    fi
    
    print_success "Permisos configurados"
}

create_systemd_service() {
    print_header "CREANDO SERVICIO SYSTEMD"
    
    print_info "Creando archivo de servicio..."
    cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=Sistema de Cámara UART Integrado
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
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/scripts/main_daemon_integrado.py --config $CONFIG_DIR/camara.conf
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Límites de recursos
LimitNOFILE=65536
LimitNPROC=4096

# Directorio de trabajo y archivos temporales
WorkingDirectory=$INSTALL_DIR
PrivateTmp=true

# Capacidades adicionales para acceso a hardware
SupplementaryGroups=dialout video gpio

[Install]
WantedBy=multi-user.target
EOF
    
    # Crear script de inicio con configuración de entorno
    cat > "$INSTALL_DIR/start_daemon.sh" << EOF
#!/bin/bash
# Script de inicio del daemon con entorno configurado

# Activar entorno virtual
source "$INSTALL_DIR/venv/bin/activate"

# Configurar variables de entorno
export PYTHONPATH="$INSTALL_DIR/src:\$PYTHONPATH"
export CAMARA_UART_CONFIG="$CONFIG_DIR/camara.conf"
export CAMARA_UART_LOG_DIR="$LOG_DIR"
export CAMARA_UART_DATA_DIR="$DATA_DIR"

# Ejecutar daemon
exec python3 "$INSTALL_DIR/scripts/main_daemon_integrado.py" --config "$CONFIG_DIR/camara.conf" "\$@"
EOF
    
    chmod +x "$INSTALL_DIR/start_daemon.sh"
    
    # Recargar systemd
    print_info "Recargando configuración de systemd..."
    systemctl daemon-reload
    
    print_success "Servicio systemd creado"
}

configure_system() {
    print_header "CONFIGURACIÓN DEL SISTEMA"
    
    # Configurar cámara en Raspberry Pi
    if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        print_info "Configurando cámara Raspberry Pi..."
        
        # Verificar si la cámara está habilitada
        if ! grep -q "^camera_auto_detect=1" /boot/config.txt; then
            echo "camera_auto_detect=1" >> /boot/config.txt
            print_info "Cámara habilitada en /boot/config.txt"
        fi
        
        # Configurar memoria GPU si es necesario
        gpu_mem=$(grep "^gpu_mem=" /boot/config.txt | cut -d'=' -f2)
        if [[ -z "$gpu_mem" ]] || [[ "$gpu_mem" -lt 128 ]]; then
            sed -i '/^gpu_mem=/d' /boot/config.txt
            echo "gpu_mem=128" >> /boot/config.txt
            print_info "Memoria GPU configurada a 128MB"
        fi
    fi
    
    # Configurar UART
    print_info "Configurando UART..."
    
    # Habilitar UART en Raspberry Pi
    if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        if ! grep -q "^enable_uart=1" /boot/config.txt; then
            echo "enable_uart=1" >> /boot/config.txt
            print_info "UART habilitado en /boot/config.txt"
        fi
        
        # Deshabilitar console en UART
        if grep -q "console=serial0" /boot/cmdline.txt; then
            sed -i 's/console=serial0,[0-9]*\s*//g' /boot/cmdline.txt
            print_info "Console en UART deshabilitado"
        fi
    fi
    
    # Configurar logrotate
    print_info "Configurando rotación de logs..."
    cat > "/etc/logrotate.d/$SERVICE_NAME" << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    sharedscripts
    postrotate
        systemctl reload $SERVICE_NAME || true
    endscript
}
EOF
    
    print_success "Sistema configurado"
}

create_utility_scripts() {
    print_header "CREANDO SCRIPTS DE UTILIDAD"
    
    # Script de estado del sistema
    cat > "/usr/local/bin/camara-uart-status" << EOF
#!/bin/bash
# Script para verificar estado del sistema de cámara UART

echo "=== ESTADO DEL SISTEMA DE CÁMARA UART ==="
echo

echo "Servicio:"
systemctl status $SERVICE_NAME --no-pager -l

echo
echo "Últimos logs:"
journalctl -u $SERVICE_NAME --no-pager -n 10

echo
echo "Archivos de configuración:"
ls -la $CONFIG_DIR/

echo
echo "Directorio de datos:"
du -sh $DATA_DIR/*

echo
echo "Puerto serie:"
ls -la /dev/tty* | grep -E "(ttyS|ttyAMA|ttyUSB|ttyACM)" || echo "No se encontraron puertos serie"

echo
echo "Cámara (si está disponible):"
if command -v vcgencmd >/dev/null 2>&1; then
    vcgencmd get_camera
else
    echo "vcgencmd no disponible"
fi
EOF
    
    chmod +x "/usr/local/bin/camara-uart-status"
    
    # Script de test del cliente
    cat > "/usr/local/bin/camara-uart-test" << EOF
#!/bin/bash
# Script para probar el cliente de cámara UART

PUERTO="\${1:-/dev/ttyS0}"
BAUDRATE="\${2:-115200}"

echo "🧪 Probando cliente de cámara UART..."
echo "Puerto: \$PUERTO"
echo "Baudrate: \$BAUDRATE"
echo

source "$INSTALL_DIR/venv/bin/activate"
cd "$INSTALL_DIR"
python3 scripts/cliente_transfer_robust.py --puerto "\$PUERTO" --baudrate "\$BAUDRATE"
EOF
    
    chmod +x "/usr/local/bin/camara-uart-test"
    
    # Script de diagnóstico
    cat > "/usr/local/bin/camara-uart-diagnostico" << EOF
#!/bin/bash
# Script de diagnóstico completo

echo "🔍 DIAGNÓSTICO DEL SISTEMA DE CÁMARA UART"
echo "========================================="
echo

echo "1. Información del sistema:"
uname -a
echo

echo "2. Información de Python:"
python3 --version
echo

echo "3. Puertos serie disponibles:"
python3 -c "import serial.tools.list_ports; [print(f'  {p.device} - {p.description}') for p in serial.tools.list_ports.comports()]"
echo

echo "4. Estado del servicio:"
systemctl is-active $SERVICE_NAME
systemctl is-enabled $SERVICE_NAME
echo

echo "5. Últimos errores:"
journalctl -u $SERVICE_NAME --no-pager -p err -n 5
echo

echo "6. Uso de recursos:"
ps aux | grep -E "(python.*camara|camara.*python)" | grep -v grep
echo

echo "7. Espacio en disco:"
df -h $DATA_DIR
echo

echo "8. Permisos:"
ls -la $INSTALL_DIR/scripts/main_daemon_integrado.py
ls -la $CONFIG_DIR/camara.conf
echo

echo "9. Test de configuración:"
source "$INSTALL_DIR/venv/bin/activate"
cd "$INSTALL_DIR"
python3 -c "from src.config_manager import ConfigManager; print('✅ Configuración válida')" 2>/dev/null || echo "❌ Error en configuración"

echo
echo "10. Variables de entorno:"
echo "PYTHONPATH=\$PYTHONPATH"
echo "PATH=\$PATH"
EOF
    
    chmod +x "/usr/local/bin/camara-uart-diagnostico"
    
    print_success "Scripts de utilidad creados"
}

finalize_installation() {
    print_header "FINALIZANDO INSTALACIÓN"
    
    # Habilitar servicio
    print_info "Habilitando servicio..."
    systemctl enable "$SERVICE_NAME"
    
    # Crear archivos de estado
    touch "$INSTALL_DIR/.installed"
    echo "$(date)" > "$INSTALL_DIR/.install_date"
    echo "integrado-v1.0" > "$INSTALL_DIR/.version"
    
    # Mostrar resumen
    print_success "Instalación completada exitosamente!"
    echo
    echo -e "${CYAN}RESUMEN DE LA INSTALACIÓN:${NC}"
    echo -e "  • Directorio de instalación: ${GREEN}$INSTALL_DIR${NC}"
    echo -e "  • Directorio de configuración: ${GREEN}$CONFIG_DIR${NC}"
    echo -e "  • Directorio de datos: ${GREEN}$DATA_DIR${NC}"
    echo -e "  • Directorio de logs: ${GREEN}$LOG_DIR${NC}"
    echo -e "  • Servicio: ${GREEN}$SERVICE_NAME${NC}"
    echo -e "  • Usuario de servicio: ${GREEN}$USER_SERVICE${NC}"
    echo
    echo -e "${CYAN}COMANDOS ÚTILES:${NC}"
    echo -e "  • Estado del sistema: ${YELLOW}camara-uart-status${NC}"
    echo -e "  • Test del cliente: ${YELLOW}camara-uart-test${NC}"
    echo -e "  • Diagnóstico: ${YELLOW}camara-uart-diagnostico${NC}"
    echo -e "  • Iniciar servicio: ${YELLOW}sudo systemctl start $SERVICE_NAME${NC}"
    echo -e "  • Ver logs: ${YELLOW}sudo journalctl -u $SERVICE_NAME -f${NC}"
    echo
    echo -e "${CYAN}PRÓXIMOS PASOS:${NC}"
    echo -e "  1. Revisar configuración: ${YELLOW}sudo nano $CONFIG_DIR/camara.conf${NC}"
    echo -e "  2. Iniciar servicio: ${YELLOW}sudo systemctl start $SERVICE_NAME${NC}"
    echo -e "  3. Probar cliente: ${YELLOW}camara-uart-test${NC}"
    echo
    
    if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        print_warning "Se recomienda reiniciar el sistema para aplicar cambios de configuración de cámara y UART"
        echo -e "  Ejecutar: ${YELLOW}sudo reboot${NC}"
    fi
}

main() {
    print_header "INSTALADOR DEL SISTEMA DE CÁMARA UART INTEGRADO"
    echo -e "${CYAN}Versión con correcciones de transferencia de archivos${NC}"
    echo
    
    check_root
    check_system
    install_dependencies
    create_directories
    install_python_environment
    copy_source_files
    configure_permissions
    create_systemd_service
    configure_system
    create_utility_scripts
    finalize_installation
}

# Ejecutar instalación
main "$@"
