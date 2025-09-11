#!/bin/bash
# Script de instalación simplificado - Sistema de Cámara UART
# Adaptado para la estructura actual del proyecto

set -e

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║         🚀 INSTALADOR SISTEMA CÁMARA UART           ║"
echo "║            Versión Simplificada Funcional           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Verificar que estamos en el directorio correcto
if [[ ! -d "src" ]] || [[ ! -d "scripts" ]]; then
    print_error "Ejecutar desde el directorio del proyecto sistema-camara-uart"
    exit 1
fi

PROJECT_ROOT="$(pwd)"
print_info "Directorio del proyecto: $PROJECT_ROOT"

# 1. Actualizar sistema
print_info "Actualizando sistema..."
sudo apt update

# 2. Instalar dependencias esenciales
print_info "Instalando dependencias esenciales..."
sudo apt install -y \
    python3-picamera2 \
    python3-serial \
    python3-pil \
    python3-venv \
    python3-pip

# 3. Configurar UART y cámara
print_info "Configurando UART y cámara..."
if command -v raspi-config &> /dev/null; then
    sudo raspi-config nonint do_camera 0
    sudo raspi-config nonint do_serial_hw 0
else
    # Configuración manual
    if ! grep -q "camera_auto_detect=1" /boot/config.txt; then
        echo "camera_auto_detect=1" | sudo tee -a /boot/config.txt
    fi
    if ! grep -q "enable_uart=1" /boot/config.txt; then
        echo "enable_uart=1" | sudo tee -a /boot/config.txt
    fi
fi

# 4. Configurar permisos
print_info "Configurando permisos..."
sudo usermod -a -G dialout,video,gpio pi

# 5. Crear entorno virtual si no existe
if [[ ! -d "venv" ]]; then
    print_info "Creando entorno virtual..."
    python3 -m venv venv --system-site-packages
fi

# 6. Instalar dependencias Python
print_info "Instalando dependencias Python..."
source venv/bin/activate
pip install --upgrade pip
pip install pyserial psutil

# 7. Crear archivos necesarios si no existen
print_info "Verificando archivos necesarios..."

# Crear src/__init__.py si no existe
if [[ ! -f "src/__init__.py" ]]; then
    echo "# Sistema de Cámara UART" > src/__init__.py
fi

# Crear configuración si no existe
if [[ ! -f "config/camara.conf" ]] && [[ -f "config/camara.conf.example" ]]; then
    cp config/camara.conf.example config/camara.conf
fi

# 8. Crear directorios necesarios
mkdir -p data/fotos data/temp logs

# 9. Establecer permisos de ejecución
chmod +x scripts/*.py 2>/dev/null || true
chmod +x scripts/*.sh 2>/dev/null || true
chmod +x *.sh 2>/dev/null || true

# 10. Test del sistema
print_info "Probando sistema..."
if python3 scripts/sistema_simple.py; then
    print_success "Sistema funciona correctamente"
else
    print_warning "Sistema tiene problemas, pero instalación completada"
fi

print_success "Instalación completada"
echo ""
print_info "Comandos disponibles:"
echo "  python3 scripts/sistema_simple.py    # Sistema simplificado"
echo "  python3 tests/test_camara.py         # Test de cámara"
echo "  python3 scripts/main_daemon.py      # Daemon completo"
echo ""
print_warning "Reiniciar sistema para aplicar cambios de UART/cámara"
