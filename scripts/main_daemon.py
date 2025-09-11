#!/usr/bin/env python3
"""
Daemon principal del sistema de cámara UART.

Este script integra todos los módulos del sistema para proporcionar
un servicio completo de captura y transferencia de fotos por UART.
"""

import sys
import os
import signal
import time
import threading
import logging
import argparse
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import traceback

# Agregar directorio src al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from config_manager import ConfigManager
    from camara_controller import CamaraController
    from uart_handler import UARTHandler
    from file_transfer import FileTransferManager
    from exceptions import (
        CamaraUARTError,
        UARTError,
        CamaraError,
        FileTransferError,
        ConfigError
    )
except ImportError as e:
    print(f"Error importando módulos: {e}")
    print("Asegúrate de que el directorio src esté configurado correctamente")
    sys.exit(1)


class SistemaCamaraUART:
    """
    Sistema principal de cámara UART.
    
    Integra todos los componentes y maneja el ciclo de vida completo.
    """
    
    def __init__(self, archivo_config: str = "config/camara.conf"):
        """
        Inicializa el sistema completo.
        
        Args:
            archivo_config: Ruta al archivo de configuración
        """
        self.archivo_config = archivo_config
        self.ejecutando = False
        self.logger = self._configurar_logging()
        
        # Componentes principales
        self.config_manager: Optional[ConfigManager] = None
        self.camara_controller: Optional[CamaraController] = None
        self.uart_handler: Optional[UARTHandler] = None
        self.transfer_manager: Optional[FileTransferManager] = None
        
        # Estado del sistema
        self.tiempo_inicio = 0.0
        self.estadisticas_sistema = {
            'comandos_procesados': 0,
            'fotos_tomadas': 0,
            'archivos_transferidos': 0,
            'errores_totales': 0,
            'tiempo_actividad': 0.0
        }
        
        # Control de hilos
        self.hilo_monitor: Optional[threading.Thread] = None
        self.hilo_mantenimiento: Optional[threading.Thread] = None
        
        self.logger.info("SistemaCamaraUART inicializado")
    
    def _configurar_logging(self) -> logging.Logger:
        """
        Configura el sistema de logging.
        
        Returns:
            Logger configurado
        """
        # Crear logger principal
        logger = logging.getLogger('camara_uart_daemon')
        logger.setLevel(logging.INFO)
        
        # Evitar duplicar handlers
        if logger.handlers:
            logger.handlers.clear()
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Handler para archivo (se configurará después de cargar config)
        return logger
    
    def inicializar(self) -> bool:
        """
        Inicializa todos los componentes del sistema.
        
        Returns:
            bool: True si la inicialización fue exitosa
        """
        try:
            self.logger.info("Inicializando sistema de cámara UART...")
            
            # 1. Cargar configuración
            self.config_manager = ConfigManager(self.archivo_config)
            self._configurar_logging_completo()
            
            # 2. Inicializar controlador de cámara
            self.camara_controller = CamaraController(self.config_manager)
            
            # 3. Inicializar gestor de transferencias
            self.transfer_manager = FileTransferManager(self.config_manager)
            
            # 4. Inicializar manejador UART
            self.uart_handler = UARTHandler(self.config_manager)
            
            # 5. Configurar callbacks y comandos
            self._configurar_callbacks()
            self._registrar_comandos_uart()
            
            # 6. Iniciar servicios
            self.transfer_manager.iniciar()
            
            self.logger.info("Sistema inicializado correctamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error inicializando sistema: {e}")
            self.logger.debug(traceback.format_exc())
            return False
    
    def _configurar_logging_completo(self):
        """Configura logging completo usando la configuración cargada."""
        try:
            # Configurar logger principal con configuración cargada
            log_config = self.config_manager.logging
            
            # Actualizar nivel
            nivel_map = {
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARNING': logging.WARNING,
                'ERROR': logging.ERROR,
                'CRITICAL': logging.CRITICAL
            }
            self.logger.setLevel(nivel_map.get(log_config.nivel, logging.INFO))
            
            # Agregar handler de archivo si no existe
            if not any(isinstance(h, logging.FileHandler) for h in self.logger.handlers):
                # Crear directorio de logs si no existe
                Path(log_config.archivo).parent.mkdir(parents=True, exist_ok=True)
                
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    log_config.archivo,
                    maxBytes=log_config.max_size_mb * 1024 * 1024,
                    backupCount=log_config.backup_count
                )
                file_handler.setLevel(nivel_map.get(log_config.nivel, logging.INFO))
                
                formatter = logging.Formatter(log_config.formato)
                file_handler.setFormatter(formatter)
                
                self.logger.addHandler(file_handler)
                self.logger.info(f"Logging configurado: {log_config.archivo}")
        
        except Exception as e:
            self.logger.warning(f"Error configurando logging completo: {e}")
    
    def _configurar_callbacks(self):
        """Configura callbacks entre componentes."""
        # Callback cuando se completa una captura
        def on_captura_completada(info_captura):
            self.estadisticas_sistema['fotos_tomadas'] += 1
            self.logger.info(f"Foto capturada: {info_captura.nombre_archivo}")
            
            # Programar transferencia automática si está configurado
            # (esto se puede hacer opcional via configuración)
            try:
                id_transferencia = self.transfer_manager.programar_envio(
                    info_captura.ruta_completa,
                    self.uart_handler,
                    info_captura.nombre_archivo
                )
                self.logger.debug(f"Transferencia programada: {id_transferencia}")
            except Exception as e:
                self.logger.error(f"Error programando transferencia: {e}")
        
        # Callback para errores de captura
        def on_error_captura(error):
            self.estadisticas_sistema['errores_totales'] += 1
            self.logger.error(f"Error en captura: {error}")
        
        # Callback para progreso de transferencia
        def on_progreso_transferencia(info_transferencia):
            if info_transferencia.progreso_chunks % 10 == 0:  # Log cada 10 chunks
                self.logger.debug(f"Transferencia {info_transferencia.id_transferencia}: "
                                f"{info_transferencia.porcentaje_completado:.1f}%")
        
        # Callback para transferencia completada
        def on_transferencia_completada(info_transferencia):
            self.estadisticas_sistema['archivos_transferidos'] += 1
            self.logger.info(f"Transferencia completada: {info_transferencia.archivo_destino}")
        
        # Callback para errores de transferencia
        def on_error_transferencia(info_transferencia, error):
            self.estadisticas_sistema['errores_totales'] += 1
            self.logger.error(f"Error en transferencia {info_transferencia.id_transferencia}: {error}")
        
        # Configurar callbacks
        self.camara_controller.establecer_callback_captura(on_captura_completada)
        self.camara_controller.establecer_callback_error(on_error_captura)
        
        self.transfer_manager.establecer_callbacks(
            callback_progreso=on_progreso_transferencia,
            callback_completada=on_transferencia_completada,
            callback_error=on_error_transferencia
        )
    
    def _registrar_comandos_uart(self):
        """Registra todos los comandos UART disponibles."""
        # Comando: foto
        def cmd_foto(comando):
            try:
                nombre_personalizado = None
                if comando.parametros:
                    nombre_personalizado = comando.parametros[0]
                
                info_captura = self.camara_controller.tomar_foto(nombre_personalizado)
                self.estadisticas_sistema['comandos_procesados'] += 1
                
                return (f"OK|{info_captura.nombre_archivo}|{info_captura.tamaño_bytes}|"
                       f"{info_captura.ruta_completa}")
                       
            except Exception as e:
                self.estadisticas_sistema['errores_totales'] += 1
                return f"ERROR|CAPTURE_FAILED|{str(e)}"
        
        # Comando: estado
        def cmd_estado(comando):
            try:
                estado = self.obtener_estado_completo()
                info_resumida = (f"STATUS:ACTIVO|{self.config_manager.uart.puerto}|"
                               f"{self.config_manager.uart.baudrate}|"
                               f"{self.estadisticas_sistema['fotos_tomadas']}|"
                               f"{self.estadisticas_sistema['comandos_procesados']}")
                
                self.estadisticas_sistema['comandos_procesados'] += 1
                return info_resumida
                
            except Exception as e:
                return f"ERROR|STATUS_FAILED|{str(e)}"
        
        # Comando: resolucion
        def cmd_resolucion(comando):
            try:
                info_res = self.camara_controller.obtener_info_resolucion_actual()
                respuesta = (f"RESOLUCION|{info_res['ancho']}x{info_res['alto']}|"
                           f"{info_res['megapixeles']}MP|{info_res['formato']}")
                
                self.estadisticas_sistema['comandos_procesados'] += 1
                return respuesta
                
            except Exception as e:
                return f"ERROR|RESOLUTION_FAILED|{str(e)}"
        
        # Comando: res:WxH (cambiar resolución)
        def cmd_cambiar_resolucion(comando):
            try:
                if not comando.parametros:
                    return "ERROR|SYNTAX_ERROR|Uso: res:1920x1080"
                
                resolucion_str = comando.parametros[0]
                if 'x' not in resolucion_str:
                    return "ERROR|SYNTAX_ERROR|Formato: WIDTHxHEIGHT"
                
                ancho, alto = map(int, resolucion_str.split('x'))
                
                if self.camara_controller.cambiar_resolucion(ancho, alto):
                    self.estadisticas_sistema['comandos_procesados'] += 1
                    return f"OK:Resolucion {ancho}x{alto}"
                else:
                    return f"ERROR|RESOLUTION_CHANGE_FAILED|No se pudo cambiar a {ancho}x{alto}"
                    
            except ValueError:
                return "ERROR|SYNTAX_ERROR|Formato invalido. Usar: res:1920x1080"
            except Exception as e:
                return f"ERROR|RESOLUTION_CHANGE_FAILED|{str(e)}"
        
        # Comando: baudrate:SPEED (cambiar velocidad)
        def cmd_cambiar_baudrate(comando):
            try:
                if not comando.parametros:
                    return "ERROR|SYNTAX_ERROR|Uso: baudrate:115200"
                
                nueva_velocidad = int(comando.parametros[0])
                
                if self.uart_handler.cambiar_baudrate(nueva_velocidad):
                    self.estadisticas_sistema['comandos_procesados'] += 1
                    return f"BAUDRATE_CHANGED|{nueva_velocidad}"
                else:
                    return f"ERROR|BAUDRATE_CHANGE_FAILED|No se pudo cambiar a {nueva_velocidad}"
                    
            except ValueError:
                return "ERROR|SYNTAX_ERROR|Velocidad debe ser numerica"
            except Exception as e:
                return f"ERROR|BAUDRATE_CHANGE_FAILED|{str(e)}"
        
        # Comando: listar
        def cmd_listar_archivos(comando):
            try:
                archivos = self.camara_controller.listar_archivos()
                total_archivos = len(archivos)
                total_bytes = sum(a['tamaño_bytes'] for a in archivos)
                
                respuesta = f"FILES|{total_archivos}|{total_bytes}"
                
                # Agregar últimos 5 archivos
                for archivo in archivos[:5]:
                    respuesta += f"|{archivo['nombre']}:{archivo['tamaño_bytes']}"
                
                self.estadisticas_sistema['comandos_procesados'] += 1
                return respuesta
                
            except Exception as e:
                return f"ERROR|LIST_FAILED|{str(e)}"
        
        # Comando: descargar:archivo
        def cmd_descargar_archivo(comando):
            try:
                if not comando.parametros:
                    return "ERROR|SYNTAX_ERROR|Uso: descargar:nombre_archivo.jpg"
                
                nombre_archivo = comando.parametros[0]
                info_archivo = self.camara_controller.obtener_info_archivo(nombre_archivo)
                
                if not info_archivo:
                    return f"ERROR|FILE_NOT_FOUND|{nombre_archivo}"
                
                # Programar transferencia
                id_transferencia = self.transfer_manager.programar_envio(
                    info_archivo['ruta_completa'],
                    self.uart_handler,
                    nombre_archivo
                )
                
                self.estadisticas_sistema['comandos_procesados'] += 1
                return f"DOWNLOAD_STARTED|{id_transferencia}|{info_archivo['tamaño_bytes']}"
                
            except Exception as e:
                return f"ERROR|DOWNLOAD_FAILED|{str(e)}"
        
        # Comando: limpiar
        def cmd_limpiar_archivos(comando):
            try:
                criterio = "antiguos"
                if comando.parametros:
                    criterio = comando.parametros[0]
                
                resultado = self.camara_controller.limpiar_archivos(criterio)
                
                self.estadisticas_sistema['comandos_procesados'] += 1
                return (f"CLEANED|{resultado['archivos_eliminados']}|"
                       f"{resultado['bytes_liberados']}|{criterio}")
                
            except Exception as e:
                return f"ERROR|CLEAN_FAILED|{str(e)}"
        
        # Comando: estadisticas
        def cmd_estadisticas(comando):
            try:
                stats = self.obtener_estadisticas_resumidas()
                
                respuesta = (f"STATS|fotos:{stats['fotos_tomadas']}|"
                           f"comandos:{stats['comandos_procesados']}|"
                           f"transferencias:{stats['archivos_transferidos']}|"
                           f"errores:{stats['errores_totales']}|"
                           f"uptime:{stats['tiempo_actividad']:.1f}s")
                
                self.estadisticas_sistema['comandos_procesados'] += 1
                return respuesta
                
            except Exception as e:
                return f"ERROR|STATS_FAILED|{str(e)}"
        
        # Comando: reiniciar
        def cmd_reiniciar_camara(comando):
            try:
                if self.camara_controller.reinicializar():
                    self.estadisticas_sistema['comandos_procesados'] += 1
                    return "OK:Camara reinicializada"
                else:
                    return "ERROR|RESTART_FAILED|No se pudo reinicializar camara"
                    
            except Exception as e:
                return f"ERROR|RESTART_FAILED|{str(e)}"
        
        # Comando: test
        def cmd_test_sistema(comando):
            try:
                resultado_test = self.camara_controller.realizar_captura_test()
                
                if resultado_test['exito']:
                    self.estadisticas_sistema['comandos_procesados'] += 1
                    return f"TEST_OK|{resultado_test['tiempo_captura']:.2f}s"
                else:
                    return f"TEST_FAILED|{resultado_test['error']}"
                    
            except Exception as e:
                return f"ERROR|TEST_FAILED|{str(e)}"
        
        # Comando: salir
        def cmd_salir(comando):
            self.logger.info("Comando de salida recibido")
            self.estadisticas_sistema['comandos_procesados'] += 1
            # Programar parada del sistema
            threading.Thread(target=self._parada_diferida, daemon=True).start()
            return "CAMERA_OFFLINE"
        
        # Registrar todos los comandos
        comandos = {
            'foto': cmd_foto,
            'estado': cmd_estado,
            'status': cmd_estado,  # Alias
            'resolucion': cmd_resolucion,
            'resolution': cmd_resolucion,  # Alias
            'res': cmd_cambiar_resolucion,
            'baudrate': cmd_cambiar_baudrate,
            'velocidad': cmd_cambiar_baudrate,  # Alias
            'listar': cmd_listar_archivos,
            'list': cmd_listar_archivos,  # Alias
            'descargar': cmd_descargar_archivo,
            'download': cmd_descargar_archivo,  # Alias
            'limpiar': cmd_limpiar_archivos,
            'clean': cmd_limpiar_archivos,  # Alias
            'estadisticas': cmd_estadisticas,
            'stats': cmd_estadisticas,  # Alias
            'reiniciar': cmd_reiniciar_camara,
            'restart': cmd_reiniciar_camara,  # Alias
            'test': cmd_test_sistema,
            'salir': cmd_salir,
            'exit': cmd_salir,  # Alias
            'quit': cmd_salir   # Alias
        }
        
        for comando, handler in comandos.items():
            self.uart_handler.registrar_comando(comando, handler)
        
        self.logger.info(f"Registrados {len(comandos)} comandos UART")
    
    def iniciar(self) -> bool:
        """
        Inicia el sistema completo.
        
        Returns:
            bool: True si el inicio fue exitoso
        """
        try:
            if self.ejecutando:
                self.logger.warning("Sistema ya está ejecutándose")
                return True
            
            # Inicializar componentes
            if not self.inicializar():
                return False
            
            # Configurar manejo de señales
            self._configurar_senales()
            
            # Iniciar UART
            self.uart_handler.iniciar()
            
            # Iniciar hilos de monitoreo
            self.ejecutando = True
            self.tiempo_inicio = time.time()
            
            self.hilo_monitor = threading.Thread(target=self._bucle_monitor, daemon=True)
            self.hilo_monitor.start()
            
            self.hilo_mantenimiento = threading.Thread(target=self._bucle_mantenimiento, daemon=True)
            self.hilo_mantenimiento.start()
            
            self.logger.info("Sistema de cámara UART iniciado exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error iniciando sistema: {e}")
            self.logger.debug(traceback.format_exc())
            return False
    
    def detener(self):
        """Detiene el sistema completo."""
        self.logger.info("Deteniendo sistema de cámara UART...")
        
        self.ejecutando = False
        
        # Detener componentes
        if self.uart_handler:
            self.uart_handler.detener()
        
        if self.transfer_manager:
            self.transfer_manager.detener()
        
        # Esperar hilos de monitoreo
        if self.hilo_monitor and self.hilo_monitor.is_alive():
            self.hilo_monitor.join(timeout=5.0)
        
        if self.hilo_mantenimiento and self.hilo_mantenimiento.is_alive():
            self.hilo_mantenimiento.join(timeout=5.0)
        
        # Guardar estadísticas finales
        self._guardar_estadisticas_finales()
        
        self.logger.info("Sistema detenido completamente")
    
    def _parada_diferida(self):
        """Parada diferida del sistema (para comando salir)."""
        time.sleep(2.0)  # Dar tiempo para enviar respuesta
        self.detener()
    
    def _configurar_senales(self):
        """Configura manejo de señales del sistema."""
        def manejador_senal(signum, frame):
            self.logger.info(f"Señal {signum} recibida, deteniendo sistema...")
            self.detener()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, manejador_senal)
        signal.signal(signal.SIGTERM, manejador_senal)
    
    def _bucle_monitor(self):
        """Bucle de monitoreo del sistema."""
        while self.ejecutando:
            try:
                # Actualizar estadísticas
                self.estadisticas_sistema['tiempo_actividad'] = time.time() - self.tiempo_inicio
                
                # Log periódico de estado
                if int(self.estadisticas_sistema['tiempo_actividad']) % 300 == 0:  # Cada 5 minutos
                    self.logger.info(f"Sistema activo: {self.obtener_estadisticas_resumidas()}")
                
                time.sleep(60)  # Monitor cada minuto
                
            except Exception as e:
                self.logger.error(f"Error en bucle monitor: {e}")
                time.sleep(60)
    
    def _bucle_mantenimiento(self):
        """Bucle de mantenimiento del sistema."""
        while self.ejecutando:
            try:
                # Mantenimiento cada hora
                time.sleep(3600)
                
                if not self.ejecutando:
                    break
                
                self.logger.info("Ejecutando mantenimiento del sistema...")
                
                # Limpiar archivos temporales
                if self.transfer_manager:
                    resultado = self.transfer_manager.limpiar_archivos_temporales()
                    if resultado['archivos_eliminados'] > 0:
                        self.logger.info(f"Mantenimiento: {resultado['archivos_eliminados']} archivos temporales eliminados")
                
                # Limpiar historial de capturas
                if self.camara_controller:
                    self.camara_controller.limpiar_historial(50)
                
                # Auto-limpieza si está habilitada
                if self.config_manager.sistema.auto_limpiar:
                    resultado = self.camara_controller.limpiar_archivos("antiguos")
                    if resultado['archivos_eliminados'] > 0:
                        self.logger.info(f"Auto-limpieza: {resultado['archivos_eliminados']} archivos antiguos eliminados")
                
            except Exception as e:
                self.logger.error(f"Error en mantenimiento: {e}")
    
    def obtener_estado_completo(self) -> Dict[str, Any]:
        """
        Obtiene estado completo del sistema.
        
        Returns:
            Dict con estado detallado
        """
        estado = {
            'sistema': {
                'ejecutando': self.ejecutando,
                'tiempo_inicio': self.tiempo_inicio,
                'tiempo_actividad': time.time() - self.tiempo_inicio if self.tiempo_inicio > 0 else 0,
                'estadisticas': self.estadisticas_sistema.copy()
            },
            'configuracion': self.config_manager.obtener_info_sistema() if self.config_manager else {},
            'camara': self.camara_controller.obtener_estado_sistema() if self.camara_controller else {},
            'uart': self.uart_handler.obtener_estadisticas() if self.uart_handler else {},
            'transferencias': self.transfer_manager.obtener_estadisticas() if self.transfer_manager else {}
        }
        
        return estado
    
    def obtener_estadisticas_resumidas(self) -> Dict[str, Any]:
        """Obtiene estadísticas resumidas del sistema."""
        return {
            'fotos_tomadas': self.estadisticas_sistema['fotos_tomadas'],
            'comandos_procesados': self.estadisticas_sistema['comandos_procesados'],
            'archivos_transferidos': self.estadisticas_sistema['archivos_transferidos'],
            'errores_totales': self.estadisticas_sistema['errores_totales'],
            'tiempo_actividad': time.time() - self.tiempo_inicio if self.tiempo_inicio > 0 else 0
        }
    
    def _guardar_estadisticas_finales(self):
        """Guarda estadísticas finales al detener el sistema."""
        try:
            archivo_stats = Path(self.config_manager.sistema.directorio_logs) / "estadisticas_finales.json"
            
            estadisticas_finales = {
                'timestamp_cierre': datetime.now().isoformat(),
                'tiempo_total_ejecucion': time.time() - self.tiempo_inicio if self.tiempo_inicio > 0 else 0,
                'estado_completo': self.obtener_estado_completo()
            }
            
            with open(archivo_stats, 'w', encoding='utf-8') as f:
                json.dump(estadisticas_finales, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Estadísticas finales guardadas en: {archivo_stats}")
            
        except Exception as e:
            self.logger.error(f"Error guardando estadísticas finales: {e}")
    
    def ejecutar_bucle_principal(self):
        """Ejecuta el bucle principal del daemon."""
        try:
            self.logger.info("Iniciando bucle principal del daemon...")
            
            while self.ejecutando:
                try:
                    time.sleep(1.0)
                except KeyboardInterrupt:
                    self.logger.info("Interrupción por teclado recibida")
                    break
                except Exception as e:
                    self.logger.error(f"Error en bucle principal: {e}")
                    time.sleep(5.0)
        
        finally:
            self.detener()


def configurar_argumentos():
    """Configura argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Daemon principal del sistema de cámara UART",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python main_daemon.py                                    # Configuración por defecto
  python main_daemon.py -c config/camara_custom.conf      # Configuración personalizada
  python main_daemon.py --debug                           # Modo debug
  python main_daemon.py --test                            # Solo probar inicialización
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        default='config/camara.conf',
        help='Archivo de configuración (default: config/camara.conf)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Habilitar modo debug'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Solo probar inicialización y salir'
    )
    
    parser.add_argument(
        '--daemon',
        action='store_true',
        help='Ejecutar como daemon (en background)'
    )
    
    parser.add_argument(
        '--pid-file',
        help='Archivo PID para control de daemon'
    )
    
    return parser.parse_args()


def configurar_daemon(pid_file: Optional[str] = None):
    """Configura el proceso como daemon."""
    try:
        import daemon
        import daemon.pidfile
        
        # Configurar contexto de daemon
        context = daemon.DaemonContext()
        
        if pid_file:
            context.pidfile = daemon.pidfile.PIDLockFile(pid_file)
        
        # Mantener stdin, stdout, stderr abiertos para logging
        context.stdin = sys.stdin
        context.stdout = sys.stdout
        context.stderr = sys.stderr
        
        return context
        
    except ImportError:
        print("Módulo 'python-daemon' no disponible. Installar con: pip install python-daemon")
        return None


def main():
    """Función principal del daemon."""
    args = configurar_argumentos()
    
    # Configurar logging inicial
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    
    print("🚀 Iniciando Sistema de Cámara UART v1.0")
    print(f"📁 Configuración: {args.config}")
    
    try:
        # Crear sistema
        sistema = SistemaCamaraUART(args.config)
        
        # Modo test: solo probar inicialización
        if args.test:
            print("🧪 Modo de prueba: verificando inicialización...")
            
        # Modo test: solo probar inicialización
        if args.test:
            print("🧪 Modo de prueba: verificando inicialización...")
            
            if sistema.inicializar():
                print("✅ Inicialización exitosa")
                print("📊 Estado del sistema:")
                estado = sistema.obtener_estado_completo()
                
                print(f"   • Cámara: {estado['camara']['estado_camara']}")
                print(f"   • Puerto UART: {estado['uart']['puerto']} @ {estado['uart']['baudrate']} baudios")
                print(f"   • Resolución: {estado['camara']['configuracion']['resolucion']}")
                print(f"   • Directorio fotos: {estado['camara']['archivos']['directorio']}")
                
                # Test de captura
                print("📸 Probando captura de test...")
                resultado_test = sistema.camara_controller.realizar_captura_test()
                if resultado_test['exito']:
                    print(f"   ✅ Captura test exitosa ({resultado_test['tiempo_captura']:.2f}s)")
                else:
                    print(f"   ❌ Error en captura test: {resultado_test['error']}")
                
                print("🏁 Test completado exitosamente")
                return 0
            else:
                print("❌ Error en inicialización")
                return 1
        
        # Modo daemon
        if args.daemon:
            print("🔧 Configurando modo daemon...")
            
            daemon_context = configurar_daemon(args.pid_file)
            if not daemon_context:
                print("❌ No se pudo configurar daemon")
                return 1
            
            print("🌙 Iniciando como daemon...")
            with daemon_context:
                ejecutar_sistema_principal(sistema)
        else:
            # Modo normal (foreground)
            ejecutar_sistema_principal(sistema)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupción por teclado")
        return 0
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        logging.error(f"Error fatal en main: {e}")
        logging.debug(traceback.format_exc())
        return 1


def ejecutar_sistema_principal(sistema: SistemaCamaraUART):
    """
    Ejecuta el sistema principal.
    
    Args:
        sistema: Instancia del sistema de cámara UART
    """
    try:
        # Iniciar sistema
        if not sistema.iniciar():
            print("❌ Error iniciando sistema")
            return
        
        print("✅ Sistema iniciado exitosamente")
        print("📡 Esperando comandos UART...")
        print("💡 Envía 'salir' por UART para detener el sistema")
        print("📊 Comandos disponibles: foto, estado, resolucion, listar, descargar, etc.")
        
        # Mostrar información de conexión
        if sistema.config_manager:
            print(f"🔌 Puerto: {sistema.config_manager.uart.puerto}")
            print(f"⚡ Velocidad: {sistema.config_manager.uart.baudrate} baudios")
            print(f"📸 Resolución: {sistema.config_manager.camara.resolucion}")
            print(f"📁 Directorio: {sistema.config_manager.sistema.directorio_fotos}")
        
        print("=" * 60)
        
        # Ejecutar bucle principal
        sistema.ejecutar_bucle_principal()
        
    except Exception as e:
        sistema.logger.error(f"Error en ejecución principal: {e}")
        print(f"❌ Error en ejecución: {e}")
    finally:
        print("🔄 Limpiando recursos...")


def verificar_requisitos():
    """Verifica que los requisitos del sistema estén cumplidos."""
    errores = []
    
    # Verificar Python 3.7+
    if sys.version_info < (3, 7):
        errores.append("Se requiere Python 3.7 o superior")
    
    # Verificar módulos críticos
    modulos_requeridos = [
        ('serial', 'pyserial'),
        ('configparser', 'configparser (incluido en Python)'),
    ]
    
    for modulo, nombre_paquete in modulos_requeridos:
        try:
            __import__(modulo)
        except ImportError:
            errores.append(f"Módulo requerido no encontrado: {nombre_paquete}")
    
    # Verificar picamera2 (opcional, se maneja en CamaraController)
    try:
        import picamera2
    except ImportError:
        print("⚠️  Advertencia: picamera2 no disponible (requerido para Raspberry Pi)")
    
    # Verificar permisos de directorio
    directorios_requeridos = ['config', 'data', 'logs']
    for directorio in directorios_requeridos:
        path = Path(directorio)
        try:
            path.mkdir(exist_ok=True)
            # Test de escritura
            test_file = path / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            errores.append(f"Sin permisos de escritura en {directorio}: {e}")
    
    if errores:
        print("❌ Errores de requisitos:")
        for error in errores:
            print(f"   • {error}")
        print("\n💡 Soluciones sugeridas:")
        print("   • pip install pyserial picamera2")
        print("   • sudo usermod -a -G dialout $USER  # Para permisos UART")
        print("   • sudo chmod 755 ./  # Para permisos de directorio")
        return False
    
    return True


def mostrar_informacion_sistema():
    """Muestra información del sistema al inicio."""
    import platform
    
    print("\n" + "=" * 60)
    print("📋 INFORMACIÓN DEL SISTEMA")
    print("=" * 60)
    print(f"🐍 Python: {sys.version}")
    print(f"💻 Sistema: {platform.system()} {platform.release()}")
    print(f"🏗️  Arquitectura: {platform.machine()}")
    print(f"📂 Directorio trabajo: {Path.cwd()}")
    
    # Información de Raspberry Pi si está disponible
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if 'Model' in line:
                    print(f"🍓 {line.strip()}")
                    break
    except:
        pass
    
    # Verificar cámara
    try:
        import subprocess
        result = subprocess.run(['vcgencmd', 'get_camera'], 
                              capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            print(f"📸 Cámara: {result.stdout.strip()}")
    except:
        print("📸 Cámara: Estado desconocido")
    
    # Puertos serie disponibles
    print("🔌 Puertos serie disponibles:")
    puertos_serie = []
    for puerto in ['/dev/ttyS0', '/dev/ttyAMA0', '/dev/ttyUSB0', '/dev/ttyACM0']:
        if Path(puerto).exists():
            puertos_serie.append(puerto)
    
    if puertos_serie:
        for puerto in puertos_serie:
            print(f"   • {puerto}")
    else:
        print("   • Ninguno detectado")
    
    print("=" * 60)


def crear_archivos_ejemplo():
    """Crea archivos de ejemplo si no existen."""
    # Crear estructura de directorios
    directorios = ['config', 'data/fotos', 'data/temp', 'logs', 'scripts']
    
    for directorio in directorios:
        Path(directorio).mkdir(parents=True, exist_ok=True)
    
    # Crear archivo de configuración ejemplo si no existe
    config_ejemplo = Path('config/camara.conf.example')
    if not config_ejemplo.exists():
        print("📝 Creando archivo de configuración ejemplo...")
        # El ConfigManager se encarga de crear el archivo ejemplo
        try:
            from config_manager import ConfigManager
            ConfigManager()  # Esto creará el archivo ejemplo
        except:
            pass
    
    # Crear script de inicio rápido
    script_inicio = Path('inicio_rapido.sh')
    if not script_inicio.exists():
        contenido_script = """#!/bin/bash
# Script de inicio rápido para Sistema de Cámara UART

echo "🚀 Iniciando Sistema de Cámara UART..."

# Verificar permisos UART
if ! groups $USER | grep -q dialout; then
    echo "⚠️  Advertencia: Usuario no está en grupo dialout"
    echo "💡 Ejecutar: sudo usermod -a -G dialout $USER"
    echo "   Luego cerrar sesión y volver a entrar"
fi

# Crear configuración si no existe
if [ ! -f config/camara.conf ]; then
    echo "📝 Creando configuración por defecto..."
    cp config/camara.conf.example config/camara.conf 2>/dev/null || true
fi

# Iniciar sistema
python3 scripts/main_daemon.py "$@"
"""
        
        script_inicio.write_text(contenido_script)
        script_inicio.chmod(0o755)
        print(f"📄 Script de inicio creado: {script_inicio}")


if __name__ == "__main__":
    # Banner de inicio
    print("""
╔══════════════════════════════════════════════════════╗
║           🚀 SISTEMA DE CÁMARA UART v1.0            ║
║                                                      ║
║  Control remoto de cámara Raspberry Pi por UART     ║
║  con transferencia automática de archivos           ║
╚══════════════════════════════════════════════════════╝
    """)
    
    # Mostrar información del sistema
    mostrar_informacion_sistema()
    
    # Verificar requisitos
    print("🔍 Verificando requisitos del sistema...")
    if not verificar_requisitos():
        print("\n❌ Requisitos no cumplidos. Corrige los errores antes de continuar.")
        sys.exit(1)
    
    print("✅ Todos los requisitos verificados")
    
    # Crear archivos ejemplo si es necesario
    crear_archivos_ejemplo()
    
    # Ejecutar función principal
    codigo_salida = main()
    
    print(f"\n👋 Sistema finalizado con código: {codigo_salida}")
    sys.exit(codigo_salida)
