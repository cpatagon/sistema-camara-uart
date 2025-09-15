#!/bin/bash
# Script de inicio rápido simple para Sistema de Cámara UART

echo "🚀 Iniciando Sistema de Cámara UART..."

# Detectar directorio del proyecto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activar entorno virtual si existe
if [[ -d "$PROJECT_DIR/venv" ]]; then
    echo "🐍 Activando entorno virtual..."
    source "$PROJECT_DIR/venv/bin/activate"
else
    echo "⚠️  Entorno virtual no encontrado - usando Python del sistema"
fi

# Verificar configuración
if [[ ! -f "$PROJECT_DIR/config/camara.conf" ]]; then
    if [[ -f "$PROJECT_DIR/config/camara.conf.example" ]]; then
        echo "📝 Creando configuración desde plantilla..."
        cp "$PROJECT_DIR/config/camara.conf.example" "$PROJECT_DIR/config/camara.conf"
    else
        echo "❌ Archivo de configuración no encontrado"
        echo "💡 Ejecutar primero: ./install.sh"
        exit 1
    fi
fi

# Configurar Python path
export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"

# Crear directorios necesarios
mkdir -p "$PROJECT_DIR/data/fotos" "$PROJECT_DIR/data/temp" "$PROJECT_DIR/logs"

echo "✅ Configuración verificada"
echo "📡 Iniciando daemon principal..."
echo "💡 Para detener: Ctrl+C"
echo

# Iniciar sistema
cd "$PROJECT_DIR"
python3 scripts/main_daemon.py "$@"
