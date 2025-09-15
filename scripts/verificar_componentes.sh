#!/bin/bash
# Verificador de componentes v2.0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo -e "${CYAN}╔══════════════════════════════════════════════════════╗"
    echo -e "║        🔍 VERIFICADOR DE COMPONENTES v2.0           ║"
    echo -e "╚══════════════════════════════════════════════════════╝${NC}"
    echo
}

check_fotodescarga_components() {
    echo -e "${BLUE}📸 COMPONENTES FOTODESCARGA${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    DAEMON_LOCATIONS=("scripts/main_daemon.py" "main_daemon.py" "src/main_daemon.py")
    
    DAEMON_WITH_FOTODESCARGA=""
    for location in "${DAEMON_LOCATIONS[@]}"; do
        if [[ -f "$location" ]] && grep -q "cmd_fotodescarga\|FotoDescarga" "$location" 2>/dev/null; then
            DAEMON_WITH_FOTODESCARGA="$location"
            break
        fi
    done
    
    if [[ -n "$DAEMON_WITH_FOTODESCARGA" ]]; then
        echo -e "  ✅ Comandos FotoDescarga: ${GREEN}Instalados en $DAEMON_WITH_FOTODESCARGA${NC}"
        
        commands_found=()
        grep -q "def cmd_fotodescarga" "$DAEMON_WITH_FOTODESCARGA" 2>/dev/null && commands_found+=("fotodescarga")
        grep -q "def cmd_fotodescarga_resolucion\|fotosize" "$DAEMON_WITH_FOTODESCARGA" 2>/dev/null && commands_found+=("fotosize")
        grep -q "def cmd_foto_preset\|fotopreset" "$DAEMON_WITH_FOTODESCARGA" 2>/dev/null && commands_found+=("fotopreset")
        grep -q "def cmd_lista_resoluciones\|resoluciones" "$DAEMON_WITH_FOTODESCARGA" 2>/dev/null && commands_found+=("resoluciones")
        grep -q "def cmd_fotoinmediata\|fotoinmediata" "$DAEMON_WITH_FOTODESCARGA" 2>/dev/null && commands_found+=("fotoinmediata")
        
        if [[ ${#commands_found[@]} -gt 0 ]]; then
            echo -e "  📋 Comandos detectados: ${CYAN}${commands_found[*]}${NC}"
        fi
    else
        echo -e "  ❌ Comandos FotoDescarga: ${RED}No instalados${NC}"
    fi
    echo
}

check_system_service() {
    echo -e "${BLUE}⚙️ SERVICIO DEL SISTEMA${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    SERVICE_NAME="camara-uart"
    
    if systemctl list-unit-files 2>/dev/null | grep -q "$SERVICE_NAME.service"; then
        echo -e "  ✅ Servicio systemd: ${GREEN}Instalado${NC}"
        
        if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
            echo -e "  🟢 Estado: ${GREEN}Activo${NC}"
        else
            echo -e "  🔴 Estado: ${RED}Inactivo${NC}"
        fi
    else
        echo -e "  ❌ Servicio systemd: ${RED}No instalado${NC}"
    fi
    echo
}

check_directories_and_data() {
    echo -e "${BLUE}📁 DIRECTORIOS Y DATOS${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    directories=("data/fotos:Fotos" "data/temp:Temporales" "logs:Logs" "venv:Python" "descargas:Descargas")
    
    for item in "${directories[@]}"; do
        dir="${item%%:*}"
        desc="${item##*:}"
        
        if [[ -d "$dir" ]]; then
            file_count=$(find "$dir" -type f 2>/dev/null | wc -l)
            echo -e "  📂 $desc: ${GREEN}$dir${NC} ($file_count archivos)"
        else
            echo -e "  📂 $desc: ${YELLOW}$dir (No existe)${NC}"
        fi
    done
    
    if [[ -d "data/temp" ]]; then
        temp_jpg_count=$(find "data/temp" -name "temp_*.jpg" 2>/dev/null | wc -l)
        [[ $temp_jpg_count -gt 0 ]] && echo -e "  ⚠️  Archivos temporales fotoinmediata: ${YELLOW}$temp_jpg_count${NC}"
    fi
    echo
}

check_processes() {
    echo -e "${BLUE}🔄 PROCESOS ACTIVOS${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    processes=("main_daemon.py:Daemon" "cliente_foto.py:Cliente" "test_fotodescarga.py:Test")
    active_processes=0
    
    for item in "${processes[@]}"; do
        process="${item%%:*}"
        desc="${item##*:}"
        
        if pgrep -f "$process" >/dev/null 2>&1; then
            pid=$(pgrep -f "$process")
            echo -e "  🟢 $desc: ${GREEN}Activo (PID: $pid)${NC}"
            ((active_processes++))
        else
            echo -e "  ⚪ $desc: ${YELLOW}Inactivo${NC}"
        fi
    done
    
    [[ $active_processes -eq 0 ]] && echo -e "  ℹ️  No hay procesos ejecutándose"
    echo
}

generate_summary() {
    echo -e "${BLUE}📋 RESUMEN${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    echo -e "  ${GREEN}COMPONENTES DETECTADOS:${NC}"
    
    DAEMON_LOCATIONS=("scripts/main_daemon.py" "main_daemon.py" "src/main_daemon.py")
    for location in "${DAEMON_LOCATIONS[@]}"; do
        if [[ -f "$location" ]] && grep -q "cmd_fotodescarga\|FotoDescarga" "$location" 2>/dev/null; then
            echo -e "    📸 Comandos FotoDescarga en $location"
            break
        fi
    done
    
    systemctl list-unit-files 2>/dev/null | grep -q "camara-uart.service" && echo -e "    ⚙️  Servicio systemd"
    [[ -d "venv" ]] && echo -e "    🐍 Entorno virtual Python"
    [[ -d "data" ]] && echo -e "    📁 Datos de usuario"
    
    backup_count=$(find . -name "*.backup_*" 2>/dev/null | wc -l)
    [[ $backup_count -gt 0 ]] && echo -e "    💾 $backup_count archivos de backup"
    
    echo
    echo -e "  ${CYAN}COMANDO RECOMENDADO:${NC}"
    
    if [[ -f "scripts/uninstall.sh" ]]; then
        echo -e "    ./scripts/uninstall.sh"
    elif [[ -f "uninstall.sh" ]]; then
        echo -e "    ./uninstall.sh"
    else
        echo -e "    ./actualizar_desinstalador.sh  # Crear desinstalador"
    fi
    echo
}

main() {
    print_header
    
    PROJECT_INDICATORS=("src/" "scripts/" "config/" "README.md")
    INDICATORS_FOUND=0
    for indicator in "${PROJECT_INDICATORS[@]}"; do
        [[ -e "$indicator" ]] && ((INDICATORS_FOUND++))
    done
    
    if [[ $INDICATORS_FOUND -lt 2 ]]; then
        echo -e "${RED}❌ Error: No parece ser el directorio del proyecto${NC}"
        exit 1
    fi
    
    echo -e "📂 Directorio: ${CYAN}$(pwd)${NC}"
    echo -e "👤 Usuario: ${CYAN}$USER${NC}"
    echo
    
    check_fotodescarga_components
    check_system_service
    check_directories_and_data
    check_processes
    generate_summary
    
    echo -e "${GREEN}✅ Verificación completada${NC}"
}

main "$@"
