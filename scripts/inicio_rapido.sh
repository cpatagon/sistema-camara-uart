#!/bin/bash
# Script de inicio rápido para Sistema de Cámara UART

echo "🚀 Iniciando Sistema de Cámara UART..."

# Activar entorno virtual
source "/home/pi/foto/sistema-camara-uart/venv/bin/activate"

# Verificar configuración
if [ ! -f "/home/pi/foto/sistema-camara-uart/config/camara.conf" ]; then
    echo "❌ Archivo de configuración no encontrado"
    echo "💡 Ejecutar: cp config/camara.conf.example config/camara.conf"
    exit 1
fi

# Iniciar sistema
python3 "/home/pi/foto/sistema-camara-uart/scripts/main_daemon.py" "$@"
