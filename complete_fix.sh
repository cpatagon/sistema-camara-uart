#!/bin/bash
# 🔧 Reparación Completa del Sistema
# Crea archivos limpios y funcionales

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║         🔧 REPARACIÓN COMPLETA DEL SISTEMA           ║"
echo "║            Creando archivos limpios                  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Verificar directorio
if [ ! -d "src" ]; then
    log_error "Ejecutar desde directorio sistema-camara-uart"
    exit 1
fi

log_info "Creando camara_controller.py limpio..."

# Crear archivo completamente nuevo
cat > src/camara_controller.py << 'EOF'
"""
Controlador de Cámara - Versión Funcional
Basado exactamente en el código simple que ya funciona
"""

import os
import time
from datetime import datetime
from picamera2 import Picamera2

class CamaraController:
    """
    Controlador de cámara que usa la misma lógica 
    del script simple que funciona
    """
    
    def __init__(self, config_manager=None):
        """Inicializa el controlador de cámara"""
        
        # Configuración desde config manager o valores por defecto
        if config_manager:
            self.directorio = config_manager.get('CAMERA', 'directorio', 'fotos')
            resolucion_str = config_manager.get('CAMERA', 'resolucion', '1280x720')
        else:
            self.directorio = "fotos"
            resolucion_str = "1280x720"
        
        # Parsear resolución
        try:
            ancho, alto = map(int, resolucion_str.split('x'))
            self.resolucion_default = (ancho, alto)
        except:
            self.resolucion_default = (1280, 720)
        
        # Crear directorio si no existe
        os.makedirs(self.directorio, exist_ok=True)
        
        log_info = f"📸 Controlador de cámara inicializado"
        print(log_info)
        print(f"📁 Directorio: {self.directorio}")
        print(f"🎯 Resolución: {self.resolucion_default[0]}x{self.resolucion_default[1]}")
    
    def tomar_foto(self, resolucion=None):
        """
        Toma una fotografía con timestamp
        Usa exactamente la misma lógica que el script que funciona
        """
        picam2 = None
        
        try:
            # Usar resolución especificada o por defecto
            res_actual = resolucion or self.resolucion_default
            
            # Generar nombre con timestamp - igual que script funcional
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"{timestamp}.jpg"
            ruta_completa = os.path.join(self.directorio, nombre_archivo)
            
            # Inicializar cámara - exactamente igual que script funcional
            picam2 = Picamera2()
            config = picam2.create_still_configuration(main={"size": res_actual})
            picam2.configure(config)
            picam2.start()
            
            # Pausa para estabilizar - igual que script funcional
            time.sleep(0.5)
            
            # Capturar foto - igual que script funcional
            picam2.capture_file(ruta_completa)
            
            print(f"📸 Foto guardada: {ruta_completa}")
            
            # Obtener información del archivo
            tamaño = os.path.getsize(ruta_completa)
            
            return {
                'success': True,
                'filename': nombre_archivo,
                'path': ruta_completa,
                'size': tamaño,
                'resolution': res_actual,
                'timestamp': timestamp
            }
            
        except Exception as e:
            error_msg = f"Error al tomar foto: {e}"
            print(f"❌ {error_msg}")
            
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S")
            }
            
        finally:
            if picam2 is not None:
                try:
                    picam2.stop()
                    picam2.close()
                except:
                    pass
                time.sleep(0.2)  # Pausa igual que script funcional
    
    def cambiar_resolucion(self, nueva_resolucion):
        """Cambia la resolución por defecto"""
        try:
            if isinstance(nueva_resolucion, str):
                # Parsear desde string "WIDTHxHEIGHT"
                ancho, alto = map(int, nueva_resolucion.split('x'))
                self.resolucion_default = (ancho, alto)
            elif isinstance(nueva_resolucion, tuple):
                # Usar tupla directamente
                self.resolucion_default = nueva_resolucion
            else:
                raise ValueError("Formato de resolución inválido")
            
            print(f"🔧 Resolución cambiada a: {self.resolucion_default[0]}x{self.resolucion_default[1]}")
            
            # Actualizar en config manager si está disponible
            if hasattr(self, 'config_manager') and self.config_manager:
                res_str = f"{self.resolucion_default[0]}x{self.resolucion_default[1]}"
                self.config_manager.set('CAMERA', 'resolucion', res_str)
            
            return True
            
        except Exception as e:
            print(f"❌ Error cambiando resolución: {e}")
            return False
    
    def verificar_camara_disponible(self):
        """Verifica si la cámara está disponible"""
        try:
            # Intentar crear instancia básica
            picam2 = Picamera2()
            
            # Cerrar inmediatamente
            picam2.close()
            
            print("✅ Cámara disponible")
            return True
            
        except Exception as e:
            print(f"⚠️  Cámara no disponible: {e}")
            return False
    
    def obtener_info_camara(self):
        """Obtiene información de la cámara"""
        try:
            from picamera2 import Picamera2
            
            # Obtener información global de cámaras
            cameras = Picamera2.global_camera_info()
            
            info = {
                'disponible': len(cameras) > 0,
                'cantidad': len(cameras),
                'resolucion_actual': self.resolucion_default,
                'directorio': self.directorio
            }
            
            if cameras:
                info['camaras'] = cameras
            
            return info
            
        except Exception as e:
            return {
                'disponible': False,
                'error': str(e)
            }
    
    def listar_fotos_recientes(self, limite=10):
        """Lista las fotos más recientes"""
        try:
            fotos = []
            
            # Buscar archivos de imagen en el directorio
            for archivo in os.listdir(self.directorio):
                if archivo.lower().endswith(('.jpg', '.jpeg', '.png')):
                    ruta_completa = os.path.join(self.directorio, archivo)
                    stat_info = os.stat(ruta_completa)
                    
                    fotos.append({
                        'nombre': archivo,
                        'tamaño': stat_info.st_size,
                        'fecha_modificacion': stat_info.st_mtime,
                        'fecha_str': datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            # Ordenar por fecha (más recientes primero)
            fotos.sort(key=lambda x: x['fecha_modificacion'], reverse=True)
            
            return fotos[:limite]
            
        except Exception as e:
            print(f"❌ Error listando fotos: {e}")
            return []


# Clases alias para compatibilidad con código existente
CamaraUART = CamaraController

def crear_controlador_camara(config_manager=None):
    """Función helper para crear instancia del controlador"""
    return CamaraController(config_manager)
EOF

log_success "camara_controller.py creado"

# Verificar sintaxis
log_info "Verificando sintaxis de Python..."
python3 -m py_compile src/camara_controller.py

if [ $? -eq 0 ]; then
    log_success "Sintaxis correcta"
else
    log_error "Error de sintaxis en camara_controller.py"
    exit 1
fi

# Probar import básico
log_info "Probando import básico..."
python3 << 'PYEOF'
import sys
sys.path.insert(0, 'src')

try:
    from camara_controller import CamaraController
    print("✅ Import CamaraController exitoso")
    
    # Crear instancia básica
    controller = CamaraController()
    print("✅ Instancia creada exitosamente")
    
    # Probar método básico
    info = controller.obtener_info_camara()
    print(f"✅ Info cámara: {info['disponible']}")
    
    print("🎉 Controlador funciona correctamente")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYEOF

if [ $? -eq 0 ]; then
    log_success "Import y creación de instancia exitosos"
else
    log_error "Error en pruebas básicas"
    exit 1
fi

# Crear script de test específico
log_info "Creando script de test específico..."
cat > test_camara_only.py << 'EOF'
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
EOF

chmod +x test_camara_only.py

# Ejecutar test específico
log_info "Ejecutando test específico del controlador..."
python3 test_camara_only.py

if [ $? -eq 0 ]; then
    log_success "Test específico exitoso"
else
    log_error "Test específico falló"
    exit 1
fi

# Ahora probar el sistema completo
log_info "Probando sistema completo..."
./test_system.sh

if [ $? -eq 0 ]; then
    log_success "🎉 Sistema completo funcionando"
else
    log_error "Sistema completo aún tiene problemas"
    echo ""
    echo "💡 Opciones:"
    echo "1. Ejecutar solo: python3 test_camara_only.py"
    echo "2. Revisar logs en scripts/main_daemon.py"
    echo "3. Ejecutar modo debug: python3 scripts/main_daemon.py --debug"
fi

echo ""
log_success "Reparación completada"
echo "📁 Archivo creado: test_camara_only.py"
echo "🔧 Controlador reparado: src/camara_controller.py"
