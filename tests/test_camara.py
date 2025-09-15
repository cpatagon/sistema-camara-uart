#!/usr/bin/env python3
"""
Test específico para el controlador de cámara
Actualizado para compatibilidad con rpicam-apps y libcamera-apps
"""

import sys
import os
import subprocess
import time

# Agregar src al path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

def print_header(title):
    """Imprime encabezado de sección"""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print('='*60)

def print_success(msg):
    """Imprime mensaje de éxito"""
    print(f"✅ {msg}")

def print_warning(msg):
    """Imprime mensaje de advertencia"""
    print(f"⚠️  {msg}")

def print_error(msg):
    """Imprime mensaje de error"""
    print(f"❌ {msg}")

def print_info(msg):
    """Imprime mensaje informativo"""
    print(f"ℹ️  {msg}")

def test_camera_commands():
    """Prueba la disponibilidad de comandos de cámara"""
    print_header("VERIFICACIÓN DE COMANDOS DE CÁMARA")
    
    # Comandos a verificar
    commands_to_test = [
        ("rpicam-still", "Raspberry Pi OS Bookworm+"),
        ("rpicam-vid", "Video Bookworm+"),
        ("rpicam-hello", "Test Bookworm+"),
        ("rpicam-jpeg", "JPEG Bookworm+"),
        ("libcamera-still", "Versiones anteriores"),
        ("libcamera-vid", "Video anteriores"),
        ("libcamera-hello", "Test anteriores"),
        ("libcamera-jpeg", "JPEG anteriores")
    ]
    
    available_commands = []
    
    for cmd, description in commands_to_test:
        try:
            # Verificar si el comando existe
            result = subprocess.run([cmd, '--help'], 
                                  capture_output=True, 
                                  timeout=5)
            if result.returncode == 0 or 'usage' in result.stderr.decode().lower():
                print_success(f"{cmd} - {description}")
                available_commands.append(cmd)
            else:
                print_warning(f"{cmd} - No disponible")
        except FileNotFoundError:
            print_warning(f"{cmd} - No encontrado")
        except subprocess.TimeoutExpired:
            print_error(f"{cmd} - Timeout")
        except Exception as e:
            print_error(f"{cmd} - Error: {e}")
    
    if available_commands:
        print_info(f"Comandos disponibles: {', '.join(available_commands)}")
        return available_commands
    else:
        print_warning("No se encontraron comandos de cámara del sistema")
        return []

def test_camera_hardware():
    """Prueba el hardware de la cámara"""
    print_header("VERIFICACIÓN DE HARDWARE DE CÁMARA")
    
    # Test 1: vcgencmd
    try:
        result = subprocess.run(['vcgencmd', 'get_camera'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            output = result.stdout.strip()
            print_info(f"vcgencmd get_camera: {output}")
            
            if 'supported=1' in output and 'detected=1' in output:
                print_success("Cámara detectada por vcgencmd")
                return True
            else:
                print_warning("Cámara no detectada por vcgencmd")
        else:
            print_warning("vcgencmd no disponible")
    except Exception as e:
        print_warning(f"Error con vcgencmd: {e}")
    
    # Test 2: Comando hello disponible
    hello_commands = ['rpicam-hello', 'libcamera-hello']
    
    for cmd in hello_commands:
        try:
            print_info(f"Probando {cmd}...")
            
            # Usar sintaxis correcta según el comando
            if cmd == 'rpicam-hello':
                # Sintaxis rpicam-hello: -t en milisegundos
                result = subprocess.run([
                    cmd, 
                    '-t', '100'  # 100ms timeout
                ], capture_output=True, timeout=10)
            else:
                # Sintaxis libcamera-hello: --timeout en milisegundos
                result = subprocess.run([
                    cmd, 
                    '--timeout', '100'  # 100ms timeout
                ], capture_output=True, timeout=10)
            
            if result.returncode == 0:
                print_success(f"Cámara responde correctamente a {cmd}")
                return True
            else:
                error_output = result.stderr.decode() if result.stderr else "Sin error específico"
                print_warning(f"{cmd} falló: {error_output}")
                
        except FileNotFoundError:
            print_info(f"{cmd} no disponible")
        except subprocess.TimeoutExpired:
            print_warning(f"{cmd} timeout - posible problema de cámara")
        except Exception as e:
            print_error(f"Error con {cmd}: {e}")
    
    return False

def test_picamera2():
    """Prueba la disponibilidad de picamera2"""
    print_header("VERIFICACIÓN DE PICAMERA2")
    
    try:
        from picamera2 import Picamera2
        print_success("picamera2 importado correctamente")
        
        # Test básico de inicialización
        try:
            picam2 = Picamera2()
            print_success("Picamera2 inicializado")
            
            # Cerrar inmediatamente
            picam2.close()
            print_success("Picamera2 cerrado correctamente")
            return True
            
        except Exception as e:
            print_error(f"Error inicializando Picamera2: {e}")
            return False
            
    except ImportError as e:
        print_warning(f"picamera2 no disponible: {e}")
        return False

def test_controller():
    """Prueba el controlador de cámara actualizado"""
    print_header("PRUEBA DEL CONTROLADOR DE CÁMARA")
    
    try:
        from camara_controller import CamaraController
        print_success("CamaraController importado correctamente")
        
        # Crear instancia
        controller = CamaraController()
        print_success("Controlador creado")
        
        # Obtener información del sistema
        print_info("Obteniendo información del sistema de cámara...")
        info_sistema = controller.obtener_info_sistema_camara()
        
        print_info(f"Método de captura: {info_sistema['metodo_captura']}")
        print_info(f"Comando activo: {info_sistema['comando_activo']}")
        print_info(f"picamera2 disponible: {info_sistema['picamera2_disponible']}")
        
        print_info("Comandos disponibles:")
        for cmd, disponible in info_sistema['comandos_disponibles'].items():
            status = "✅" if disponible else "❌"
            print(f"   {status} {cmd}")
        
        # Verificar cámara
        print_info("Verificando disponibilidad de cámara...")
        disponible = controller.verificar_camara_disponible()
        if disponible:
            print_success("Cámara disponible y funcional")
        else:
            print_warning("Cámara no disponible o con problemas")
        
        # Obtener información de resolución
        print_info("Obteniendo información de resolución...")
        info_res = controller.obtener_info_resolucion_actual()
        print_info(f"Resolución actual: {info_res['ancho']}x{info_res['alto']}")
        print_info(f"Megapíxeles: {info_res['megapixeles']}")
        print_info(f"Formato: {info_res['formato']}")
        print_info(f"Método: {info_res['metodo_captura']}")
        print_info(f"Comando: {info_res['comando_usado']}")
        
        # Test de cambio de resolución
        print_info("Probando cambio de resolución...")
        resultado = controller.cambiar_resolucion(640, 480)
        if resultado:
            print_success("Cambio de resolución exitoso")
        else:
            print_warning("Error en cambio de resolución")
        
        # Listar fotos existentes
        print_info("Listando fotos existentes...")
        fotos = controller.listar_archivos()
        print_info(f"Fotos encontradas: {len(fotos)}")
        
        # Test de captura (solo si la cámara está disponible)
        if disponible:
            print_info("Realizando test de captura...")
            resultado_test = controller.realizar_captura_test()
            
            if resultado_test['exito']:
                print_success(f"Captura test exitosa:")
                print_info(f"  • Tiempo: {resultado_test['tiempo_captura']:.2f}s")
                print_info(f"  • Método: {resultado_test['metodo_usado']}")
                print_info(f"  • Comando: {resultado_test['comando_usado']}")
                print_info(f"  • Archivo: {resultado_test['archivo']}")
                print_info(f"  • Tamaño: {resultado_test['tamaño']:,} bytes")
                if 'resolucion' in resultado_test:
                    print_info(f"  • Resolución: {resultado_test['resolucion']}")
            else:
                print_error(f"Error en captura test: {resultado_test['error']}")
        else:
            print_warning("Saltando test de captura (cámara no disponible)")
        
        # Estado completo del sistema
        print_info("Obteniendo estado completo del sistema...")
        estado = controller.obtener_estado_sistema()
        
        print_info("Estado del sistema:")
        print_info(f"  • Estado cámara: {estado['estado_camara']}")
        print_info(f"  • Método captura: {estado['metodo_captura']}")
        print_info(f"  • Comando activo: {estado['comando_activo']}")
        print_info(f"  • Capturas realizadas: {estado['estadisticas']['capturas_realizadas']}")
        print_info(f"  • Total archivos: {estado['archivos']['total_archivos']}")
        
        print_success("Todas las pruebas del controlador completadas")
        return True
        
    except Exception as e:
        print_error(f"Error en pruebas del controlador: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_compatibility_aliases():
    """Prueba los alias de compatibilidad"""
    print_header("VERIFICACIÓN DE ALIAS DE COMPATIBILIDAD")
    
    alias_pairs = [
        ("rpicam-still", "libcamera-still"),
        ("rpicam-vid", "libcamera-vid"),
        ("rpicam-hello", "libcamera-hello"),
        ("rpicam-jpeg", "libcamera-jpeg")
    ]
    
    compatibility_ok = True
    
    for new_cmd, old_cmd in alias_pairs:
        new_available = subprocess.run(['which', new_cmd], 
                                     capture_output=True).returncode == 0
        old_available = subprocess.run(['which', old_cmd], 
                                     capture_output=True).returncode == 0
        
        if new_available and old_available:
            print_success(f"Ambos disponibles: {new_cmd} y {old_cmd}")
        elif new_available and not old_available:
            print_warning(f"Solo {new_cmd} disponible, falta alias {old_cmd}")
            compatibility_ok = False
        elif not new_available and old_available:
            print_warning(f"Solo {old_cmd} disponible, falta alias {new_cmd}")
            compatibility_ok = False
        else:
            print_info(f"Ninguno disponible: {new_cmd}, {old_cmd}")
    
    if compatibility_ok:
        print_success("Compatibilidad de alias OK")
    else:
        print_warning("Algunos alias de compatibilidad faltantes")
        print_info("Ejecutar: sudo python3 -c 'from camara_controller import crear_alias_compatibilidad; crear_alias_compatibilidad()'")
    
    return compatibility_ok

def generate_compatibility_report():
    """Genera un reporte completo de compatibilidad"""
    print_header("REPORTE DE COMPATIBILIDAD COMPLETO")
    
    # Información del sistema
    try:
        with open('/etc/os-release', 'r') as f:
            os_info = f.read()
        
        if 'bookworm' in os_info.lower():
            os_version = "Raspberry Pi OS Bookworm (2023+)"
            expected_commands = ["rpicam-still", "rpicam-vid", "rpicam-hello"]
        elif 'bullseye' in os_info.lower():
            os_version = "Raspberry Pi OS Bullseye (2021-2023)"
            expected_commands = ["libcamera-still", "libcamera-vid", "libcamera-hello"]
        elif 'buster' in os_info.lower():
            os_version = "Raspberry Pi OS Buster (2019-2021)"
            expected_commands = ["picamera2 only"]
        else:
            os_version = "Versión desconocida"
            expected_commands = []
        
        print_info(f"Sistema operativo: {os_version}")
        print_info(f"Comandos esperados: {', '.join(expected_commands)}")
        
    except Exception as e:
        print_warning(f"No se pudo determinar la versión del OS: {e}")
    
    # Resumen de tests
    results = {
        'comandos_sistema': len(test_camera_commands()) > 0,
        'hardware_camara': test_camera_hardware(),
        'picamera2': test_picamera2(),
        'controlador': test_controller(),
        'compatibilidad': test_compatibility_aliases()
    }
    
    print_header("RESUMEN DE RESULTADOS")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name.replace('_', ' ').title()}")
    
    print(f"\nResultado final: {passed_tests}/{total_tests} tests pasaron")
    
    if passed_tests == total_tests:
        print_success("🎉 Todas las pruebas completadas exitosamente")
        print_info("El sistema es totalmente compatible y funcional")
    elif passed_tests >= total_tests - 1:
        print_warning("⚠️  Sistema mayormente funcional con limitaciones menores")
    else:
        print_error("❌ Sistema con problemas significativos")
        print_info("Revisar los errores anteriores y:")
        print_info("  • Verificar conexión física de la cámara")
        print_info("  • Ejecutar raspi-config para habilitar cámara")
        print_info("  • Instalar paquetes faltantes")
        print_info("  • Reiniciar el sistema")
    
    return passed_tests >= total_tests - 1

def main():
    """Función principal del test"""
    print("🚀 Sistema de Cámara UART - Test de Compatibilidad")
    print("Compatible con rpicam-apps (Bookworm+) y libcamera-apps (anteriores)")
    
    try:
        success = generate_compatibility_report()
        
        if success:
            print_success("\n🎯 Sistema listo para usar")
            print_info("Comandos disponibles:")
            print_info("  python3 scripts/main_daemon.py --test")
            print_info("  python3 scripts/cliente_foto.py")
            print_info("  ./scripts/inicio_rapido.sh")
            return 0
        else:
            print_error("\n⚠️  Sistema necesita configuración adicional")
            return 1
            
    except KeyboardInterrupt:
        print_warning("\n🛑 Test interrumpido por usuario")
        return 1
    except Exception as e:
        print_error(f"\n💥 Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
