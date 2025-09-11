"""
Excepciones personalizadas para el sistema de cámara UART.

Este módulo define todas las excepciones específicas del proyecto,
proporcionando un manejo de errores granular y descriptivo.
"""

class CamaraUARTError(Exception):
    """Excepción base para todos los errores del sistema de cámara UART."""
    
    def __init__(self, mensaje: str, codigo_error: str = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo_error = codigo_error or "UNKNOWN_ERROR"
    
    def __str__(self):
        return f"[{self.codigo_error}] {self.mensaje}"


# ============================================================================
# EXCEPCIONES DE CONFIGURACIÓN
# ============================================================================

class ConfigError(CamaraUARTError):
    """Error relacionado con la configuración del sistema."""
    
    def __init__(self, mensaje: str):
        super().__init__(mensaje, "CONFIG_ERROR")


class ConfigFileNotFoundError(ConfigError):
    """Error cuando no se encuentra el archivo de configuración."""
    
    def __init__(self, ruta_archivo: str):
        mensaje = f"Archivo de configuración no encontrado: {ruta_archivo}"
        super().__init__(mensaje)
        self.ruta_archivo = ruta_archivo


class ConfigInvalidError(ConfigError):
    """Error cuando la configuración tiene valores inválidos."""
    
    def __init__(self, seccion: str, clave: str, valor: str, razon: str):
        mensaje = f"Configuración inválida [{seccion}][{clave}] = '{valor}': {razon}"
        super().__init__(mensaje)
        self.seccion = seccion
        self.clave = clave
        self.valor = valor
        self.razon = razon


# ============================================================================
# EXCEPCIONES DE UART
# ============================================================================

class UARTError(CamaraUARTError):
    """Error base para problemas de comunicación UART."""
    
    def __init__(self, mensaje: str, puerto: str = None):
        super().__init__(mensaje, "UART_ERROR")
        self.puerto = puerto


class UARTConnectionError(UARTError):
    """Error al establecer conexión UART."""
    
    def __init__(self, puerto: str, razon: str):
        mensaje = f"No se pudo conectar al puerto {puerto}: {razon}"
        super().__init__(mensaje, puerto)
        self.razon = razon


class UARTTimeoutError(UARTError):
    """Error de timeout en comunicación UART."""
    
    def __init__(self, puerto: str, timeout: float, operacion: str = "comunicación"):
        mensaje = f"Timeout en {operacion} UART ({timeout}s) en puerto {puerto}"
        super().__init__(mensaje, puerto)
        self.timeout = timeout
        self.operacion = operacion


class UARTDataError(UARTError):
    """Error en datos recibidos por UART."""
    
    def __init__(self, puerto: str, datos_recibidos: str, razon: str):
        mensaje = f"Datos UART inválidos en {puerto}: {razon}"
        super().__init__(mensaje, puerto)
        self.datos_recibidos = datos_recibidos
        self.razon = razon


# ============================================================================
# EXCEPCIONES DE CÁMARA
# ============================================================================

class CamaraError(CamaraUARTError):
    """Error base para problemas de cámara."""
    
    def __init__(self, mensaje: str):
        super().__init__(mensaje, "CAMERA_ERROR")


class CamaraNotFoundError(CamaraError):
    """Error cuando no se detecta la cámara."""
    
    def __init__(self):
        mensaje = "Cámara no detectada. Verificar conexión física y configuración."
        super().__init__(mensaje)


class CamaraInitError(CamaraError):
    """Error al inicializar la cámara."""
    
    def __init__(self, razon: str):
        mensaje = f"Error al inicializar cámara: {razon}"
        super().__init__(mensaje)
        self.razon = razon


class CamaraCaptureError(CamaraError):
    """Error durante la captura de foto."""
    
    def __init__(self, razon: str, archivo_destino: str = None):
        mensaje = f"Error al capturar foto: {razon}"
        super().__init__(mensaje)
        self.razon = razon
        self.archivo_destino = archivo_destino


class CamaraResolutionError(CamaraError):
    """Error con resolución de cámara."""
    
    def __init__(self, resolucion: tuple, razon: str):
        mensaje = f"Resolución {resolucion[0]}x{resolucion[1]} inválida: {razon}"
        super().__init__(mensaje)
        self.resolucion = resolucion
        self.razon = razon


# ============================================================================
# EXCEPCIONES DE TRANSFERENCIA DE ARCHIVOS
# ============================================================================

class FileTransferError(CamaraUARTError):
    """Error base para transferencia de archivos."""
    
    def __init__(self, mensaje: str, archivo: str = None):
        super().__init__(mensaje, "FILE_TRANSFER_ERROR")
        self.archivo = archivo


class FileNotFoundError(FileTransferError):
    """Error cuando el archivo a transferir no existe."""
    
    def __init__(self, ruta_archivo: str):
        mensaje = f"Archivo no encontrado: {ruta_archivo}"
        super().__init__(mensaje, ruta_archivo)
        self.ruta_archivo = ruta_archivo


class FileTransferTimeoutError(FileTransferError):
    """Error de timeout durante transferencia."""
    
    def __init__(self, archivo: str, bytes_transferidos: int, bytes_totales: int):
        porcentaje = (bytes_transferidos / bytes_totales * 100) if bytes_totales > 0 else 0
        mensaje = f"Timeout en transferencia de {archivo} ({porcentaje:.1f}% completado)"
        super().__init__(mensaje, archivo)
        self.bytes_transferidos = bytes_transferidos
        self.bytes_totales = bytes_totales


class FileTransferChecksumError(FileTransferError):
    """Error de verificación de integridad en transferencia."""
    
    def __init__(self, archivo: str, checksum_esperado: str, checksum_recibido: str):
        mensaje = f"Error de integridad en {archivo}: esperado {checksum_esperado}, recibido {checksum_recibido}"
        super().__init__(mensaje, archivo)
        self.checksum_esperado = checksum_esperado
        self.checksum_recibido = checksum_recibido


# ============================================================================
# EXCEPCIONES DE SISTEMA
# ============================================================================

class SystemError(CamaraUARTError):
    """Error de sistema general."""
    
    def __init__(self, mensaje: str):
        super().__init__(mensaje, "SYSTEM_ERROR")


class DiskSpaceError(SystemError):
    """Error por falta de espacio en disco."""
    
    def __init__(self, directorio: str, espacio_requerido: int, espacio_disponible: int):
        mensaje = f"Espacio insuficiente en {directorio}: necesarios {espacio_requerido} bytes, disponibles {espacio_disponible}"
        super().__init__(mensaje)
        self.directorio = directorio
        self.espacio_requerido = espacio_requerido
        self.espacio_disponible = espacio_disponible


class PermissionError(SystemError):
    """Error de permisos de archivos/directorios."""
    
    def __init__(self, ruta: str, operacion: str):
        mensaje = f"Permisos insuficientes para {operacion} en {ruta}"
        super().__init__(mensaje)
        self.ruta = ruta
        self.operacion = operacion


# ============================================================================
# EXCEPCIONES DE PROTOCOLO
# ============================================================================

class ProtocolError(CamaraUARTError):
    """Error en el protocolo de comunicación."""
    
    def __init__(self, mensaje: str, comando: str = None):
        super().__init__(mensaje, "PROTOCOL_ERROR")
        self.comando = comando


class CommandNotFoundError(ProtocolError):
    """Error cuando se recibe un comando no reconocido."""
    
    def __init__(self, comando: str, comandos_disponibles: list = None):
        mensaje = f"Comando '{comando}' no reconocido"
        if comandos_disponibles:
            mensaje += f". Comandos disponibles: {', '.join(comandos_disponibles)}"
        super().__init__(mensaje, comando)
        self.comandos_disponibles = comandos_disponibles or []


class CommandSyntaxError(ProtocolError):
    """Error de sintaxis en comando."""
    
    def __init__(self, comando: str, sintaxis_esperada: str):
        mensaje = f"Sintaxis incorrecta en comando '{comando}'. Esperado: {sintaxis_esperada}"
        super().__init__(mensaje, comando)
        self.sintaxis_esperada = sintaxis_esperada


# ============================================================================
# UTILIDADES DE EXCEPCIONES
# ============================================================================

def format_error_response(excepcion: CamaraUARTError) -> str:
    """
    Formatea una excepción para enviar por UART.
    
    Args:
        excepcion: La excepción a formatear
        
    Returns:
        str: Mensaje formateado para UART
    """
    return f"ERROR|{excepcion.codigo_error}|{excepcion.mensaje}"


def is_recoverable_error(excepcion: Exception) -> bool:
    """
    Determina si un error es recuperable y el sistema puede continuar.
    
    Args:
        excepcion: La excepción a evaluar
        
    Returns:
        bool: True si el error es recuperable
    """
    # Errores no recuperables
    errores_fatales = (
        CamaraNotFoundError,
        ConfigFileNotFoundError,
        DiskSpaceError,
        PermissionError
    )
    
    # Errores recuperables
    errores_recuperables = (
        UARTTimeoutError,
        CamaraCaptureError,
        FileTransferTimeoutError,
        CommandNotFoundError
    )
    
    if isinstance(excepcion, errores_fatales):
        return False
    elif isinstance(excepcion, errores_recuperables):
        return True
    else:
        # Por defecto, consideramos errores desconocidos como no recuperables
        return False


# Mapeo de códigos de error para respuestas UART
ERROR_CODES = {
    ConfigError: "CONFIG_ERROR",
    UARTError: "UART_ERROR", 
    CamaraError: "CAMERA_ERROR",
    FileTransferError: "FILE_ERROR",
    SystemError: "SYSTEM_ERROR",
    ProtocolError: "PROTOCOL_ERROR"
}
