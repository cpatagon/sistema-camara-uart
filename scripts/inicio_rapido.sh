#!/bin/bash
# Script de inicio rápido para Sistema de Cámara UART
# Versión actualizada - Compatible con rpicam-apps y libcamera-apps

set -e

# Colores para output
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

# Banner
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║         🚀 INICIO RÁPIDO - CÁMARA UART              ║"
echo "║       Compatible con rpicam-apps + libcamera        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Detectar directorio del proyecto automáticamente
detect_project_dir() {
    local current_dir="$(pwd)"
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Si estamos en el directorio scripts, subir un nivel
    if [[ "$(basename "$script_dir")" == "scripts" ]]; then
        echo "$(dirname "$script_dir")"
    # Si estamos en el directorio raíz del proyecto
    elif [[ -f "$current_dir/scripts/main_daemon.py" ]]; then
        echo "$current_dir"
    # Buscar hacia arriba
    elif [[ -f "$(dirname "$current_dir")/scripts/main_daemon.py" ]]; then
        echo "$(dirname "$current_dir")"
    else
        echo ""
    fi
}

PROJECT_DIR=$(detect_project_dir)

if [[ -z "$PROJECT_DIR" ]]; then
    print_error "No se pudo detectar el directorio del proyecto"
    print_info "Ejecutar desde el directorio sistema-camara-uart o scripts/"
    exit 1
fi

print_info "Directorio del proyecto detectado: $PROJECT_DIR"
cd "$PROJECT_DIR"

# Verificar estructura del proyecto
verify_project_structure() {
    print_header "VERIFICANDO ESTRUCTURA DEL PROYECTO"
    
    local required_dirs=("src" "scripts" "config")
    local required_files=("scripts/main_daemon.py" "src/camara_controller.py")
    
    for dir in "${required_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            print_success "Directorio $dir encontrado"
        else
            print_error "Directorio $dir faltante"
            return 1
        fi
    done
    
    for file in "${required_files[@]}"; do
        if [[ -f "$file" ]]; then
            print_success "Archivo $file encontrado"
        else
            print_error "Archivo $file faltante"
            return 1
        fi
    done
    
    print_success "Estructura del proyecto verificada"
    return 0
}

# Verificar y activar entorno virtual
setup_virtual_environment() {
    print_header "CONFIGURANDO ENTORNO VIRTUAL"
    
    local venv_path="$PROJECT_DIR/venv"
    
    if [[ -d "$venv_path" ]]; then
        print_info "Activando entorno virtual existente..."
        source "$venv_path/bin/activate"
        print_success "Entorno virtual activado: $venv_path"
    else
        print_warning "Entorno virtual no encontrado"
        print_info "Creando entorno virtual..."
        
        python3 -m venv "$venv_path" --system-site-packages
        source "$venv_path/bin/activate"
        
        # Instalar dependencias básicas
        pip install --upgrade pip
        pip install pyserial psutil
        
        print_success "Entorno virtual creado y configurado"
    fi
    
    # Verificar dependencias Python críticas
    print_info "Verificando dependencias Python..."
    
    if python3 -c "import serial; print('✅ pyserial OK')" 2>/dev/null; then
        print_success "pyserial disponible"
    else
        print_warning "pyserial no disponible, instalando..."
        pip install pyserial
    fi
    
    if python3 -c "from picamera2 import Picamera2; print('✅ picamera2 OK')" 2>/dev/null; then
        print_success "picamera2 disponible"
    else
        print_warning "picamera2 no disponible (se usará alternativa)"
    fi
}

# Verificar configuración
verify_configuration() {
    print_header "VERIFICANDO CONFIGURACIÓN"
    
    local config_file="$PROJECT_DIR/config/camara.conf"
    local config_example="$PROJECT_DIR/config/camara.conf.example"
    
    if [[ -f "$config_file" ]]; then
        print_success "Archivo de configuración encontrado: $config_file"
    elif [[ -f "$config_example" ]]; then
        print_info "Creando configuración desde plantilla..."
        cp "$config_example" "$config_file"
        print_success "Configuración creada desde: $config_example"
    else
        print_error "No se encontró archivo de configuración"
        print_info "Crear manualmente: config/camara.conf"
        return 1
    fi
    
    # Verificar directorios de datos
    local data_dirs=("data/fotos" "data/temp" "logs")
    for dir in "${data_dirs[@]}"; do
        mkdir -p "$PROJECT_DIR/$dir"
        print_success "Directorio $dir verificado"
    done
    
    return 0
}

# Detectar sistema de cámara disponible
detect_camera_system() {
    print_header "DETECTANDO SISTEMA DE CÁMARA"
    
    local rpicam_commands=("rpicam-still" "rpicam-hello")
    local libcamera_commands=("libcamera-still" "libcamera-hello")
    local found_commands=()
    
    # Verificar comandos rpicam (Bookworm)
    for cmd in "${rpicam_commands[@]}"; do
        if command -v "$cmd" &> /dev/null; then
            found_commands+=("$cmd")
            print_success "$cmd disponible (Raspberry Pi OS Bookworm)"
        fi
    done
    
    # Verificar comandos libcamera (anteriores)
    for cmd in "${libcamera_commands[@]}"; do
        if command -v "$cmd" &> /dev/null; then
            found_commands+=("$cmd")
            print_success "$cmd disponible (Raspberry Pi OS anteriores)"
        fi
    done
    
    if [[ ${#found_commands[@]} -eq 0 ]]; then
        print_warning "No se encontraron comandos de cámara del sistema"
        print_info "El sistema usará picamera2 o modo simulación"
    else
        print_success "Comandos de cámara detectados: ${#found_commands[@]}"
        
        # Test rápido de cámara
        if command -v "rpicam-hello" &> /dev/null; then
            if timeout 5s rpicam-hello -t 100 &>/dev/null; then
                print_success "Cámara verificada con rpicam-hello"
            else
                print_warning "Comando rpicam-hello disponible pero cámara no responde"
            fi
        elif command -v "libcamera-hello" &> /dev/null; then
            if timeout 5s libcamera-hello --timeout 100 &>/dev/null; then
                print_success "Cámara verificada con libcamera-hello"
            else
                print_warning "Comando libcamera-hello disponible pero cámara no responde"
            fi
        fi
    fi
}

# Verificar permisos de usuario
verify_user_permissions() {
    print_header "VERIFICANDO PERMISOS DE USUARIO"
    
    local required_groups=("dialout" "video")
    local user_groups=$(groups "$USER")
    
    for group in "${required_groups[@]}"; do
        if echo "$user_groups" | grep -q "$group"; then
            print_success "Usuario en grupo: $group"
        else
            print_warning "Usuario NO está en grupo: $group"
            print_info "Ejecutar: sudo usermod -a -G $group $USER"
        fi
    done
    
    # Verificar puerto UART
    local uart_ports=("/dev/ttyS0" "/dev/ttyAMA0" "/dev/ttyUSB0")
    local uart_found=false
    
    for port in "${uart_ports[@]}"; do
        if [[ -e "$port" ]]; then
            print_success "Puerto UART disponible: $port"
            uart_found=true
            
            # Verificar permisos de escritura
            if [[ -w "$port" ]]; then
                print_success "Permisos de escritura OK para $port"
            else
                print_warning "Sin permisos de escritura para $port"
            fi
        fi
    done
    
    if ! $uart_found; then
        print_warning "No se encontraron puertos UART"
        print_info "El sistema funcionará en modo simulación"
    fi
}

# Test rápido del sistema
quick_system_test() {
    print_header "TEST RÁPIDO DEL SISTEMA"
    
    # Configurar PYTHONPATH
    export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"
    
    print_info "Probando importación de módulos..."
    
    if python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/src')
try:
    from camara_controller import CamaraController
    print('✅ CamaraController importado correctamente')
    
    controller = CamaraController()
    info = controller.obtener_info_sistema_camara()
    print(f'✅ Método de captura: {info[\"metodo_captura\"]}')
    print(f'✅ Comando activo: {info[\"comando_activo\"]}')
    
    if controller.verificar_camara_disponible():
        print('✅ Cámara disponible y funcional')
    else:
        print('⚠️  Cámara con limitaciones (normal en algunos sistemas)')
    
except Exception as e:
    print(f'❌ Error: {e}')
    exit(1)
" 2>/dev/null; then
        print_success "Test de módulos completado exitosamente"
    else
        print_error "Error en test de módulos"
        print_info "Verificar instalación con: ./install.sh"
        return 1
    fi
}

# Función principal para iniciar el sistema
start_system() {
    print_header "INICIANDO SISTEMA DE CÁMARA UART"
    
    # Configurar variables de entorno
    export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"
    
    print_info "Configuración del entorno:"
    print_info "  • Directorio: $PROJECT_DIR"
    print_info "  • PYTHONPATH: $PYTHONPATH"
    print_info "  • Usuario: $USER"
    
    # Iniciar el daemon principal
    local daemon_script="$PROJECT_DIR/scripts/main_daemon.py"
    
    if [[ -f "$daemon_script" ]]; then
        print_success "Iniciando daemon principal..."
        print_info "💡 Para detener el sistema: Ctrl+C"
        print_info "💡 Para test rápido: python3 scripts/main_daemon.py --test"
        echo
        
        # Ejecutar daemon con todos los argumentos pasados al script
        python3 "$daemon_script" "$@"
    else
        print_error "Daemon principal no encontrado: $daemon_script"
        return 1
    fi
}

# Función para mostrar ayuda
show_help() {
    echo "🚀 Script de Inicio Rápido - Sistema de Cámara UART"
    echo
    echo "Uso: $0 [opciones]"
    echo
    echo "Opciones:"
    echo "  --test          Ejecutar solo tests del sistema"
    echo "  --debug         Iniciar en modo debug"
    echo "  --help          Mostrar esta ayuda"
    echo "  --verify-only   Solo verificar configuración"
    echo "  --config FILE   Usar archivo de configuración específico"
    echo
    echo "Ejemplos:"
    echo "  $0                    # Inicio normal"
    echo "  $0 --test            # Solo tests"
    echo "  $0 --debug           # Modo debug"
    echo "  $0 --verify-only     # Solo verificación"
    echo
    echo "📚 Más información:"
    echo "  • README.md - Documentación completa"
    echo "  • python3 scripts/cliente_foto.py - Cliente interactivo"
    echo "  • python3 tests/test_camara.py - Tests específicos"
}

# Función principal
main() {
    # Procesar argumentos
    local verify_only=false
    local show_help_flag=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help_flag=true
                shift
                ;;
            --verify-only)
                verify_only=true
                shift
                ;;
            *)
                # Pasar argumentos restantes al daemon
                break
                ;;
        esac
    done
    
    if $show_help_flag; then
        show_help
        return 0
    fi
    
    # Ejecutar verificaciones
    if ! verify_project_structure; then
        print_error "Error en estructura del proyecto"
        return 1
    fi
    
    setup_virtual_environment
    
    if ! verify_configuration; then
        print_error "Error en configuración"
        return 1
    fi
    
    detect_camera_system
    verify_user_permissions
    
    if ! quick_system_test; then
        print_error "Error en test del sistema"
        print_info "Ejecutar instalación completa: ./install.sh"
        return 1
    fi
    
    if $verify_only; then
        print_success "🎉 Verificación completada - Sistema listo"
        return 0
    fi
    
    # Iniciar sistema
    start_system "$@"
}

# Manejo de señales
trap 'print_warning "\n🛑 Inicio interrumpido"; exit 1' INT TERM

# Ejecutar función principal con todos los argumentos
main "$@"
