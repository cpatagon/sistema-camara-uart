#!/usr/bin/env python3
"""
Script de prueba para comandos FotoDescarga
"""

import time
import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path.cwd() / 'src'))

def test_comandos():
    """Prueba los comandos por cliente"""
    try:
        from cliente_foto import ClienteUARTLimpio
        
        cliente = ClienteUARTLimpio()
        if not cliente.conectar():
            print("❌ No se pudo conectar")
            return
        
        # Comandos de prueba
        comandos_test = [
            "resoluciones",           # Ver opciones disponibles
            "fotopreset:vga:test",   # Foto VGA rápida
            "fotosize:1280x720:hd",  # Foto HD específica
            "fotoinmediata",         # Foto temporal
        ]
        
        for cmd in comandos_test:
            print(f"\n🧪 Probando: {cmd}")
            cliente.enviar_comando(cmd)
            time.sleep(3)
        
        cliente.desconectar()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_comandos()
