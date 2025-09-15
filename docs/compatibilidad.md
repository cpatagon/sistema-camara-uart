#!/bin/bash
# Script de verificación de compatibilidad rpicam-apps vs libcamera-apps
# Versión actualizada con sintaxis correcta

set -e

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_header() { echo -e "${CYAN}[=== $1 ===]${NC}"; }

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║         🔍 VERIFICADOR DE COMPATIBILIDAD            ║"
echo "║       rpicam-apps vs libcamera-apps                 ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Detectar versión del OS
detect_os_version() {
    if [[ -f "/etc/os-release" ]]; then
        local version=$(grep VERSION_CODENAME /etc/os-release | cut -d'=' -f2)
        echo "$version"
    else
        echo "unknown"
    fi
}

OS_VERSION=$(detect_os_version)
print_info "Raspberry Pi OS detectado: $OS_VERSION"

# Verificar paquetes instalados
print_header "PAQUETES INSTALADOS"

packages_to_check=("rpicam-apps-core" "rpicam-apps" "libcamera-apps" "python3-picamera2")
installed_packages=()

for package in "${packages_to_check[@]}"; do
    if dpkg -l | grep -q "^ii.*$package"; then
        version=$(dpkg -l | grep "^ii.*$package" | awk '{print $3}')
        print_success "$package ($version)"
        installed_packages+=("$package")
    else
        print_warning "$package - No instalado"
    fi
done

# Verificar comandos disponibles
print_header "COMANDOS DISPONIBLES"

commands_to_check=(
    "rpicam-still:Captura de fotos (Bookworm)"
    "rpicam-vid:Grabación de video (Bookworm)"
    "rpicam-hello:Test de cámara (Bookworm)"
    "rpicam-jpeg:Captura JPEG (Bookworm)"
    "libcamera-still:Captura de fotos (Anteriores)"
    "libcamera-vid:Grabación de video (Anteriores)"
    "libcamera-hello:Test de cámara (Anteriores)"
    "libcamera-jpeg:Captura JPEG (Anteriores)"
)

available_commands=()

for cmd_desc in "${commands_to_check[@]}"; do
    cmd="${cmd_desc%%:*}"
    desc="${cmd_desc##*:}"
    
    if command -v "$cmd" &> /dev/null; then
        print_success "$cmd - $desc"
        available_commands+=("$cmd")
    else
        print_warning "$cmd - No disponible"
    fi
done

# Test de sintaxis de comandos
print_header "VERIFICACIÓN DE SINTAXIS"

test_camera_syntax() {
    local cmd="$1"
    local desc="$2"
    
    print_info "Probando sintaxis de $cmd..."
    
    if [[ "$cmd" == rpicam-* ]]; then
        # Sintaxis rpicam (Bookworm): -t en milisegundos, -o para output
        if timeout 10s "$cmd" --help &>/dev/null; then
            print_success "$cmd - Sintaxis rpicam-apps (Bookworm) disponible"
            
            # Test rápido de funcionamiento
            if [[ "$cmd" == "rpicam-hello" ]]; then
                if timeout 5s "$cmd" -t 100 &>/dev/null; then
                    print_success "$cmd - Test funcional exitoso"
                else
                    print_warning "$cmd - Disponible pero test falló (posible problema de cámara)"
                fi
            fi
        else
            print_error "$cmd - Error en help"
        fi
    else
        # Sintaxis libcamera (anteriores): --timeout en milisegundos, --output
        if timeout 10s "$cmd" --help &>/dev/null; then
            print_success "$cmd - Sintaxis libcamera-apps (anteriores) disponible"
            
            # Test rápido de funcionamiento
            if [[ "$cmd" == "libcamera-hello" ]]; then
                if timeout 5s "$cmd" --timeout 100 &>/dev/null; then
                    print_success "$cmd - Test funcional exitoso"
                else
                    print_warning "$cmd - Disponible pero test falló (posible problema de cámara)"
                fi
            fi
        else
            print_error "$cmd - Error en help"
        fi
    fi
}

# Probar comandos principales
primary_commands=("rpicam-hello" "libcamera-hello" "rpicam-still" "libcamera-still")

for cmd in "${primary_commands[@]}"; do
    if command -v "$cmd" &> /dev/null; then
        test_camera_syntax "$cmd"
    fi
done

# Verificar hardware de cámara
print_header "HARDWARE DE CÁMARA"

if command -v vcgencmd &> /dev/null; then
    camera_status=$(vcgencmd get_camera 2>/dev/null || echo "error")
    if [[ "$camera_status" == *"supported=1 detected=1"* ]]; then
        print_success "Cámara detectada por vcgencmd: $camera_status"
    elif [[ "$camera_status" == *"supported=1"* ]]; then
        print_warning "Cámara soportada pero no detectada: $camera_status"
    else
        print_error "Problema con cámara: $camera_status"
    fi
else
    print_warning "vcgencmd no disponible"
fi

# Verificar configuración de boot
print_header "CONFIGURACIÓN DE BOOT"

boot_configs=("/boot/config.txt" "/boot/firmware/config.txt")
config_found=false

for config_file in "${boot_configs[@]}"; do
    if [[ -f "$config_file" ]]; then
        config_found=true
        print_info "Verificando $config_file..."
        
        if grep -q "camera_auto_detect=1" "$config_file" 2>/dev/null; then
            print_success "camera_auto_detect=1 configurado"
        else
            print_warning "camera_auto_detect=1 no encontrado"
        fi
        
        if grep -q "enable_uart=1" "$config_file" 2>/dev/null; then
            print_success "enable_uart=1 configurado"
        else
            print_warning "enable_uart=1 no encontrado"
        fi
        
        # Verificar start_x (legacy)
        if grep -q "start_x=1" "$config_file" 2>/dev/null; then
            print_info "start_x=1 encontrado (configuración legacy)"
        fi
        
        break
    fi
done

if ! $config_found; then
    print_error "No se encontró archivo de configuración de boot"
fi

# Recomendaciones
print_header "RECOMENDACIONES"

if [[ ${#available_commands[@]} -eq 0 ]]; then
    print_error "No hay comandos de cámara disponibles"
    echo "💡 Soluciones:"
    echo "   • sudo apt update && sudo apt install rpicam-apps-core"
    echo "   • sudo apt install libcamera-apps (si rpicam-apps-core no está disponible)"
    echo "   • Verificar que la cámara esté conectada"
    echo "   • Ejecutar raspi-config para habilitar cámara"
    
elif [[ " ${available_commands[*]} " =~ " rpicam-hello " ]]; then
    print_success "Sistema Bookworm con rpicam-apps - Configuración óptima"
    echo "💡 Tu sistema está actualizado y usa la sintaxis moderna"
    
elif [[ " ${available_commands[*]} " =~ " libcamera-hello " ]]; then
    print_success "Sistema anterior con libcamera-apps - Funcional"
    echo "💡 Consideraciones:"
    echo "   • Sistema funcional con libcamera-apps"
    echo "   • Actualizar a Bookworm para rpicam-apps si es posible"
    echo "   • El código es compatible con ambos sistemas"
    
else
    print_warning "Solo comandos parciales disponibles"
fi

# Test de python
print_header "VERIFICACIÓN DE PYTHON"

if python3 -c "from picamera2 import Picamera2; print('✅ picamera2 OK')" 2>/dev/null; then
    print_success "picamera2 disponible"
else
    print_warning "picamera2 no disponible"
    echo "💡 Instalar con: sudo apt install python3-picamera2"
fi

if python3 -c "import serial; print('✅ pyserial OK')" 2>/dev/null; then
    print_success "pyserial disponible"
else
    print_warning "pyserial no disponible"
    echo "💡 Instalar con: pip install pyserial"
fi

# Resumen final
print_header "RESUMEN FINAL"

total_commands=${#available_commands[@]}
primary_available=0

for cmd in "${available_commands[@]}"; do
    if [[ "$cmd" == *"-hello" ]] || [[ "$cmd" == *"-still" ]]; then
        primary_available=$((primary_available + 1))
    fi
done

if [[ $primary_available -ge 2 ]]; then
    print_success "🎉 Sistema completamente compatible"
    echo "✅ Comandos principales disponibles: $primary_available"
    echo "✅ Total de comandos: $total_commands"
    
    if [[ " ${available_commands[*]} " =~ " rpicam-hello " ]]; then
        echo "🚀 Usando rpicam-apps (Bookworm) - Sintaxis moderna"
    else
        echo "🔧 Usando libcamera-apps (anterior) - Sintaxis legacy"
    fi
    
elif [[ $primary_available -ge 1 ]]; then
    print_warning "⚠️  Sistema parcialmente compatible"
    echo "⚠️  Comandos principales: $primary_available (recomendado: 2+)"
    echo "💡 Instalar paquetes faltantes"
    
else
    print_error "❌ Sistema no compatible"
    echo "❌ No hay comandos principales de cámara"
    echo "💡 Ejecutar instalación completa"
fi

echo
print_info "📚 Para más información:"
print_info "   • ./install.sh - Instalación automática completa"
print_info "   • python3 tests/test_camara.py - Test detallado"
print_info "   • python3 scripts/main_daemon.py --test - Test del sistema"
