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
