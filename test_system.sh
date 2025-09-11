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
