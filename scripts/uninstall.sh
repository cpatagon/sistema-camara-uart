#!/bin/bash
# ============================================================================
# DESINSTALADOR ACTUALIZADO - SISTEMA DE CÁMARA UART v2.0
# ============================================================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Variables globales
SERVICE_NAME="camara-uart"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Opciones de desinstalación
REMOVE_VENV=false
REMOVE_DATA=false
REMOVE_LOGS=false
RESTORE_CONFIGS=false
REMOVE_USER_FROM_GROUPS=false
REMOVE_FOTODESCARGA=false

print_banner() {
    echo -e "${RED}"
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║      🗑️  DESINSTALADOR SISTEMA CÁMARA UART v2.0     ║"
    echo "║                                                      ║"
    echo "║     Desinstalación completa para Raspberry Pi       ║"
    echo "║        Incluye comandos FotoDescarga nuevos         ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() { echo -e "${BLUE}[PASO]${NC} $1"; }
print_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_question() { echo -e "${MAGENTA}[?]${NC} $1"; }

check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "No ejecutar este script como root directamente."
        exit 1
    fi
}

show_uninstall_options() {
    print_step "Configurando opciones de desinstalación..."
    echo
    
    print_question "¿Remover comandos FotoDescarga y restaurar main_daemon.py original? (S/n):"
    read -p "" -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Nn]$ ]] && REMOVE_FOTODESCARGA=true
    
    print_question "¿Eliminar entorno virtual Python? (S/n):"
    read -p "" -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Nn]$ ]] && REMOVE_VENV=true
    
    print_question "¿Eliminar datos de usuario (fotos, configuración)? (s/N):"
    read -p "" -n 1 -r
    echo
    [[ $REPLY =~ ^[Ss]$ ]] && REMOVE_DATA=true
    
    print_question "¿Eliminar archivos de log? (S/n):"
    read -p "" -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Nn]$ ]] && REMOVE_LOGS=true
    
    print_question "¿Restaurar configuraciones originales? (S/n):"
    read -p "" -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Nn]$ ]] && RESTORE_CONFIGS=true
    
    print_question "¿Remover usuario de grupos especiales? (s/N):"
    read -p "" -n 1 -r
    echo
    [[ $REPLY =~ ^[Ss]$ ]] && REMOVE_USER_FROM_GROUPS=true
}

stop_all_processes() {
    print_step "Deteniendo todos los procesos del sistema..."
    
    if systemctl list-unit-files 2>/dev/null | grep -q "$SERVICE_NAME.service"; then
        if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
            print_info "Deteniendo servicio $SERVICE_NAME..."
            sudo systemctl stop "$SERVICE_NAME"
        fi
    fi
    
    print_info "Deteniendo procesos Python del sistema de cámara..."
    pkill -f "main_daemon.py" 2>/dev/null || true
    pkill -f "cliente_foto.py" 2>/dev/null || true
    pkill -f "test_fotodescarga.py" 2>/dev/null || true
    pkill -f "receptor_archivos.py" 2>/dev/null || true
    pkill -f "diagnostico_uart.py" 2>/dev/null || true
    
    sleep 2
    print_success "Procesos detenidos"
}

remove_fotodescarga_commands() {
    if [[ $REMOVE_FOTODESCARGA == true ]]; then
        print_step "Removiendo comandos FotoDescarga..."
        
        # Buscar main_daemon.py en múltiples ubicaciones
        DAEMON_LOCATIONS=(
            "$PROJECT_ROOT/scripts/main_daemon.py"
            "$PROJECT_ROOT/main_daemon.py"
            "$PROJECT_ROOT/src/main_daemon.py"
        )
        
        DAEMON_FILE=""
        for location in "${DAEMON_LOCATIONS[@]}"; do
            if [[ -f "$location" ]]; then
                DAEMON_FILE="$location"
                break
            fi
        done
        
        if [[ -z "$DAEMON_FILE" ]]; then
            print_warning "No se encontró main_daemon.py para limpiar"
            return 0
        fi
        
        BACKUP_PATTERN="$DAEMON_FILE.backup_*"
        
        if ls $BACKUP_PATTERN 1> /dev/null 2>&1; then
            LATEST_BACKUP=$(ls -t $BACKUP_PATTERN | head -n1)
            print_question "¿Restaurar desde backup $LATEST_BACKUP? (S/n):"
            read -p "" -n 1 -r
            echo
            
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                cp "$LATEST_BACKUP" "$DAEMON_FILE"
                print_success "main_daemon.py restaurado desde backup"
            fi
        else
            print_info "Limpiando comandos FotoDescarga manualmente..."
            if [[ -f "$DAEMON_FILE" ]]; then
                cp "$DAEMON_FILE" "${DAEMON_FILE}.pre-clean.$(date +%Y%m%d_%H%M%S)"
                
                sed -i '/# ===== COMANDOS FOTODESCARGA/,/# ===== FIN COMANDOS FOTODESCARGA =====/d' "$DAEMON_FILE"
                sed -i "/fotodescarga.*cmd_fotodescarga/d" "$DAEMON_FILE"
                sed -i "/fotosize.*cmd_fotodescarga_resolucion/d" "$DAEMON_FILE"
                sed -i "/fotopreset.*cmd_foto_preset/d" "$DAEMON_FILE"
                sed -i "/resoluciones.*cmd_lista_resoluciones/d" "$DAEMON_FILE"
                sed -i "/fotoinmediata.*cmd_fotoinmediata/d" "$DAEMON_FILE"
                
                print_success "Comandos FotoDescarga removidos"
            fi
        fi
        
        # Limpiar archivos relacionados
        FILES_TO_REMOVE=(
            "$PROJECT_ROOT/instalar_fotodescarga_completo.py"
            "$PROJECT_ROOT/test_fotodescarga.py"
            "$PROJECT_ROOT/cliente_limpio.py"
            "$PROJECT_ROOT/diagnostico_uart.py"
            "$PROJECT_ROOT/receptor_archivos.py"
        )
        
        for file in "${FILES_TO_REMOVE[@]}"; do
            if [[ -f "$file" ]]; then
                rm -f "$file"
                print_success "Removido: $(basename "$file")"
            fi
        done
    fi
}

cleanup_fotodescarga_temp_files() {
    print_step "Limpiando archivos temporales de FotoDescarga..."
    
    TEMP_DIR="$PROJECT_ROOT/data/temp"
    if [[ -d "$TEMP_DIR" ]]; then
        temp_files_count=$(find "$TEMP_DIR" -name "temp_*.jpg" 2>/dev/null | wc -l)
        if [[ $temp_files_count -gt 0 ]]; then
            print_question "¿Eliminar $temp_files_count archivos temporales? (S/n):"
            read -p "" -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                find "$TEMP_DIR" -name "temp_*.jpg" -delete
                print_success "$temp_files_count archivos temporales eliminados"
            fi
        fi
    fi
    
    DOWNLOAD_DIR="$PROJECT_ROOT/descargas"
    if [[ -d "$DOWNLOAD_DIR" ]]; then
        print_question "¿Eliminar directorio de descargas? (s/N):"
        read -p "" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            rm -rf "$DOWNLOAD_DIR"
            print_success "Directorio de descargas eliminado"
        fi
    fi
    
    CLIENT_HISTORY="$HOME/.camara_uart_historial"
    if [[ -f "$CLIENT_HISTORY" ]]; then
        rm -f "$CLIENT_HISTORY"
        print_success "Historial de cliente eliminado"
    fi
}

cleanup_backup_files() {
    print_step "Limpiando archivos de backup..."
    
    BACKUP_PATTERNS=(
        "$PROJECT_ROOT/scripts/*.backup_*"
        "$PROJECT_ROOT/src/*.backup_*"
        "$PROJECT_ROOT/*.backup_*"
        "$PROJECT_ROOT/config/*.backup*"
    )
    
    backup_count=0
    for pattern in "${BACKUP_PATTERNS[@]}"; do
        for file in $pattern; do
            if [[ -f "$file" ]]; then
                print_question "¿Eliminar backup $(basename "$file")? (S/n):"
                read -p "" -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                    rm -f "$file"
                    ((backup_count++))
                    print_success "Backup eliminado: $(basename "$file")"
                fi
            fi
        done
    done
    
    [[ $backup_count -eq 0 ]] && print_info "No se encontraron archivos de backup"
}

stop_and_remove_service() {
    print_step "Removiendo servicio systemd..."
    
    SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
    
    if systemctl list-unit-files 2>/dev/null | grep -q "$SERVICE_NAME.service"; then
        if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
            sudo systemctl stop "$SERVICE_NAME"
        fi
        
        if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
            sudo systemctl disable "$SERVICE_NAME"
        fi
        
        if [[ -f "$SERVICE_FILE" ]]; then
            sudo rm -f "$SERVICE_FILE"
        fi
        
        sudo systemctl daemon-reload 2>/dev/null || true
        print_success "Servicio removido"
    fi
}

remove_virtual_environment() {
    if [[ $REMOVE_VENV == true ]]; then
        print_step "Removiendo entorno virtual..."
        VENV_DIR="$PROJECT_ROOT/venv"
        if [[ -d "$VENV_DIR" ]]; then
            rm -rf "$VENV_DIR"
            print_success "Entorno virtual removido"
        fi
    fi
}

remove_user_data() {
    if [[ $REMOVE_DATA == true ]]; then
        print_step "Removiendo datos de usuario..."
        
        BACKUP_DIR="$HOME/camara-uart-backup-$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        if [[ -f "$PROJECT_ROOT/config/camara.conf" ]]; then
            cp "$PROJECT_ROOT/config/camara.conf" "$BACKUP_DIR/"
        fi
        
        if [[ -d "$PROJECT_ROOT/data" ]]; then
            rm -rf "$PROJECT_ROOT/data"
            print_success "Datos removidos (backup en $BACKUP_DIR)"
        fi
    fi
}

remove_logs() {
    if [[ $REMOVE_LOGS == true ]]; then
        print_step "Removiendo logs..."
        
        [[ -d "/var/log/camara-uart" ]] && sudo rm -rf "/var/log/camara-uart"
        [[ -d "$PROJECT_ROOT/logs" ]] && rm -rf "$PROJECT_ROOT/logs"
        
        print_success "Logs removidos"
    fi
}

cleanup_temp_files() {
    print_step "Limpiando archivos temporales..."
    
    find "$PROJECT_ROOT" -name "*.pyc" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_ROOT" -name "*.tmp" -delete 2>/dev/null || true
    
    print_success "Archivos temporales limpiados"
}

verify_uninstallation() {
    print_step "Verificando desinstalación..."
    
    ISSUES_FOUND=false
    
    if systemctl list-unit-files 2>/dev/null | grep -q "$SERVICE_NAME.service"; then
        print_error "Servicio systemd aún presente"
        ISSUES_FOUND=true
    fi
    
    if [[ $REMOVE_FOTODESCARGA == true ]]; then
        DAEMON_LOCATIONS=(
            "$PROJECT_ROOT/scripts/main_daemon.py"
            "$PROJECT_ROOT/main_daemon.py"
            "$PROJECT_ROOT/src/main_daemon.py"
        )
        
        for location in "${DAEMON_LOCATIONS[@]}"; do
            if [[ -f "$location" ]] && grep -q "cmd_fotodescarga" "$location" 2>/dev/null; then
                print_error "Comandos FotoDescarga aún presentes"
                ISSUES_FOUND=true
                break
            fi
        done
    fi
    
    if [[ $ISSUES_FOUND == false ]]; then
        print_success "Verificación completada sin problemas"
        return 0
    else
        print_warning "Se encontraron algunos problemas"
        return 1
    fi
}

show_post_uninstall_info() {
    print_step "Información post-desinstalación"
    
    echo
    print_success "🧹 ¡Desinstalación completada!"
    echo
    
    print_info "Para reinstalar:"
    echo "  ./install.sh"
    [[ $REMOVE_FOTODESCARGA == true ]] && echo "  python3 instalar_fotodescarga_completo.py"
}

main() {
    print_banner
    check_root
    
    print_info "Directorio del proyecto: $PROJECT_ROOT"
    echo
    
    show_uninstall_options
    
    echo
    print_question "¿Continuar con la desinstalación? (s/N):"
    read -p "" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        print_info "Desinstalación cancelada"
        exit 0
    fi
    
    # Proceso de desinstalación
    stop_all_processes
    stop_and_remove_service
    remove_fotodescarga_commands
    cleanup_fotodescarga_temp_files
    cleanup_backup_files
    remove_logs
    remove_virtual_environment
    remove_user_data
    cleanup_temp_files
    
    # Verificación final
    if verify_uninstallation; then
        show_post_uninstall_info
    else
        print_warning "La desinstalación se completó con algunos problemas"
    fi
}

# Manejo de señales
trap 'print_error "Desinstalación interrumpida"; exit 1' INT TERM

# Ejecutar función principal
main "$@"
