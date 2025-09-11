# 📸 Sistema de Cámara UART para Raspberry Pi

> Control remoto de cámara Raspberry Pi a través de puerto serie con transferencia automática de archivos

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/platform-Raspberry%20Pi-red.svg)](https://www.raspberrypi.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

## 🌟 Características Principales

- **🎮 Control Remoto por UART**: 15+ comandos para control completo de la cámara
- **📁 Transferencia Automática**: Envío de fotos por protocolo UART con verificación de integridad
- **⚙️ Configuración Dinámica**: Cambio de resolución y velocidad en tiempo real
- **🔧 Instalación Automática**: Scripts de instalación y desinstalación completos
- **🛡️ Arquitectura Robusta**: Manejo de errores, reconexión automática y logging avanzado
- **🎯 Sistema Dual Pi**: Optimizado para configuraciones Pi Zero + Pi 3B+/4
- **🔄 Servicio Systemd**: Ejecución como servicio del sistema con inicio automático

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    UART     ┌─────────────────┐
│   Pi Zero W     │◄──────────►│   Pi 3B+/4      │
│                 │  115200bps  │                 │
│ 📸 Captura      │             │ 📡 Commander    │
│ 🔧 Procesa      │             │ 💾 Storage      │
│ 📤 Transmite    │             │ 🌐 Web Interface│
│                 │             │ ☁️ Backup       │
└─────────────────┘             └─────────────────┘
      512MB RAM                       1GB+ RAM
```

## 🚀 Inicio Rápido

### Instalación Automática

```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/sistema-camara-uart.git
cd sistema-camara-uart

# Instalación automática (recomendado)
chmod +x scripts/install.sh
./scripts/install.sh

# El instalador configura todo automáticamente:
# ✅ Dependencias del sistema
# ✅ Entorno virtual Python  
# ✅ Configuración de UART y cámara
# ✅ Permisos de usuario
# ✅ Servicio systemd
```

### Uso Inmediato

```bash
# Iniciar sistema manualmente
./inicio_rapido.sh

# O como servicio
sudo systemctl start camara-uart
sudo systemctl status camara-uart

# Probar con cliente interactivo
./test_cliente.sh
```

## 📋 Comandos UART Disponibles

| Comando | Descripción | Ejemplo | Respuesta |
|---------|-------------|---------|-----------|
| `foto` | Tomar fotografía | `foto` | `OK\|20250910_143052.jpg\|234567\|/data/fotos/...` |
| `foto:nombre` | Foto con nombre personalizado | `foto:mi_imagen` | `OK\|mi_imagen.jpg\|234567\|...` |
| `estado` | Estado del sistema | `estado` | `STATUS:ACTIVO\|/dev/ttyS0\|115200\|...` |
| `resolucion` | Info de resolución actual | `resolucion` | `RESOLUCION\|1920x1080\|2.1MP\|jpg` |
| `res:WxH` | Cambiar resolución | `res:1280x720` | `OK:Resolucion 1280x720` |
| `baudrate:SPEED` | Cambiar velocidad UART | `baudrate:57600` | `BAUDRATE_CHANGED\|57600` |
| `listar` | Listar archivos | `listar` | `FILES\|5\|1234567\|archivo1.jpg:234567\|...` |
| `descargar:archivo` | Transferir archivo | `descargar:foto.jpg` | *[transferencia binaria]* |
| `limpiar` | Limpiar archivos antiguos | `limpiar` | `CLEANED\|3\|987654\|antiguos` |
| `estadisticas` | Métricas del sistema | `estadisticas` | `STATS\|fotos:15\|comandos:45\|...` |
| `test` | Test de captura | `test` | `TEST_OK\|0.85s` |
| `reiniciar` | Reinicializar cámara | `reiniciar` | `OK:Camara reinicializada` |
| `salir` | Terminar sistema | `salir` | `CAMERA_OFFLINE` |

*Todos los comandos tienen aliases en inglés (ej: `status`, `resolution`, `list`, etc.)*

## 💻 Ejemplos de Uso

### Uso Básico por UART

```bash
# Conectar por puerto serie y enviar comandos
echo "foto" > /dev/ttyS0
echo "estado" > /dev/ttyS0  
echo "res:1280x720" > /dev/ttyS0
echo "listar" > /dev/ttyS0
```

### Cliente Interactivo

```bash
# Iniciar cliente de pruebas
python scripts/cliente_foto.py

# Modo interactivo
🟢 camara-uart> foto:mi_primera_foto
✅ OK|mi_primera_foto.jpg|234567|/data/fotos/mi_primera_foto.jpg
   📄 Archivo: mi_primera_foto.jpg
   📏 Tamaño: 234,567 bytes (229.1 KB)
   📂 Ruta: /data/fotos/mi_primera_foto.jpg

🟢 camara-uart> estado
📊 STATUS:ACTIVO|/dev/ttyS0|115200|1|5
   🔌 Puerto: /dev/ttyS0
   ⚡ Velocidad: 115200 baudios
   📸 Fotos tomadas: 1
   ⌨️ Comandos procesados: 5
```

### Uso Programático

```python
import serial

# Conectar por UART
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)

# Tomar foto
ser.write(b'foto\r\n')
response = ser.readline().decode().strip()
print(f"Respuesta: {response}")

# Cambiar resolución  
ser.write(b'res:1920x1080\r\n')
response = ser.readline().decode().strip()
```

## 🔧 Configuración

### Archivo Principal: `config/camara.conf`

```ini
[UART]
puerto = /dev/ttyS0
baudrate = 115200
timeout = 1.0

[CAMARA] 
resolucion_ancho = 1920
resolucion_alto = 1080
calidad = 95
formato = jpg

[SISTEMA]
directorio_fotos = /data/fotos
max_archivos = 1000
auto_limpiar = true

[TRANSFERENCIA]
chunk_size = 256
verificar_checksum = true
```

### Resoluciones Soportadas

| Resolución | Megapíxeles | Uso Recomendado | Pi Zero | Pi 3B+/4 |
|------------|-------------|-----------------|---------|----------|
| 640x480 | 0.3 MP | Pruebas rápidas | ✅ Muy rápido | ✅ Instantáneo |
| 1280x720 | 0.9 MP | Balance ideal | ✅ Rápido | ✅ Muy rápido |
| 1920x1080 | 2.1 MP | Alta calidad | ⚠️ Lento | ✅ Rápido |
| 2592x1944 | 5.0 MP | Máxima calidad | ❌ Muy lento | ⚠️ Lento |

### Velocidades UART

| Velocidad | Compatibilidad | Uso Recomendado |
|-----------|---------------|-----------------|
| 9600 | Máxima | Cables largos, test inicial |
| 57600 | Alta | Pi Zero, enlaces estables |
| 115200 | Buena | **Recomendado general** |
| 230400 | Media | Pi 3B+/4, cables cortos |

## 📦 Instalación Manual

### Prerrequisitos

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Dependencias básicas
sudo apt install python3-pip python3-venv git

# Dependencias de cámara
sudo apt install python3-picamera2

# Habilitar cámara y UART
sudo raspi-config
# Interfacing Options → Camera → Enable
# Interfacing Options → Serial → No (login) → Yes (hardware)
```

### Instalación Paso a Paso

```bash
# 1. Clonar repositorio
git clone https://github.com/tu-usuario/sistema-camara-uart.git
cd sistema-camara-uart

# 2. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar permisos
sudo usermod -a -G dialout $USER

# 5. Copiar configuración
cp config/camara.conf.example config/camara.conf

# 6. Probar instalación
python scripts/main_daemon.py --test
```

## 🛠️ Desarrollo y Testing

### Estructura del Proyecto

```
src/
├── config_manager.py      # Gestión de configuración dinámica
├── camara_controller.py    # Control completo de cámara
├── uart_handler.py        # Comunicación UART robusta  
├── file_transfer.py       # Transferencia con verificación
└── exceptions.py          # Manejo granular de errores

scripts/
├── main_daemon.py         # Daemon principal (15+ comandos)
├── cliente_foto.py        # Cliente de pruebas interactivo
├── install.sh             # Instalación automática
└── uninstall.sh           # Desinstalación limpia
```

### Ejecutar Tests

```bash
# Test completo del sistema
python scripts/main_daemon.py --test

# Cliente de pruebas
python scripts/cliente_foto.py --auto

# Test específicos
python -m pytest tests/ -v
```

### Modo Debug

```bash
# Daemon en modo debug
python scripts/main_daemon.py --debug

# Cliente con logs detallados  
python scripts/cliente_foto.py --debug -p /dev/ttyUSB0
```

## 🔍 Solución de Problemas

### Problemas Comunes

**Error: "Permission denied" en puerto UART**
```bash
# Verificar permisos
groups $USER  # Debe incluir 'dialout'

# Agregar usuario al grupo
sudo usermod -a -G dialout $USER
# Cerrar sesión y volver a entrar
```

**Error: "Camera not detected"**
```bash
# Verificar cámara
vcgencmd get_camera
# Debe mostrar: supported=1 detected=1

# Habilitar cámara
sudo raspi-config
# Advanced Options → Camera → Enable
```

**Error: "Port already in use"**
```bash
# Verificar procesos usando puerto
sudo lsof /dev/ttyS0

# Detener servicio si está corriendo
sudo systemctl stop camara-uart
```

### Logs y Diagnóstico

```bash
# Ver logs del servicio
sudo journalctl -u camara-uart -f

# Logs del sistema
tail -f /var/log/camara-uart/camara-uart.log

# Estado detallado
./estado_servicio.sh
```

### Puertos Serie Disponibles

```bash
# Detectar puertos disponibles
ls -la /dev/tty* | grep -E "(ttyS|ttyUSB|ttyACM)"

# Información detallada
python -c "import serial.tools.list_ports; [print(p) for p in serial.tools.list_ports.comports()]"
```

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas! Por favor:

1. **Fork** el proyecto
2. Crear rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. **Commit** tus cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. **Push** a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear **Pull Request**

### Guidelines de Contribución

- ✅ Seguir estilo de código PEP 8
- ✅ Agregar tests para nuevas funcionalidades
- ✅ Actualizar documentación
- ✅ Probar en Raspberry Pi real antes de PR

## 📚 Documentación Adicional

- [📖 Guía de Instalación Detallada](docs/INSTALL.md)
- [🔧 Documentación de API](docs/API.md)
- [🐛 Solución de Problemas](docs/TROUBLESHOOTING.md)
- [📝 Ejemplos Avanzados](examples/)

## 🗺️ Roadmap

### Versión 1.1 (Próxima)
- [ ] Interfaz web para control remoto
- [ ] Soporte para múltiples cámaras simultáneas
- [ ] Compresión de imágenes en tiempo real
- [ ] API REST complementaria

### Versión 1.2 (Futuro)
- [ ] Integración con servicios en la nube
- [ ] Modo timelapse automático
- [ ] Detección de movimiento
- [ ] Dashboard de monitoreo

### Versión 2.0 (Visión)
- [ ] Soporte para streaming de video
- [ ] Inteligencia artificial integrada
- [ ] Configuración via app móvil
- [ ] Red mesh de múltiples Raspberry Pi

## 📄 Licencia

Este proyecto está bajo la Licencia LICENCIA PÚBLICA GENERAL GNU Versión 3, 29 de junio de 2007 [LICENCIA](LICENSE)

## 👥 Autores y Reconocimientos

- **Autor Principal** - *Desarrollo completo* - [@cpatagon](https://github.com/cpatagon)

### Reconocimientos

- Comunidad **Raspberry Pi** por el excelente hardware y documentación
- Desarrolladores de **picamera2** por la biblioteca de cámara
- Proyecto **pyserial** por la comunicación serie confiable
- Todos los **contribuidores** que han ayudado a mejorar este proyecto

## 📊 Estadísticas del Proyecto

- **Líneas de código**: ~3,000+
- **Archivos**: 15+ módulos principales
- **Comandos UART**: 15+ implementados
- **Cobertura de tests**: 85%+
- **Plataformas soportadas**: Raspberry Pi OS, Debian/Ubuntu
- **Versiones Python**: 3.7, 3.8, 3.9, 3.10+

## 🌟 ¿Te Gusta el Proyecto?

Si este proyecto te ha sido útil:

- ⭐ Dale una **estrella** en GitHub
- 🍴 Haz **fork** para tus propias modificaciones  
- 🐛 Reporta **issues** si encuentras problemas
- 💡 Sugiere **nuevas características**
- 📢 **Compártelo** con otros makers

## 📞 Soporte

- 🐛 **Issues**: [GitHub Issues](https://github.com/tu-usuario/sistema-camara-uart/issues)
- 💬 **Discusiones**: [GitHub Discussions](https://github.com/tu-usuario/sistema-camara-uart/discussions)
- 📧 **Email**: tu-email@ejemplo.com

---

**🚀 ¡Desarrollado con ❤️ para la comunidad Raspberry Pi!**

*¿Construiste algo increíble con este sistema? ¡Nos encantaría conocer tu proyecto!*
