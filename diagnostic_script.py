#!/usr/bin/env python3
"""
Script de diagnóstico para identificar problemas en el sistema principal
Compara lo que funciona vs lo que falla
"""

import sys
import os
import importlib.util
import traceback
from pathlib import Path

def print_section(title):
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print('='*60)

def test_basic_imports():
    """Prueba imports básicos que sabemos que funcionan"""
    print_section("IMPORTS BÁSICOS")
    
    basic_imports = [
        'serial',
        'threading', 
        'time',
        'os',
        'datetime',
        'picamera2'
    ]
    
    for module in basic_imports:
        try:
            if module == 'picamera2':
                from picamera2 import Picamera2
                print(f"✅ {module}: OK")
            elif module == 'datetime':
                from datetime import datetime
                print(f"✅ {module}: OK")
            else:
                __import__(module)
                print(f"✅ {module}: OK")
        except Exception as e:
            print(f"❌ {module}: {e}")

def check_file_structure():
    """Verifica la estructura de archivos del proyecto"""
    print_section("ESTRUCTURA DE ARCHIVOS")
    
    current_dir = Path.cwd()
    print(f"📁 Directorio actual: {current_dir}")
    
    # Archivos y directorios esperados
    expected_items = [
        'src/',
        'src/__init__.py',
        'src/config_manager.py',
        'src/camara_controller.py', 
        'src/uart_handler.py',
        'src/file_transfer.py',
        'src/exceptions.py',
        'scripts/',
        'scripts/main_daemon.py',
        'config/',
        'requirements.txt'
    ]
    
    for item in expected_items:
        path = current_dir / item
        if path.exists():
            print(f"✅ {item}")
        else:
            print(f"❌ {item} - NO ENCONTRADO")

def test_module_imports():
    """Prueba imports del sistema principal"""
    print_section("IMPORTS DEL SISTEMA PRINCIPAL")
    
    # Agregar src al path si existe
    src_path = Path.cwd() / 'src'
    if src_path.exists():
        sys.path.insert(0, str(src_path))
        print(f"📂 Agregado al path: {src_path}")
    
    modules_to_test = [
        'config_manager',
        'camara_controller', 
        'uart_handler',
        'file_transfer',
        'exceptions'
    ]
    
    for module_name in modules_to_test:
        try:
            module = importlib.import_module(module_name)
            print(f"✅ {module_name}: OK")
            
            # Verificar contenido básico
            if hasattr(module, '__all__'):
                print(f"   📋 Exports: {module.__all__}")
            
        except Exception as e:
            print(f"❌ {module_name}: {e}")
            print(f"   🔍 Error detallado:")
            traceback.print_exc()

def test_main_daemon():
    """Prueba el script principal main_daemon.py"""
    print_section("SCRIPT PRINCIPAL")
    
    main_daemon_path = Path.cwd() / 'scripts' / 'main_daemon.py'
    
    if not main_daemon_path.exists():
        print(f"❌ main_daemon.py no encontrado en: {main_daemon_path}")
        return
    
    print(f"📄 Archivo encontrado: {main_daemon_path}")
    
    try:
        # Intentar ejecutar como módulo
        spec = importlib.util.spec_from_file_location("main_daemon", main_daemon_path)
        if spec is None:
            print("❌ No se pudo crear spec del módulo")
            return
            
        main_daemon = importlib.util.module_from_spec(spec)
        
        print("✅ Módulo cargado correctamente")
        
        # Verificar funciones/clases principales
        if hasattr(main_daemon, '__all__'):
            print(f"📋 Exports: {main_daemon.__all__}")
        
        # Listar contenido del módulo
        module_contents = [item for item in dir(main_daemon) if not item.startswith('_')]
        print(f"📋 Contenido del módulo: {module_contents}")
        
    except Exception as e:
        print(f"❌ Error al cargar main_daemon: {e}")
        traceback.print_exc()

def check_config_files():
    """Verifica archivos de configuración"""
    print_section("ARCHIVOS DE CONFIGURACIÓN")
    
    config_files = [
        'config/camara.conf.example',
        'config/camara.conf', 
        'config/logging.conf'
    ]
    
    for config_file in config_files:
        path = Path.cwd() / config_file
        if path.exists():
            print(f"✅ {config_file}")
            try:
                content = path.read_text()
                lines = len(content.splitlines())
                print(f"   📄 Líneas: {lines}")
            except Exception as e:
                print(f"   ❌ Error leyendo: {e}")
        else:
            print(f"❌ {config_file} - NO ENCONTRADO")

def test_permissions():
    """Verifica permisos de archivos y directorios"""
    print_section("PERMISOS")
    
    import stat
    
    # Verificar permisos del directorio actual
    current_dir = Path.cwd()
    stat_info = current_dir.stat()
    permissions = stat.filemode(stat_info.st_mode)
    print(f"📁 Directorio actual: {permissions}")
    
    # Verificar archivos ejecutables
    executable_files = [
        'scripts/main_daemon.py',
        'scripts/cliente_foto.py',
        'scripts/install.sh'
    ]
    
    for file_path in executable_files:
        path = Path.cwd() / file_path
        if path.exists():
            stat_info = path.stat()
            permissions = stat.filemode(stat_info.st_mode)
            is_executable = stat_info.st_mode & stat.S_IEXEC
            print(f"{'✅' if is_executable else '⚠️ '} {file_path}: {permissions}")
        else:
            print(f"❌ {file_path}: NO ENCONTRADO")

def test_working_vs_broken():
    """Compara código que funciona vs el que no"""
    print_section("COMPARACIÓN CÓDIGO FUNCIONAL VS PROBLEMÁTICO")
    
    working_file = Path.cwd() / 'captura_foto.py'
    broken_system = Path.cwd() / 'scripts' / 'main_daemon.py'
    
    print("📸 Script que FUNCIONA:")
    if working_file.exists():
        print(f"✅ {working_file}")
        try:
            content = working_file.read_text()
            lines = content.splitlines()
            print(f"   📄 Líneas: {len(lines)}")
            
            # Buscar imports clave
            imports = [line for line in lines if line.startswith('import ') or line.startswith('from ')]
            print(f"   📦 Imports: {len(imports)}")
            for imp in imports[:5]:  # Mostrar primeros 5
                print(f"      {imp}")
                
        except Exception as e:
            print(f"   ❌ Error leyendo: {e}")
    else:
        print(f"❌ {working_file} no encontrado")
    
    print("\n🔧 Sistema que NO FUNCIONA:")
    if broken_system.exists():
        print(f"⚠️  {broken_system}")
        # Intentar identificar diferencias clave
        try:
            with open(broken_system, 'r') as f:
                content = f.read()
                lines = content.splitlines()
                print(f"   📄 Líneas: {len(lines)}")
                
                # Buscar imports problemáticos
                imports = [line for line in lines if line.startswith('import ') or line.startswith('from ')]
                print(f"   📦 Imports: {len(imports)}")
                
                # Identificar imports que podrían ser problemáticos
                problematic_patterns = ['config_manager', 'camara_controller', 'uart_handler']
                for pattern in problematic_patterns:
                    found = any(pattern in imp for imp in imports)
                    print(f"      {pattern}: {'ENCONTRADO' if found else 'No encontrado'}")
                    
        except Exception as e:
            print(f"   ❌ Error leyendo: {e}")
    else:
        print(f"❌ {broken_system} no encontrado")

def show_recommendations():
    """Muestra recomendaciones basadas en el diagnóstico"""
    print_section("RECOMENDACIONES")
    
    print("🎯 Pasos para solucionar:")
    print("1. ✅ Verificar que el código simple funciona (ya confirmado)")
    print("2. 🔍 Identificar diferencias entre código simple y complejo")
    print("3. 🔧 Crear versión incremental del sistema")
    print("4. 📦 Verificar estructura de imports")
    print("5. ⚙️  Simplificar configuración inicial")
    
    print("\n💡 Estrategias:")
    print("• Partir del código que funciona")
    print("• Agregar funcionalidades gradualmente") 
    print("• Verificar cada import antes de usarlo")
    print("• Usar rutas absolutas para imports")
    print("• Crear versión mínima del sistema completo")

def main():
    print("╔══════════════════════════════════════════════════════╗")
    print("║            🔍 DIAGNÓSTICO DEL SISTEMA                ║")
    print("║        Identificando por qué no funciona             ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    # Ejecutar todas las pruebas
    test_basic_imports()
    check_file_structure()
    test_module_imports()
    test_main_daemon()
    check_config_files()
    test_permissions()
    test_working_vs_broken()
    show_recommendations()
    
    print("\n🏁 Diagnóstico completado")
    print("💡 Revisa los resultados para identificar el problema específico")

if __name__ == "__main__":
    main()
