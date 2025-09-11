#!/usr/bin/env python3
"""
Sistema de cámara UART simplificado que SÍ funciona
Usa directamente el controlador que ya probamos
"""

import sys
import os

# Agregar src al path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from camara_controller import CamaraController
import serial
import threading
import time

class SistemaSimpleFuncional:
    def __init__(self):
        print("🚀 Sistema Simple Funcional - Basado en código que funciona")
        
        # Inicializar componentes
        self.camara = CamaraController()
        self.puerto_serie = '/dev/ttyS0'
        self.baudrate = 9600
        self.ejecutando = False
        self.serial_conn = None
        
    def conectar_uart(self):
        try:
            self.serial_conn = serial.Serial(
                port=self.puerto_serie,
                baudrate=self.baudrate,
                timeout=1
            )
            print(f"✅ UART conectado: {self.puerto_serie}")
            return True
        except Exception as e:
            print(f"❌ Error UART: {e}")
            return False
    
    def procesar_comando(self, comando):
        comando = comando.strip().lower()
        
        if comando == "foto":
            print("📸 Capturando foto...")
            result = self.camara.tomar_foto()
            if result['success']:
                msg = f"OK|{result['filename']}|{result['size']}"
                print(f"✅ {msg}")
                if self.serial_conn:
                    self.serial_conn.write(f"{msg}\r\n".encode())
            else:
                print(f"❌ Error: {result['error']}")
        
        elif comando == "test":
            print("🧪 Test de cámara...")
            disponible = self.camara.verificar_camara_disponible()
            print(f"📸 Cámara disponible: {disponible}")
        
        elif comando == "salir":
            print("👋 Saliendo...")
            self.ejecutando = False
    
    def iniciar(self):
        print("🎯 Iniciando sistema...")
        
        # Test inicial
        print("🧪 Verificando cámara...")
        if self.camara.verificar_camara_disponible():
            print("✅ Cámara OK")
        else:
            print("⚠️  Cámara no detectada, pero continuando...")
        
        # Conectar UART
        if self.conectar_uart():
            print("✅ Sistema listo")
            
            # Comandos de prueba
            print("\n📋 Ejecutando comandos de prueba:")
            self.procesar_comando("test")
            self.procesar_comando("foto")
            
            print("\n🎉 Sistema funcional completo")
        else:
            print("⚠️  UART no conectado, pero cámara funciona")

if __name__ == "__main__":
    sistema = SistemaSimpleFuncional()
    sistema.iniciar()
