#!/bin/bash
# Script de prueba del cliente UART

echo "🧪 Iniciando cliente de pruebas..."

# Activar entorno virtual
source "/home/pi/foto/sistema-camara-uart/venv/bin/activate"

# Ejecutar cliente
python3 "/home/pi/foto/sistema-camara-uart/scripts/cliente_foto.py" "$@"
