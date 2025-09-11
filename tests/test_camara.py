#!/usr/bin/env python3
"""
Test específico para el controlador de cámara
"""

import sys
import os

# Agregar src al path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

def test_controller():
    """Prueba el controlador de cámara"""
    print("🧪 Probando CamaraController...")
    
    try:
        from camara_controller import CamaraController
        
        # Crear instancia
        controller = CamaraController()
        print("✅ Controlador creado")
        
        # Verificar cámara
        disponible = controller.verificar_camara_disponible()
        print(f"📸 Cámara disponible: {disponible}")
        
        # Cambiar resolución
        resultado = controller.cambiar_resolucion("640x480")
        print(f"🔧 Cambio resolución: {resultado}")
        
        # Obtener info
        info = controller.obtener_info_camara()
        print(f"ℹ️  Info cámara: {info}")
        
        # Listar fotos
        fotos = controller.listar_fotos_recientes(3)
        print(f"📁 Fotos recientes: {len(fotos)}")
        
        print("🎉 Todas las pruebas del controlador exitosas")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if test_controller():
        print("✅ Test exitoso")
    else:
        print("❌ Test falló")
        sys.exit(1)
