#!/bin/bash
# Script para verificar estado del servicio

echo "📊 Estado del servicio camara-uart:"
echo "============================================"

# Estado del servicio
sudo systemctl status "camara-uart" --no-pager

echo ""
echo "📈 Últimas líneas del log:"
echo "============================================"
sudo journalctl -u "camara-uart" -n 10 --no-pager

echo ""
echo "🔧 Comandos útiles:"
echo "  sudo systemctl start camara-uart      # Iniciar servicio"
echo "  sudo systemctl stop camara-uart       # Detener servicio"
echo "  sudo systemctl restart camara-uart    # Reiniciar servicio"
echo "  sudo journalctl -u camara-uart -f     # Ver logs en tiempo real"
