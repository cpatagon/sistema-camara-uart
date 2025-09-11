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
