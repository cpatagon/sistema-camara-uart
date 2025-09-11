#!/bin/bash
# ============================================================================
# SCRIPT DE DESINSTALACIÓN - SISTEMA DE CÁMARA UART
# ============================================================================
#
# Este script desinstala completamente el sistema de cámara UART,
# revirtiendo cambios de configuración y limpiando archivos.
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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Opciones de desinstalación
REMOVE_VENV=false
REMOVE_DATA=false
REMOVE_LOGS=false
RESTORE_CONFIGS=false
REMOVE_USER_FROM_GROUPS=false
FORCE_REMOVAL=false

# Funciones auxiliares
print_banner() {
    echo -e "${RED}"
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║      🗑️  DESINSTALADOR SISTEMA CÁMARA UART          ║"
    echo "║                                                      ║"
    echo "║     Desinstalación completa para Raspberry Pi       ║"
    echo "║           Limpieza de configuraciones               ║"
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

# Mostrar opciones de desinstalación
show_uninstall_options() {
    print_step "Configurando opciones de desinstalación..."
    echo
    
    print_info "Selecciona qué elementos desinstalar:"
    echo
    
    # Opción: Entorno virtual
    print_question "¿Eliminar entorno virtual Python? (recomendado) (S/n):"
    read -p "" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        REMOVE_VENV=true
        print_info "✓ Se eliminará el entorno virtual"
    fi
    
    # Opción: Datos de usuario
    print_question "¿Eliminar datos de usuario (fotos, configuración)? (s/N):"
    read -p "" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        REMOVE_DATA=true
        print_warning "⚠️  Se eliminarán TODAS las fotos y configuraciones"
    fi
    
    # Opción: Logs
    print_question "¿Eliminar archivos de log? (S/n):"
    read -p "" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        REMOVE_LOGS=true
        print_info "✓ Se eliminarán los archivos de log"
    fi
    
    # Opción: Restaurar configuraciones
    print_question "¿Restaurar configuraciones originales (UART, cámara)? (S/n):"
    read -p "" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        RESTORE_CONFIGS=true
        print_info "✓ Se restaurarán las configuraciones originales"
    fi
    
    # Opción: Remover usuario de grupos
    print_question "¿Remover usuario de grupos especiales (dialout, camara-uart)? (s/N):"
    read -p "" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        REMOVE_USER_FROM_GROUPS=true
        print_warning "⚠️  Puede afectar otros programas que usen puerto serie"
    fi
    
    echo
    print_info "Resumen de acciones:"
    [[ $REMOVE_VENV == true ]] && echo "  • Eliminar entorno virtual Python"
    [[ $REMOVE_DATA == true ]] && echo "  • Eliminar datos de usuario y configuración"
    [[ $REMOVE_LOGS == true ]] && echo "  • Eliminar archivos de log"
    [[ $RESTORE_CONFIGS == true ]] && echo "  • Restaurar configuraciones del sistema"
    [[ $REMOVE_USER_FROM_GROUPS == true ]] && echo "  • Remover usuario de grupos especiales"
    echo
}

# Detener y deshabilitar servicio
stop_and_remove_service() {
    print_step "Deteniendo y removiendo servicio systemd..."
    
    SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
    
    # Verificar si el servicio existe
    if systemctl list-unit-files | grep -q "$SERVICE_NAME.service"; then
        
        # Detener servicio si está corriendo
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            print_info "Deteniendo servicio $SERVICE_NAME..."
            sudo systemctl stop "$SERVICE_NAME"
            print_success "Servicio detenido"
        fi
        
        # Deshabilitar servicio
        if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
            print_info "Deshabilitando servicio $SERVICE_NAME..."
            sudo systemctl disable "$SERVICE_NAME"
            print_success "Servicio deshabilitado"
        fi
        
        # Remover archivo de servicio
        if [[ -f "$SERVICE_FILE" ]]; then
            print_info "Removiendo archivo de servicio..."
            sudo rm -f "$SERVICE_FILE"
            print_success "Archivo de servicio removido"
        fi
        
        # Recargar systemd
        print_info "Recargando configuración de systemd..."
        sudo systemctl daemon-reload
        sudo systemctl reset-failed 2>/dev/null || true
        
    else
        print_info "Servicio $SERVICE_NAME no encontrado"
    fi
}

# Remover configuración de logging
remove_logging_config() {
    print_step "Removiendo configuración de logging..."
    
    # Remover configuración de logrotate
    LOGROTATE_CONFIG="/etc/logrotate.d/camara-uart"
    if [[ -f "$LOGROTATE_CONFIG" ]]; then
        print_info "Removiendo configuración de logrotate..."
        sudo rm -f "$LOGROTATE_CONFIG"
        print_success "Configuración de logrotate removida"
    fi
    
    # Remover logs si está seleccionado
    if [[ $REMOVE_LOGS == true ]]; then
        print_info "Removiendo archivos de log..."
        
        # Logs del sistema
        if [[ -d "/var/log/camara-uart" ]]; then
            sudo rm -rf "/var/log/camara-uart"
            print_success "Logs del sistema removidos"
        fi
        
        # Logs locales
        if [[ -d "$PROJECT_ROOT/logs" ]]; then
            rm -rf "$PROJECT_ROOT/logs"
            print_success "Logs locales removidos"
        fi
    else
        print_info "Conservando archivos de log"
    fi
}

# Remover entorno virtual
remove_virtual_environment() {
    if [[ $REMOVE_VENV == true ]]; then
        print_step "Removiendo entorno virtual Python..."
        
        VENV_DIR="$PROJECT_ROOT/venv"
        if [[ -d "$VENV_DIR" ]]; then
            print_info "Removiendo directorio: $VENV_DIR"
            rm -rf "$VENV_DIR"
            print_success "Entorno virtual removido"
        else
            print_info "Entorno virtual no encontrado"
        fi
    else
        print_info "Conservando entorno virtual Python"
    fi
}

# Remover datos de usuario
remove_user_data() {
    if [[ $REMOVE_DATA == true ]]; then
        print_step "Removiendo datos de usuario..."
        
        print_warning "⚠️  ATENCIÓN: Se eliminarán TODOS los datos de usuario"
        print_question "¿Estás seguro? Esta acción NO se puede deshacer (s/N):"
        read -p "" -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            # Hacer backup antes de eliminar
            BACKUP_DIR="$HOME/camara-uart-backup-$(date +%Y%m%d_%H%M%S)"
            print_info "Creando backup en: $BACKUP_DIR"
            mkdir -p "$BACKUP_DIR"
            
            # Backup de configuración
            if [[ -f "$PROJECT_ROOT/config/camara.conf" ]]; then
                cp "$PROJECT_ROOT/config/camara.conf" "$BACKUP_DIR/"
                print_info "Configuración respaldada"
            fi
            
            # Backup de fotos (solo lista)
            if [[ -d "$PROJECT_ROOT/data/fotos" ]]; then
                ls -la "$PROJECT_ROOT/data/fotos" > "$BACKUP_DIR/lista_fotos.txt" 2>/dev/null || true
                print_info "Lista de fotos respaldada"
            fi
            
            # Remover datos
            if [[ -d "$PROJECT_ROOT/data" ]]; then
                rm -rf "$PROJECT_ROOT/data"
                print_success "Datos de usuario removidos"
            fi
            
            # Remover configuración
            if [[ -f "$PROJECT_ROOT/config/camara.conf" ]]; then
                rm -f "$PROJECT_ROOT/config/camara.conf"
                print_success "Configuración removida"
            fi
            
            print_success "Backup creado en: $BACKUP_DIR"
        else
            print_info "Conservando datos de usuario"
        fi
    else
        print_info "Conservando datos de usuario"
    fi
}

# Restaurar configuraciones del sistema
restore_system_configs() {
    if [[ $RESTORE_CONFIGS == true ]]; then
        print_step "Restaurando configuraciones del sistema..."
        
        # Restaurar /boot/config.txt si existe backup
        CONFIG_FILE="/boot/config.txt"
        BACKUP_PATTERN="${CONFIG_FILE}.backup.*"
        
        if ls $BACKUP_PATTERN 1> /dev/null 2>&1; then
            LATEST_BACKUP=$(ls -t $BACKUP_PATTERN | head -n1)
            print_question "¿Restaurar $CONFIG_FILE desde backup $LATEST_BACKUP? (S/n):"
            read -p "" -n 1 -r
            echo
            
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                print_info "Restaurando $CONFIG_FILE..."
                sudo cp "$LATEST_BACKUP" "$CONFIG_FILE"
                print_success "Configuración restaurada desde backup"
                print_warning "⚠️  Reinicio requerido para aplicar cambios"
            fi
        else
            # Deshacer cambios manualmente
            print_info "No se encontraron backups, deshaciendo cambios manualmente..."
            
            if [[ -f "$CONFIG_FILE" ]]; then
                # Remover líneas que agregamos
                print_info "Removiendo configuraciones de cámara y UART..."
                
                # Crear backup antes de modificar
                sudo cp "$CONFIG_FILE" "${CONFIG_FILE}.pre-uninstall.$(date +%Y%m%d_%H%M%S)"
                
                # Remover líneas específicas
                sudo sed -i '/^camera_auto_detect=1$/d' "$CONFIG_FILE"
                sudo sed -i '/^enable_uart=1$/d' "$CONFIG_FILE"
                sudo sed -i '/^gpu_mem=128$/d' "$CONFIG_FILE"
                
                print_success "Configuraciones removidas"
                print_warning "⚠️  Reinicio requerido para aplicar cambios"
            fi
        fi
        
        # Deshabilitar cámara y UART usando raspi-config si está disponible
        if command -v raspi-config &> /dev/null; then
            print_question "¿Deshabilitar cámara usando raspi-config? (s/N):"
            read -p "" -n 1 -r
            echo
            if [[ $REPLY =~ ^[Ss]$ ]]; then
                sudo raspi-config nonint do_camera 1  # Deshabilitar cámara
                print_success "Cámara deshabilitada"
            fi
            
            print_question "¿Deshabilitar UART usando raspi-config? (s/N):"
            read -p "" -n 1 -r
            echo
            if [[ $REPLY =~ ^[Ss]$ ]]; then
                sudo raspi-config nonint do_serial 0  # Deshabilitar UART
                print_success "UART deshabilitado"
            fi
        fi
    else
        print_info "Conservando configuraciones del sistema"
    fi
}

# Remover usuario de grupos
remove_user_from_groups() {
    if [[ $REMOVE_USER_FROM_GROUPS == true ]]; then
        print_step "Removiendo usuario de grupos especiales..."
        
        # Remover de grupo camara-uart
        if getent group camara-uart &> /dev/null; then
            if groups "$USER" | grep -q "camara-uart"; then
                print_info "Removiendo usuario $USER del grupo camara-uart..."
                sudo gpasswd -d "$USER" camara-uart
                print_success "Usuario removido del grupo camara-uart"
            fi
            
            # Eliminar grupo si está vacío
            if ! getent group camara-uart | grep -q ":.*[^:]"; then
                print_info "Eliminando grupo vacío camara-uart..."
                sudo groupdel camara-uart
                print_success "Grupo camara-uart eliminado"
            fi
        fi
        
        # Preguntar sobre grupo dialout (más cuidadoso)
        if groups "$USER" | grep -q "dialout"; then
            print_warning "⚠️  El usuario $USER está en el grupo dialout"
            print_info "Este grupo da acceso a puertos serie y puede ser usado por otros programas"
            print_question "¿Remover usuario del grupo dialout? (s/N):"
            read -p "" -n 1 -r
            echo
            if [[ $REPLY =~ ^[Ss]$ ]]; then
                sudo gpasswd -d "$USER" dialout
                print_success "Usuario removido del grupo dialout"
                print_warning "⚠️  Debe cerrar sesión para aplicar cambios"
            fi
        fi
    else
        print_info "Conservando membresías de grupos"
    fi
}

# Remover scripts auxiliares
remove_helper_scripts() {
    print_step "Removiendo scripts auxiliares..."
    
    SCRIPTS_TO_REMOVE=(
        "$PROJECT_ROOT/inicio_rapido.sh"
        "$PROJECT_ROOT/test_cliente.sh"
        "$PROJECT_ROOT/estado_servicio.sh"
    )
    
    for script in "${SCRIPTS_TO_REMOVE[@]}"; do
        if [[ -f "$script" ]]; then
            rm -f "$script"
            print_success "Removido: $(basename "$script")"
        fi
    done
}

# Remover directorios del sistema
remove_system_directories() {
    print_step "Removiendo directorios del sistema..."
    
    SYSTEM_DIRS=(
        "/var/log/camara-uart"
        "/etc/camara-uart"
    )
    
    for dir in "${SYSTEM_DIRS[@]}"; do
        if [[ -d "$dir" ]]; then
            print_info "Removiendo directorio: $dir"
            sudo rm -rf "$dir"
            print_success "Removido: $dir"
        fi
    done
}

# Limpiar archivos temporales
cleanup_temp_files() {
    print_step "Limpiando archivos temporales..."
    
    # Archivos temporales en el proyecto
    find "$PROJECT_ROOT" -name "*.pyc" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_ROOT" -name "*.tmp" -delete 2>/dev/null || true
    
    # Historial del cliente
    if [[ -f "$HOME/.camara_uart_historial" ]]; then
        rm -f "$HOME/.camara_uart_historial"
        print_success "Historial del cliente removido"
    fi
    
    print_success "Archivos temporales limpiados"
}

# Verificar desinstalación
verify_uninstallation() {
    print_step "Verificando desinstalación..."
    
    ISSUES_FOUND=false
    
    # Verificar servicio systemd
    if systemctl list-unit-files | grep -q "$SERVICE_NAME.service"; then
        print_error "Servicio systemd aún presente"
        ISSUES_FOUND=true
    else
        print_success "Servicio systemd removido correctamente"
    fi
    
    # Verificar archivos de configuración del sistema
    if [[ -f "/etc/logrotate.d/camara-uart" ]]; then
        print_error "Configuración de logrotate aún presente"
        ISSUES_FOUND=true
    else
        print_success "Configuración de logrotate removida"
    fi
    
    # Verificar directorios del sistema
    if [[ -d "/var/log/camara-uart" ]] && [[ $REMOVE_LOGS == true ]]; then
        print_error "Directorio de logs del sistema aún presente"
        ISSUES_FOUND=true
    fi
    
    # Verificar entorno virtual
    if [[ -d "$PROJECT_ROOT/venv" ]] && [[ $REMOVE_VENV == true ]]; then
        print_error "Entorno virtual aún presente"
        ISSUES_FOUND=true
    fi
    
    # Verificar datos
    if [[ -d "$PROJECT_ROOT/data" ]] && [[ $REMOVE_DATA == true ]]; then
        print_error "Datos de usuario aún presentes"
        ISSUES_FOUND=true
    fi
    
    if [[ $ISSUES_FOUND == false ]]; then
        print_success "Verificación de desinstalación completada sin problemas"
        return 0
    else
        print_warning "Se encontraron algunos problemas en la verificación"
        return 1
    fi
}

# Mostrar información post-desinstalación
show_post_uninstall_info() {
    print_step "Información post-desinstalación"
    
    echo
    print_success "🧹 ¡Desinstalación completada!"
    echo
    
    print_info "📋 Resumen de acciones realizadas:"
    echo "  • Servicio systemd detenido y removido"
    echo "  • Configuración de logging removida"
    echo "  • Scripts auxiliares removidos"
    echo "  • Directorios del sistema limpiados"
    
    [[ $REMOVE_VENV == true ]] && echo "  • Entorno virtual Python removido"
    [[ $REMOVE_DATA == true ]] && echo "  • Datos de usuario removidos (con backup)"
    [[ $REMOVE_LOGS == true ]] && echo "  • Archivos de log removidos"
    [[ $RESTORE_CONFIGS == true ]] && echo "  • Configuraciones del sistema restauradas"
    [[ $REMOVE_USER_FROM_GROUPS == true ]] && echo "  • Usuario removido de grupos especiales"
    
    echo
    print_info "📁 Archivos principales del proyecto conservados:"
    echo "  • Código fuente en src/"
    echo "  • Scripts en scripts/"
    echo "  • Documentación en docs/"
    
    if [[ $REMOVE_DATA == true ]]; then
        BACKUP_DIR=$(ls -d "$HOME"/camara-uart-backup-* 2>/dev/null | tail -n1)
        if [[ -n "$BACKUP_DIR" ]]; then
            echo
            print_info "💾 Backup de datos creado en:"
            echo "  $BACKUP_DIR"
        fi
    fi
    
    echo
    if [[ $RESTORE_CONFIGS == true ]] || [[ $REMOVE_USER_FROM_GROUPS == true ]]; then
        print_warning "⚠️  IMPORTANTE:"
        [[ $RESTORE_CONFIGS == true ]] && echo "  • Reinicio requerido para aplicar cambios de configuración"
        [[ $REMOVE_USER_FROM_GROUPS == true ]] && echo "  • Cerrar sesión para aplicar cambios de grupos"
    fi
    
    echo
    print_info "🔄 Para reinstalar el sistema:"
    echo "  ./scripts/install.sh"
    
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
    
    print_info "Directorio del proyecto: $PROJECT_ROOT"
    print_info "Usuario actual: $USER"
    
    # Mostrar advertencia
    echo
    print_warning "⚠️  ADVERTENCIA: Este script desinstalará el sistema de cámara UART"
    print_info "Se pueden conservar datos y configuraciones según tu elección"
    
    # Configurar opciones
    show_uninstall_options
    
    # Confirmación final
    echo
    print_question "¿Continuar con la desinstalación? (s/N):"
    read -p "" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        print_info "Desinstalación cancelada"
        exit 0
    fi
    
    # Proceso de desinstalación
    stop_and_remove_service
    remove_logging_config
    remove_virtual_environment
    remove_user_data
    restore_system_configs
    remove_user_from_groups
    remove_helper_scripts
    remove_system_directories
    cleanup_temp_files
    
    # Verificación
    if verify_uninstallation; then
        show_post_uninstall_info
    else
        print_warning "⚠️  La verificación encontró algunos problemas"
        print_info "La desinstalación se completó pero revisa los errores anteriores"
    fi
}

# Manejo de señales
trap 'print_error "Desinstalación interrumpida"; exit 1' INT TERM

# Ejecutar función principal
main "$@"
