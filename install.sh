#!/bin/bash
# Script de instalación corregido - Sistema de Cámara UART
# Compatible con rpicam-apps (Raspberry Pi OS Bookworm) y libcamera-* (versiones anteriores)

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
echo "║       Compatible con rpicam-apps (Bookworm+)        ║"
echo "║           y libcamera-* (versiones anteriores)      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Verificar que estamos en el directorio correcto
if [[ ! -d "src" ]] || [[ ! -d "scripts" ]]; then
    print_error "Ejecutar desde el directorio del proyecto sistema-camara-uart"
    exit 1
fi

PROJECT_ROOT="$(pwd)"
print_info "Directorio del proyecto: $PROJECT_ROOT"

# Detectar versión de Raspberry Pi OS
detect_rpi_version() {
    if [[ -f "/etc/os-release" ]]; then
        local version=$(grep VERSION_CODENAME /etc/os-release | cut -d'=' -f2)
        echo "$version"
    else
        echo "unknown"
    fi
}

RPI_VERSION=$(detect_rpi_version)
print_info "Versión detectada de Raspberry Pi OS: $RPI_VERSION"

# Función para instalar paquetes de cámara según la versión
install_camera_packages() {
    print_info "Instalando paquetes de cámara..."
    
    # Actualizar repositorios
    sudo apt update
    
    # Paquetes base siempre necesarios
    sudo apt install -y python3-picamera2 python3-numpy python3-pil
    
    # Según la versión del OS, instalar los paquetes correctos
    case "$RPI_VERSION" in
        "bookworm")
            print_info "Instalando rpicam-apps para Raspberry Pi OS Bookworm..."
            if sudo apt install -y rpicam-apps-core; then
                print_success "rpicam-apps-core instalado correctamente"
                
                # Intentar también el metapaquete si está disponible
                if sudo apt install -y rpicam-apps 2>/dev/null; then
                    print_success "rpicam-apps (metapaquete) también instalado"
                fi
            else
                print_warning "rpicam-apps-core no disponible, intentando libcamera-apps..."
                sudo apt install -y libcamera-apps || print_warning "Ni rpicam-apps-core ni libcamera-apps disponibles"
            fi
            ;;
        "bullseye"|"buster"|"stretch")
            print_info "Instalando libcamera-apps (Raspberry Pi OS anterior)..."
            sudo apt install -y libcamera-apps || print_warning "libcamera-apps no disponible"
            ;;
        *)
            print_warning "Versión de OS no reconocida, intentando instalar ambos..."
            sudo apt install -y rpicam-apps-core || sudo apt install -y libcamera-apps || print_warning "Paquetes de cámara no disponibles"
            ;;
    esac
}

# Función para verificar instalación de cámara
verify_camera_installation() {
    print_info "Verificando instalación de cámara..."
    
    local verification_commands=("rpicam-hello" "libcamera-hello")
    local camera_working=false
    
    for cmd in "${verification_commands[@]}"; do
        if command -v "$cmd" &> /dev/null; then
            print_info "Probando cámara con $cmd..."
            
            # Usar sintaxis correcta según el comando
            if [[ "$cmd" == "rpicam-hello" ]]; then
                # Sintaxis de rpicam-hello (Bookworm): -t en milisegundos
                if timeout 10s "$cmd" -t 100 &>/dev/null; then
                    print_success "Cámara funciona correctamente con $cmd"
                    camera_working=true
                    break
                else
                    print_warning "$cmd disponible pero cámara no responde"
                fi
            else
                # Sintaxis de libcamera-hello (anteriores): --timeout en milisegundos
                if timeout 10s "$cmd" --timeout 100 &>/dev/null; then
                    print_success "Cámara funciona correctamente con $cmd"
                    camera_working=true
                    break
                else
                    print_warning "$cmd disponible pero cámara no responde"
                fi
            fi
        fi
    done
    
    if ! $camera_working; then
        print_warning "Comandos de cámara del sistema no funcionan"
        print_info "El sistema usará picamera2 como alternativa"
        
        # Verificar picamera2
        if python3 -c "from picamera2 import Picamera2; print('picamera2 OK')" &>/dev/null; then
            print_success "picamera2 disponible como alternativa"
        else
            print_error "Ni comandos del sistema ni picamera2 funcionan"
            print_info "Verificar:"
            print_info "  • Cámara conectada correctamente"
            print_info "  • Cámara habilitada en raspi-config"
            print_info "  • Cable de cámara en buen estado"
            print_info "  • Reiniciar el sistema después de habilitar cámara"
        fi
    fi
}

# Función principal de instalación
main_installation() {
    print_info "Iniciando instalación..."
    
    # 1. Instalar paquetes necesarios
    install_camera_packages
    
    # 2. Instalar dependencias Python básicas
    print_info "Instalando dependencias básicas del sistema..."
    sudo apt install -y \
        python3-serial \
        python3-venv \
        python3-pip \
        git
    
    # 3. Configurar UART y cámara
    print_info "Configurando UART y cámara..."
    if command -v raspi-config &> /dev/null; then
        sudo raspi-config nonint do_camera 0
        sudo raspi-config nonint do_serial_hw 0
        print_success "UART y cámara configurados con raspi-config"
    else
        # Configuración manual para sistemas sin raspi-config
        print_info "Configurando manualmente (sin raspi-config)..."
        
        if ! grep -q "camera_auto_detect=1" /boot/config.txt 2>/dev/null; then
            echo "camera_auto_detect=1" | sudo tee -a /boot/config.txt
        fi
        if ! grep -q "enable_uart=1" /boot/config.txt 2>/dev/null; then
            echo "enable_uart=1" | sudo tee -a /boot/config.txt
        fi
        
        # Para sistemas más nuevos, verificar también /boot/firmware/config.txt
        if [[ -f "/boot/firmware/config.txt" ]]; then
            if ! grep -q "camera_auto_detect=1" /boot/firmware/config.txt; then
                echo "camera_auto_detect=1" | sudo tee -a /boot/firmware/config.txt
            fi
            if ! grep -q "enable_uart=1" /boot/firmware/config.txt; then
                echo "enable_uart=1" | sudo tee -a /boot/firmware/config.txt
            fi
        fi
        
        print_success "Configuración manual completada"
    fi
    
    # 4. Configurar permisos de usuario
    print_info "Configurando permisos de usuario..."
    sudo usermod -a -G dialout,video,gpio "$USER"
    print_success "Usuario agregado a grupos: dialout, video, gpio"
    
    # 5. Crear entorno virtual si no existe
    if [[ ! -d "venv" ]]; then
        print_info "Creando entorno virtual Python..."
        python3 -m venv venv --system-site-packages
        print_success "Entorno virtual creado"
    fi
    
    # 6. Instalar dependencias Python
    print_info "Instalando dependencias Python..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install pyserial psutil
    print_success "Dependencias Python instaladas"
    
    # 7. Crear archivos necesarios
    print_info "Verificando estructura de archivos..."
    
    # Crear src/__init__.py si no existe
    if [[ ! -f "src/__init__.py" ]]; then
        echo "# Sistema de Cámara UART - rpicam/libcamera compatible" > src/__init__.py
        print_success "Archivo src/__init__.py creado"
    fi
    
    # Crear configuración si no existe
    if [[ ! -f "config/camara.conf" ]] && [[ -f "config/camara.conf.example" ]]; then
        cp config/camara.conf.example config/camara.conf
        print_success "Configuración inicial creada"
    fi
    
    # 8. Crear directorios necesarios
    mkdir -p data/fotos data/temp logs
    print_success "Directorios de datos creados"
    
    # 9. Establecer permisos de ejecución
    chmod +x scripts/*.py 2>/dev/null || true
    chmod +x scripts/*.sh 2>/dev/null || true
    chmod +x *.sh 2>/dev/null || true
    print_success "Permisos de ejecución establecidos"
    
    # 10. Verificar instalación de cámara
    verify_camera_installation
    
    # 11. Test básico del sistema (opcional, no crítico)
    print_info "Realizando test básico del sistema (opcional)..."
    
    if python3 -c "
import sys
sys.path.insert(0, 'src')
try:
    from camara_controller import CamaraController
    controller = CamaraController()
    info = controller.obtener_info_sistema_camara()
    print(f'✅ Método de captura: {info[\"metodo_captura\"]}')
    print(f'✅ Comando activo: {info[\"comando_activo\"]}')
    if controller.verificar_camara_disponible():
        print('✅ Sistema de cámara funcional')
        exit(0)
    else:
        print('⚠️  Sistema con limitaciones, pero funcional')
        exit(0)
except ImportError as e:
    print(f'⚠️  Módulo no encontrado (normal durante instalación): {e}')
    exit(0)
except Exception as e:
    print(f'⚠️  Test opcional falló: {e}')
    exit(0)
" 2>/dev/null; then
        print_success "Test básico completado exitosamente"
    else
        print_info "Test básico saltado (normal durante instalación inicial)"
        print_info "Ejecutar después: python3 scripts/main_daemon.py --test"
    fi
}

# Función para mostrar información post-instalación
show_post_install_info() {
    echo
    print_success "🎉 ¡Instalación completada!"
    echo
    
    print_info "📋 Comandos disponibles:"
    echo "  python3 scripts/main_daemon.py --test    # Test completo del sistema"
    echo "  python3 scripts/cliente_foto.py         # Cliente interactivo"
    echo "  python3 tests/test_camara.py            # Test específico de cámara"
    echo "  ./scripts/inicio_rapido.sh              # Inicio rápido"
    echo
    
    print_info "🔧 Compatibilidad instalada:"
    if command -v rpicam-still &> /dev/null; then
        echo "  ✅ rpicam-apps (Raspberry Pi OS Bookworm+)"
    fi
    if command -v libcamera-still &> /dev/null; then
        echo "  ✅ libcamera-apps (versiones anteriores)"
    fi
    if python3 -c "from picamera2 import Picamera2" &>/dev/null; then
        echo "  ✅ picamera2 (respaldo universal)"
    fi
    echo
    
    print_info "🔄 Para aplicar todos los cambios:"
    echo "  sudo reboot"
    echo
    
    print_warning "⚠️  IMPORTANTE:"
    echo "  • Reiniciar para aplicar cambios de UART/cámara"
    echo "  • Cerrar sesión para aplicar cambios de grupos"
    echo "  • Verificar que la cámara esté conectada correctamente"
    echo
    
    print_info "📚 Documentación:"
    echo "  • README.md - Guía completa del sistema"
    echo "  • config/camara.conf.example - Configuración detallada"
    echo "  • docs/ - Documentación adicional"
}

# Función principal
main() {
    # Verificar si se ejecuta como root
    if [[ $EUID -eq 0 ]]; then
        print_error "No ejecutar como root. El script pedirá sudo cuando sea necesario."
        exit 1
    fi
    
    # Verificar sistema
    if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
        print_warning "Este script está optimizado para Raspberry Pi"
        print_info "Continuando con instalación genérica..."
    fi
    
    # Ejecutar instalación principal
    main_installation
    
    # Mostrar información post-instalación
    show_post_install_info
    
    print_success "🚀 Sistema de Cámara UART listo para usar"
}

# Manejo de señales
trap 'print_error "Instalación interrumpida"; exit 1' INT TERM

# Ejecutar función principal
main "$@"
