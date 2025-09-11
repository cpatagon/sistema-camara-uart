#!/bin/bash
# ============================================================================
# SCRIPT DE INSTALACIÓN - SISTEMA DE CÁMARA UART
# ============================================================================
#
# Este script automatiza la instalación completa del sistema de cámara UART
# para Raspberry Pi, incluyendo dependencias, configuración y servicios.
#
# Autor: Sistema de Cámara UART v1.0
# Fecha: 2025-09-10
# ============================================================================

set -e  # Salir en caso de error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Variables globales
INSTALL_DIR="/opt/camara-uart"
SERVICE_NAME="camara-uart"
USER_GROUP="dialout"
PYTHON_MIN_VERSION="3.7"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Funciones auxiliares
print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║         🚀 INSTALADOR SISTEMA CÁMARA UART           ║"
    echo "║                                                      ║"
    echo "║    Instalación automática para Raspberry Pi         ║"
    echo "║        Control de cámara por puerto serie           ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "${BLUE}[PASO]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_question() {
    echo -e "${MAGENTA}[?]${NC} $1"
}

# Verificar si se ejecuta como root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "No ejecutar este script como root directamente."
        print_info "El script pedirá permisos sudo cuando sea necesario."
        exit 1
    fi
}

# Verificar sistema operativo
check_os() {
    print_step "Verificando sistema operativo..."
    
    if [[ ! -f /etc/os-release ]]; then
        print_error "No se pudo detectar el sistema operativo"
        exit 1
    fi
    
    source /etc/os-release
    
    if [[ "$ID" != "raspbian" ]] && [[ "$ID_LIKE" != *"debian"* ]] && [[ "$ID" != "debian" ]]; then
        print_warning "Sistema no oficialmente soportado: $PRETTY_NAME"
        print_info "El script está optimizado para Raspberry Pi OS/Debian"
        
        read -p "¿Continuar de todos modos? (s/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Ss]$ ]]; then
            print_info "Instalación cancelada"
            exit 0
        fi
    else
        print_success "Sistema soportado: $PRETTY_NAME"
    fi
    
    # Verificar arquitectura
    ARCH=$(uname -m)
    print_info "Arquitectura: $ARCH"
    
    # Detectar modelo de Raspberry Pi
    if [[ -f /proc/cpuinfo ]]; then
        PI_MODEL=$(grep "Model" /proc/cpuinfo | cut -d: -f2 | xargs)
        if [[ -n "$PI_MODEL" ]]; then
            print_info "Modelo detectado: $PI_MODEL"
        fi
    fi
}

# Verificar versión de Python
check_python() {
    print_step "Verificando Python..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 no está instalado"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    print_info "Versión de Python: $PYTHON_VERSION"
    
    # Verificar versión mínima
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,7) else 1)"; then
        print_error "Se requiere Python $PYTHON_MIN_VERSION o superior"
        print_info "Versión actual: $PYTHON_VERSION"
        exit 1
    fi
    
    print_success "Python verificado correctamente"
}

# Actualizar sistema
update_system() {
    print_step "Actualizando sistema..."
    
    print_info "Actualizando lista de paquetes..."
    sudo apt-get update -q
    
    print_question "¿Actualizar paquetes instalados? (recomendado) (S/n):"
    read -p "" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        print_info "Actualizando paquetes..."
        sudo apt-get upgrade -y
    fi
    
    print_success "Sistema actualizado"
}

# Instalar dependencias del sistema
install_system_dependencies() {
    print_step "Instalando dependencias del sistema..."
    
    PACKAGES=(
        "python3-pip"
        "python3-venv"
        "python3-dev"
        "git"
        "curl"
        "build-essential"
        "cmake"
        "pkg-config"
        "libjpeg-dev"
        "libpng-dev"
        "libtiff-dev"
        "libavcodec-dev"
        "libavformat-dev"
        "libswscale-dev"
        "libv4l-dev"
        "libxvidcore-dev"
        "libx264-dev"
        "libgtk-3-dev"
        "libcanberra-gtk3-dev"
        "libatlas-base-dev"
        "gfortran"
        "python3-numpy"
    )
    
    print_info "Instalando paquetes: ${PACKAGES[*]}"
    sudo apt-get install -y "${PACKAGES[@]}"
    
    print_success "Dependencias del sistema instaladas"
}

# Habilitar cámara y UART
enable_camera_uart() {
    print_step "Configurando cámara y UART..."
    
    # Verificar si raspi-config está disponible
    if command -v raspi-config &> /dev/null; then
        print_info "Habilitando cámara..."
        sudo raspi-config nonint do_camera 0
        
        print_info "Habilitando UART..."
        sudo raspi-config nonint do_serial 1  # Deshabilitar serial login
        sudo raspi-config nonint do_serial_hw 0  # Habilitar hardware serial
        
        print_success "Cámara y UART configurados"
    else
        print_warning "raspi-config no disponible, configuración manual requerida"
        
        # Configuración manual
        CONFIG_FILE="/boot/config.txt"
        if [[ -f "$CONFIG_FILE" ]]; then
            print_info "Configurando $CONFIG_FILE..."
            
            # Backup
            sudo cp "$CONFIG_FILE" "${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
            
            # Habilitar cámara
            if ! grep -q "^camera_auto_detect=1" "$CONFIG_FILE"; then
                echo "camera_auto_detect=1" | sudo tee -a "$CONFIG_FILE"
            fi
            
            # Configurar UART
            if ! grep -q "^enable_uart=1" "$CONFIG_FILE"; then
                echo "enable_uart=1" | sudo tee -a "$CONFIG_FILE"
            fi
            
            # Configurar memoria GPU para Pi Zero
            if [[ "$PI_MODEL" == *"Zero"* ]]; then
                if ! grep -q "^gpu_mem=" "$CONFIG_FILE"; then
                    echo "gpu_mem=128" | sudo tee -a "$CONFIG_FILE"
                    print_info "Memoria GPU configurada para Pi Zero"
                fi
            fi
        fi
        
        print_info "Configuración manual aplicada"
    fi
}

# Configurar permisos de usuario
setup_user_permissions() {
    print_step "Configurando permisos de usuario..."
    
    # Agregar usuario al grupo dialout
    if groups "$USER" | grep -q "\b$USER_GROUP\b"; then
        print_info "Usuario $USER ya está en el grupo $USER_GROUP"
    else
        print_info "Agregando usuario $USER al grupo $USER_GROUP..."
        sudo usermod -a -G "$USER_GROUP" "$USER"
        print_warning "Debe cerrar sesión y volver a entrar para que los cambios surtan efecto"
    fi
    
    # Crear grupo adicional si es necesario
    if ! getent group camara-uart &> /dev/null; then
        print_info "Creando grupo camara-uart..."
        sudo groupadd camara-uart
        sudo usermod -a -G camara-uart "$USER"
    fi
    
    print_success "Permisos de usuario configurados"
}

# Instalar dependencias Python
install_python_dependencies() {
    print_step "Instalando dependencias Python..."
    
    # Crear entorno virtual
    VENV_DIR="$PROJECT_ROOT/venv"
    if [[ ! -d "$VENV_DIR" ]]; then
        print_info "Creando entorno virtual..."
        python3 -m venv "$VENV_DIR"
    fi
    
    # Activar entorno virtual
    source "$VENV_DIR/bin/activate"
    
    # Actualizar pip
    print_info "Actualizando pip..."
    pip install --upgrade pip
    
    # Instalar dependencias
    if [[ -f "$PROJECT_ROOT/requirements.txt" ]]; then
        print_info "Instalando desde requirements.txt..."
        pip install -r "$PROJECT_ROOT/requirements.txt"
    else
        print_info "Instalando dependencias básicas..."
        pip install pyserial configparser pathlib
        
        # Intentar instalar picamera2
        print_info "Instalando picamera2..."
        if pip install picamera2; then
            print_success "picamera2 instalado correctamente"
        else
            print_warning "No se pudo instalar picamera2, puede instalarse manualmente después"
        fi
    fi
    
    # Crear requirements.txt si no existe
    if [[ ! -f "$PROJECT_ROOT/requirements.txt" ]]; then
        print_info "Generando requirements.txt..."
        pip freeze > "$PROJECT_ROOT/requirements.txt"
    fi
    
    print_success "Dependencias Python instaladas"
}

# Configurar estructura de directorios
setup_directories() {
    print_step "Configurando estructura de directorios..."
    
    # Directorios necesarios
    DIRECTORIES=(
        "$PROJECT_ROOT/config"
        "$PROJECT_ROOT/data/fotos"
        "$PROJECT_ROOT/data/temp"
        "$PROJECT_ROOT/logs"
        "/var/log/camara-uart"
        "/etc/camara-uart"
    )
    
    for dir in "${DIRECTORIES[@]}"; do
        if [[ ! -d "$dir" ]]; then
            print_info "Creando directorio: $dir"
            if [[ "$dir" == /var/* ]] || [[ "$dir" == /etc/* ]]; then
                sudo mkdir -p "$dir"
                sudo chown "$USER:$USER" "$dir"
            else
                mkdir -p "$dir"
            fi
        fi
    done
    
    # Configurar permisos
    print_info "Configurando permisos de directorios..."
    chmod 755 "$PROJECT_ROOT/data"
    chmod 755 "$PROJECT_ROOT/data/fotos"
    chmod 755 "$PROJECT_ROOT/data/temp"
    chmod 755 "$PROJECT_ROOT/logs"
    
    if [[ -d "/var/log/camara-uart" ]]; then
        sudo chmod 755 "/var/log/camara-uart"
    fi
    
    print_success "Estructura de directorios configurada"
}

# Configurar archivos de configuración
setup_configuration() {
    print_step "Configurando archivos de configuración..."
    
    # Copiar configuración ejemplo si no existe
    CONFIG_EXAMPLE="$PROJECT_ROOT/config/camara.conf.example"
    CONFIG_MAIN="$PROJECT_ROOT/config/camara.conf"
    
    if [[ ! -f "$CONFIG_MAIN" ]]; then
        if [[ -f "$CONFIG_EXAMPLE" ]]; then
            print_info "Copiando configuración ejemplo..."
            cp "$CONFIG_EXAMPLE" "$CONFIG_MAIN"
        else
            print_info "Creando configuración básica..."
            cat > "$CONFIG_MAIN" << 'EOF'
[UART]
puerto = /dev/ttyS0
baudrate = 115200
timeout = 1.0

[CAMARA]
resolucion_ancho = 1920
resolucion_alto = 1080
calidad = 95
formato = jpg

[SISTEMA]
directorio_fotos = /data/fotos
directorio_temp = /data/temp
max_archivos = 1000
auto_limpiar = true

[TRANSFERENCIA]
chunk_size = 256
verificar_checksum = true

[LOGGING]
nivel = INFO
archivo = /var/log/camara-uart/camara-uart.log
EOF
        fi
        print_success "Configuración creada: $CONFIG_MAIN"
    else
        print_info "Configuración ya existe: $CONFIG_MAIN"
    fi
    
    # Configurar logging
    setup_logging_config
}

# Configurar logging
setup_logging_config() {
    print_info "Configurando sistema de logging..."
    
    # Crear configuración de logrotate
    LOGROTATE_CONFIG="/etc/logrotate.d/camara-uart"
    
    sudo tee "$LOGROTATE_CONFIG" > /dev/null << 'EOF'
/var/log/camara-uart/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    copytruncate
    create 644 root root
}
EOF
    
    print_success "Configuración de logging creada"
}

# Instalar servicio systemd
install_systemd_service() {
    print_step "Instalando servicio systemd..."
    
    SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
    
    print_info "Creando archivo de servicio: $SERVICE_FILE"
    
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Sistema de Cámara UART
Documentation=file://$PROJECT_ROOT/docs/README.md
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=camara-uart
WorkingDirectory=$PROJECT_ROOT
Environment=PATH=$PROJECT_ROOT/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStartPre=/bin/sleep 10
ExecStart=$PROJECT_ROOT/venv/bin/python $PROJECT_ROOT/scripts/main_daemon.py -c $PROJECT_ROOT/config/camara.conf
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=camara-uart

# Límites de recursos
LimitNOFILE=65536
LimitNPROC=4096

# Seguridad
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=$PROJECT_ROOT/data $PROJECT_ROOT/logs /var/log/camara-uart

[Install]
WantedBy=multi-user.target
EOF

    # Recargar systemd
    print_info "Recargando configuración de systemd..."
    sudo systemctl daemon-reload
    
    # Habilitar servicio
    print_question "¿Habilitar inicio automático del servicio? (S/n):"
    read -p "" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        sudo systemctl enable "$SERVICE_NAME"
        print_success "Servicio habilitado para inicio automático"
    fi
    
    print_success "Servicio systemd instalado"
}

# Crear scripts auxiliares
create_helper_scripts() {
    print_step "Creando scripts auxiliares..."
    
    # Script de inicio rápido
    QUICK_START="$PROJECT_ROOT/inicio_rapido.sh"
    cat > "$QUICK_START" << EOF
#!/bin/bash
# Script de inicio rápido para Sistema de Cámara UART

echo "🚀 Iniciando Sistema de Cámara UART..."

# Activar entorno virtual
source "$PROJECT_ROOT/venv/bin/activate"

# Verificar configuración
if [ ! -f "$PROJECT_ROOT/config/camara.conf" ]; then
    echo "❌ Archivo de configuración no encontrado"
    echo "💡 Ejecutar: cp config/camara.conf.example config/camara.conf"
    exit 1
fi

# Iniciar sistema
python3 "$PROJECT_ROOT/scripts/main_daemon.py" "\$@"
EOF
    chmod +x "$QUICK_START"
    
    # Script de prueba del cliente
    CLIENT_TEST="$PROJECT_ROOT/test_cliente.sh"
    cat > "$CLIENT_TEST" << EOF
#!/bin/bash
# Script de prueba del cliente UART

echo "🧪 Iniciando cliente de pruebas..."

# Activar entorno virtual
source "$PROJECT_ROOT/venv/bin/activate"

# Ejecutar cliente
python3 "$PROJECT_ROOT/scripts/cliente_foto.py" "\$@"
EOF
    chmod +x "$CLIENT_TEST"
    
    # Script de estado del servicio
    SERVICE_STATUS="$PROJECT_ROOT/estado_servicio.sh"
    cat > "$SERVICE_STATUS" << EOF
#!/bin/bash
# Script para verificar estado del servicio

echo "📊 Estado del servicio $SERVICE_NAME:"
echo "============================================"

# Estado del servicio
sudo systemctl status "$SERVICE_NAME" --no-pager

echo ""
echo "📈 Últimas líneas del log:"
echo "============================================"
sudo journalctl -u "$SERVICE_NAME" -n 10 --no-pager

echo ""
echo "🔧 Comandos útiles:"
echo "  sudo systemctl start $SERVICE_NAME      # Iniciar servicio"
echo "  sudo systemctl stop $SERVICE_NAME       # Detener servicio"
echo "  sudo systemctl restart $SERVICE_NAME    # Reiniciar servicio"
echo "  sudo journalctl -u $SERVICE_NAME -f     # Ver logs en tiempo real"
EOF
    chmod +x "$SERVICE_STATUS"
    
    print_success "Scripts auxiliares creados"
}

# Verificar instalación
verify_installation() {
    print_step "Verificando instalación..."
    
    # Verificar estructura de archivos
    REQUIRED_FILES=(
        "$PROJECT_ROOT/src/config_manager.py"
        "$PROJECT_ROOT/src/camara_controller.py"
        "$PROJECT_ROOT/src/uart_handler.py"
        "$PROJECT_ROOT/src/file_transfer.py"
        "$PROJECT_ROOT/scripts/main_daemon.py"
        "$PROJECT_ROOT/scripts/cliente_foto.py"
        "$PROJECT_ROOT/config/camara.conf"
    )
    
    for file in "${REQUIRED_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            print_success "Archivo encontrado: $(basename "$file")"
        else
            print_error "Archivo faltante: $file"
            return 1
        fi
    done
    
    # Verificar entorno virtual
    if [[ -d "$PROJECT_ROOT/venv" ]]; then
        source "$PROJECT_ROOT/venv/bin/activate"
        
        # Verificar importación de módulos
        if python3 -c "import serial, configparser" 2>/dev/null; then
            print_success "Dependencias Python verificadas"
        else
            print_error "Error en dependencias Python"
            return 1
        fi
        
        # Verificar módulos del proyecto
        if PYTHONPATH="$PROJECT_ROOT/src" python3 -c "import config_manager, camara_controller" 2>/dev/null; then
            print_success "Módulos del proyecto verificados"
        else
            print_error "Error en módulos del proyecto"
            return 1
        fi
    else
        print_error "Entorno virtual no encontrado"
        return 1
    fi
    
    # Verificar servicio systemd
    if systemctl list-unit-files | grep -q "$SERVICE_NAME.service"; then
        print_success "Servicio systemd instalado"
    else
        print_warning "Servicio systemd no encontrado"
    fi
    
    # Verificar permisos UART
    if groups "$USER" | grep -q dialout; then
        print_success "Permisos UART configurados"
    else
        print_warning "Usuario no está en grupo dialout"
    fi
    
    print_success "Verificación completada"
    return 0
}

# Test del sistema
test_system() {
    print_step "Realizando test del sistema..."
    
    # Activar entorno virtual
    source "$PROJECT_ROOT/venv/bin/activate"
    
    print_info "Ejecutando test de inicialización..."
    if PYTHONPATH="$PROJECT_ROOT/src" python3 "$PROJECT_ROOT/scripts/main_daemon.py" --test; then
        print_success "Test de inicialización pasado"
    else
        print_error "Test de inicialización falló"
        return 1
    fi
    
    return 0
}

# Mostrar información post-instalación
show_post_install_info() {
    print_step "Información post-instalación"
    
    echo
    print_success "🎉 ¡Instalación completada exitosamente!"
    echo
    
    print_info "📁 Directorio del proyecto: $PROJECT_ROOT"
    print_info "⚙️  Archivo de configuración: $PROJECT_ROOT/config/camara.conf"
    print_info "📋 Logs del sistema: /var/log/camara-uart/"
    print_info "🔧 Servicio systemd: $SERVICE_NAME"
    
    echo
    print_info "🚀 Comandos para empezar:"
    echo "  # Iniciar manualmente:"
    echo "  ./inicio_rapido.sh"
    echo
    echo "  # Usar como servicio:"
    echo "  sudo systemctl start $SERVICE_NAME"
    echo "  sudo systemctl status $SERVICE_NAME"
    echo
    echo "  # Probar cliente:"
    echo "  ./test_cliente.sh"
    echo
    echo "  # Ver estado del servicio:"
    echo "  ./estado_servicio.sh"
    
    echo
    print_info "📖 Archivos importantes:"
    echo "  • config/camara.conf          - Configuración principal"
    echo "  • scripts/main_daemon.py      - Daemon principal"
    echo "  • scripts/cliente_foto.py     - Cliente de pruebas"
    echo "  • docs/README.md              - Documentación completa"
    
    echo
    print_warning "⚠️  IMPORTANTE:"
    echo "  • Debe reiniciar el sistema para aplicar cambios de UART/cámara"
    echo "  • Cerrar sesión y volver a entrar para permisos de grupo"
    echo "  • Verificar que la cámara esté conectada físicamente"
    echo "  • Ajustar configuración en config/camara.conf según necesidades"
    
    echo
    print_question "¿Desea iniciar el test del sistema ahora? (S/n):"
    read -p "" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        if test_system; then
            print_success "✅ Test del sistema exitoso"
        else
            print_warning "⚠️  Test del sistema falló - revisar configuración"
        fi
    fi
    
    echo
    print_question "¿Desea reiniciar el sistema ahora? (s/N):"
    read -p "" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        print_info "🔄 Reiniciando sistema en 5 segundos..."
        sleep 5
        sudo reboot
    fi
}

# Función principal
main() {
    print_banner
    
    # Verificaciones iniciales
    check_root
    check_os
    check_python
    
    print_info "Iniciando instalación en: $PROJECT_ROOT"
    print_info "Usuario actual: $USER"
    
    # Confirmar instalación
    echo
    print_question "¿Continuar con la instalación? (S/n):"
    read -p "" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_info "Instalación cancelada"
        exit 0
    fi
    
    # Proceso de instalación
    update_system
    install_system_dependencies
    enable_camera_uart
    setup_user_permissions
    install_python_dependencies
    setup_directories
    setup_configuration
    install_systemd_service
    create_helper_scripts
    
    # Verificación
    if verify_installation; then
        show_post_install_info
    else
        print_error "❌ La verificación de instalación falló"
        print_info "Revisar los errores anteriores y ejecutar el script nuevamente"
        exit 1
    fi
}

# Manejo de señales
trap 'print_error "Instalación interrumpida"; exit 1' INT TERM

# Ejecutar función principal
main "$@"
