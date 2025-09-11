#!/bin/bash
# 🔧 Script de Reparación del Sistema de Cámara UART
# Arregla los problemas identificados en el diagnóstico

set -e

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║         🔧 REPARANDO SISTEMA CÁMARA UART            ║"
echo "║           Solucionando problemas detectados          ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Verificar que estamos en el directorio correcto
if [ ! -d "src" ] || [ ! -d "scripts" ]; then
    log_error "Ejecutar desde el directorio sistema-camara-uart"
    log_info "cd /home/pi/foto/sistema-camara-uart"
    exit 1
fi

log_info "Directorio actual: $(pwd)"

# 1. Crear __init__.py faltante
log_info "Creando src/__init__.py..."
cat > src/__init__.py << 'EOF'
"""
Sistema de Cámara UART - Paquete Principal
Control remoto de cámara Raspberry Pi por UART
"""

__version__ = "1.0.0"
__author__ = "Sistema Cámara UART"

# Importaciones principales disponibles
try:
    from .config_manager import ConfigManager
    from .camara_controller import CamaraController
    from .uart_handler import UARTHandler
    from .file_transfer import FileTransfer
    from .exceptions import *
    
    __all__ = [
        'ConfigManager',
        'CamaraController', 
        'UARTHandler',
        'FileTransfer'
    ]
    
    print("📦 Módulos del sistema cargados correctamente")
    
except ImportError as e:
    print(f"⚠️  Advertencia import: {e}")
    # Continúar sin fallar
    pass
EOF

log_success "src/__init__.py creado"

# 2. Arreglar permisos de ejecución
log_info "Arreglando permisos de archivos..."

chmod +x scripts/main_daemon.py
chmod +x scripts/cliente_foto.py
chmod +x scripts/install.sh 
chmod +x scripts/uninstall.sh 2>/dev/null || true

log_success "Permisos de ejecución establecidos"

# 3. Crear archivo de configuración logging si no existe
log_info "Verificando configuración de logging..."
if [ ! -f "config/logging.conf" ]; then
    cat > config/logging.conf << 'EOF'
[loggers]
keys=root,camara_uart_daemon

[handlers]
keys=consoleHandler,fileHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=INFO
handlers=consoleHandler

[logger_camara_uart_daemon]
level=INFO
handlers=consoleHandler,fileHandler
qualname=camara_uart_daemon
propagate=0

[handler_consoleHandler]
class=StreamHandler
level=INFO
formatter=simpleFormatter
args=(sys.stdout,)

[handler_fileHandler]
class=FileHandler
level=INFO
formatter=simpleFormatter
args=('logs/camara-uart.log',)

[formatter_simpleFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
EOF
    log_success "config/logging.conf creado"
else
    log_info "config/logging.conf ya existe"
fi

# 4. Crear directorio de logs si no existe
mkdir -p logs
touch logs/camara-uart.log
chmod 666 logs/camara-uart.log

# 5. Verificar y crear directorios necesarios
log_info "Verificando estructura de directorios..."
mkdir -p data/fotos
mkdir -p data/temp
mkdir -p tests

# 6. Probar imports del sistema
log_info "Probando imports del sistema reparado..."

python3 << 'EOF'
import sys
import os

# Agregar src al path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

try:
    # Probar imports básicos
    import config_manager
    print("✅ config_manager importado")
    
    import camara_controller  
    print("✅ camara_controller importado")
    
    import uart_handler
    print("✅ uart_handler importado")
    
    import file_transfer
    print("✅ file_transfer importado")
    
    import exceptions
    print("✅ exceptions importado")
    
    print("🎉 Todos los módulos se importan correctamente")
    
except ImportError as e:
    print(f"❌ Error de import: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    log_success "Imports del sistema funcionando"
else
    log_error "Problema con imports - revisar código de módulos"
    exit 1
fi

# 7. Probar ejecución del daemon en modo test
log_info "Probando daemon en modo test..."

# Crear script de prueba que no requiera hardware
cat > test_daemon_imports.py << 'EOF'
#!/usr/bin/env python3
"""
Prueba de imports del daemon sin inicializar hardware
"""

import sys
import os

# Agregar src al path  
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

try:
    # Importar módulos del daemon
    from config_manager import ConfigManager
    from camara_controller import CamaraController
    from uart_handler import UARTHandler
    
    print("✅ Imports del daemon OK")
    
    # Crear instancias básicas (sin hardware)
    config = ConfigManager("config/camara.conf")
    print("✅ ConfigManager creado")
    
    print("🎉 Sistema listo para uso")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

python3 test_daemon_imports.py

if [ $? -eq 0 ]; then
    log_success "Daemon puede importar módulos correctamente"
    rm test_daemon_imports.py
else
    log_error "Problema con daemon - revisar main_daemon.py"
    exit 1
fi

# 8. Crear script de inicio mejorado
log_info "Creando script de inicio mejorado..."
cat > start_camera_uart.sh << 'EOF'
#!/bin/bash
# Script de inicio del sistema de cámara UART

echo "🚀 Iniciando Sistema de Cámara UART..."

# Verificar que estamos en el directorio correcto
if [ ! -f "scripts/main_daemon.py" ]; then
    echo "❌ Error: Ejecutar desde directorio sistema-camara-uart"
    exit 1
fi

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    echo "🐍 Activando entorno virtual..."
    source venv/bin/activate
fi

# Exportar PYTHONPATH para imports
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"

# Ejecutar daemon
echo "📡 Iniciando daemon principal..."
python3 scripts/main_daemon.py "$@"
EOF

chmod +x start_camera_uart.sh
log_success "Script de inicio creado: ./start_camera_uart.sh"

# 9. Crear script de prueba completa
cat > test_system.sh << 'EOF'
#!/bin/bash
# Prueba completa del sistema

echo "🧪 Ejecutando pruebas del sistema..."

# Activar entorno virtual
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Configurar path
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"

# Ejecutar daemon en modo test
echo "📋 Probando daemon en modo test..."
python3 scripts/main_daemon.py --test

echo "✅ Pruebas completadas"
EOF

chmod +x test_system.sh
log_success "Script de prueba creado: ./test_system.sh"

# 10. Mostrar resultado final
echo ""
log_success "🎉 Sistema reparado exitosamente"

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║                   ✅ SISTEMA LISTO                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}📋 Comandos disponibles:${NC}"
echo -e "${GREEN}•${NC} ${BLUE}./start_camera_uart.sh${NC} - Iniciar sistema"
echo -e "${GREEN}•${NC} ${BLUE}./test_system.sh${NC} - Ejecutar pruebas"
echo -e "${GREEN}•${NC} ${BLUE}python3 scripts/main_daemon.py --test${NC} - Modo test"
echo -e "${GREEN}•${NC} ${BLUE}python diagnostic_script.py${NC} - Ejecutar diagnóstico"

echo ""
echo -e "${YELLOW}🔧 Problemas solucionados:${NC}"
echo -e "${GREEN}✅${NC} src/__init__.py creado"
echo -e "${GREEN}✅${NC} Permisos de ejecución arreglados"  
echo -e "${GREEN}✅${NC} Imports del sistema funcionando"
echo -e "${GREEN}✅${NC} Configuración de logging creada"
echo -e "${GREEN}✅${NC} Scripts de inicio y prueba creados"

echo ""
echo -e "${BLUE}🚀 Próximo paso: ${YELLOW}./test_system.sh${NC}"
