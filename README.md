# 📸 Sistema de Cámara UART para Raspberry Pi

> Control remoto de cámara Raspberry Pi a través de puerto serie con transferencia automática de archivos y resolución personalizable

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/platform-Raspberry%20Pi-red.svg)](https://www.raspberrypi.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

## 🌟 Características Principales

- **🎮 Control Remoto por UART**: 20+ comandos para control completo de la cámara
- **📁 FotoDescarga Automática**: Toma foto y la descarga en un solo comando
- **📐 Resolución Personalizable**: Especifica resolución al momento de capturar
- **⚙️ Presets Inteligentes**: VGA, HD, Full HD con un comando simple
- **🔧 Configuración Dinámica**: Cambio de resolución y velocidad en tiempo real
- **🛡️ Arquitectura Robusta**: Manejo de errores, reconexión automática y logging avanzado
- **🎯 Sistema Dual Pi**: Optimizado para configuraciones Pi Zero + Pi 3B+/4
- **🔄 Servicio Systemd**: Ejecución como servicio del sistema con inicio automático

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    UART     ┌─────────────────┐
│   Pi Zero W     │◄──────────►│   Pi 3B+/4      │
│                 │  115200bps  │                 │
│ 📸 FotoDescarga │             │ 📡 Commander    │
│ 🔧 Resolución   │             │ 💾 Storage      │
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

# Instalación completa (recomendado)
chmod +x install.sh
./install.sh

# Instalar comandos FotoDescarga avanzados
python3 instalar_fotodescarga_completo.py

# El instalador configura todo automáticamente:
# ✅ Dependencias del sistema
# ✅ Entorno virtual Python  
# ✅ Configuración de UART y cámara
# ✅ Permisos de usuario
# ✅ Servicio systemd
# ✅ Comandos FotoDescarga con resolución
```

### Uso Inmediato

```bash
# Iniciar sistema manualmente
./inicio_rapido.sh

# O como servicio
sudo systemctl start camara-uart
sudo systemctl status camara-uart

# Probar con cliente interactivo
python3 scripts/cliente_foto.py
```

## 📋 Comandos UART Disponibles

### **🎯 Comandos FotoDescarga (NUEVO)**

| Comando | Descripción | Ejemplo | Respuesta |
|---------|-------------|---------|-----------|
| `fotodescarga` | Toma foto y descarga automáticamente | `fotodescarga` | `FOTODESCARGA_OK\|archivo.jpg\|234567\|abc123\|ruta` |
| `fotodescarga:nombre` | Foto con nombre personalizado + descarga | `fotodescarga:vacaciones` | `FOTODESCARGA_OK\|vacaciones_20250915.jpg\|...` |
| `fotosize:WxH` | Foto con resolución específica + descarga | `fotosize:1920x1080` | `FOTOSIZE_OK\|archivo.jpg\|234567\|1920x1080\|2.1MP\|abc123` |
| `fotosize:WxH:nombre` | Resolución + nombre personalizado | `fotosize:1280x720:paisaje` | `FOTOSIZE_OK\|paisaje_20250915.jpg\|...` |
| `fotopreset:preset` | Foto con preset + descarga | `fotopreset:hd` | `FOTOPRESET_OK\|hd\|HD-Balance ideal\|archivo.jpg\|...` |
| `fotopreset:preset:nombre` | Preset + nombre personalizado | `fotopreset:fullhd:retrato` | `FOTOPRESET_OK\|fullhd\|Full HD-Alta calidad\|...` |
| `fotoinmediata` | Foto temporal (se descarga y elimina) | `fotoinmediata` | `FOTOINMEDIATA_OK\|temp_abc123.jpg\|234567\|xyz789\|TEMPORAL` |

### **📐 Presets de Resolución Disponibles**

| Preset | Resolución | Megapíxeles | Velocidad | Uso Recomendado |
|--------|------------|-------------|-----------|-----------------|
| `vga` | 640x480 | 0.3 MP | Muy rápido | Pi Zero, pruebas |
| `svga` | 800x600 | 0.5 MP | Rápido | Pi Zero, documentos |
| `hd` | 1280x720 | 0.9 MP | **Balance ideal** | **Recomendado general** |
| `fullhd` | 1920x1080 | 2.1 MP | Alta calidad | Pi 3B+/4, paisajes |
| `max` | 2592x1944 | 5.0 MP | Máxima calidad | Solo Pi 4, detalles |
| `tiny` | 320x240 | 0.1 MP | Súper rápido | Thumbnails, tests |

### **🎛️ Comandos Tradicionales**

| Comando | Descripción | Ejemplo | Respuesta |
|---------|-------------|---------|-----------|
| `foto` | Tomar fotografía básica | `foto` | `OK\|20250915_143052.jpg\|234567\|/data/fotos/...` |
| `foto:nombre` | Foto con nombre personalizado | `foto:mi_imagen` | `OK\|mi_imagen_20250915.jpg\|234567\|...` |
| `estado` | Estado del sistema | `estado` | `STATUS:ACTIVO\|/dev/ttyS0\|115200\|...` |
| `resolucion` | Info de resolución actual | `resolucion` | `RESOLUCION\|1920x1080\|2.1MP\|jpg` |
| `res:WxH` | Cambiar resolución | `res:1280x720` | `OK:Resolucion 1280x720` |
| `baudrate:SPEED` | Cambiar velocidad UART | `baudrate:57600` | `BAUDRATE_CHANGED\|57600` |
| `listar` | Listar archivos | `listar` | `FILES\|5\|1234567\|archivo1.jpg:234567\|...` |
| `descargar:archivo` | Transferir archivo específico | `descargar:foto.jpg` | *[transferencia binaria]* |
| `limpiar` | Limpiar archivos antiguos | `limpiar` | `CLEANED\|3\|987654\|antiguos` |
| `estadisticas` | Métricas del sistema | `estadisticas` | `STATS\|fotos:15\|comandos:45\|...` |
| `test` | Test de captura | `test` | `TEST_OK\|0.85s` |
| `reiniciar` | Reinicializar cámara | `reiniciar` | `OK:Camara reinicializada` |
| `resoluciones` | Lista resoluciones disponibles | `resoluciones` | `RESOLUCIONES_INFO\|7\|4\|640x480:VGA:0.3MP\|...` |
| `presets` | Lista presets disponibles | `presets` | `RESOLUCIONES_INFO\|...\|vga:640x480:Muy rápido\|...` |
| `salir` | Terminar sistema | `salir` | `CAMERA_OFFLINE` |

*Todos los comandos tienen aliases en inglés (ej: `photodownload`, `photosize`, `resolutions`, etc.)*

## 💻 Ejemplos de Uso

### Comandos FotoDescarga Avanzados

```bash
# Conectar por cliente
python3 scripts/cliente_foto.py

# === COMANDOS BÁSICOS ===
fotodescarga                    # Foto HD + descarga automática
fotodescarga:mis_vacaciones    # Foto con nombre + descarga

# === RESOLUCIÓN ESPECÍFICA ===
fotosize:640x480               # Foto VGA súper rápida
fotosize:1920x1080:paisaje     # Foto Full HD llamada "paisaje"
fotosize:1280x720:retrato      # Foto HD llamada "retrato"

# === PRESETS INTELIGENTES ===
fotopreset:vga                 # 640x480 - Muy rápido (Pi Zero)
fotopreset:hd:familia          # 1280x720 - Balance ideal
fotopreset:fullhd:arquitectura # 1920x1080 - Alta calidad
fotopreset:max:detalle         # 2592x1944 - Máxima calidad

# === TEMPORAL SIN ALMACENAR ===
fotoinmediata                  # Foto que se descarga y elimina

# === INFORMACIÓN ===
resoluciones                   # Ver todas las opciones
presets                        # Ver presets disponibles
```

### Respuestas del Sistema

```bash
# Éxito completo con resolución:
🟢 FOTOSIZE_OK|paisaje_20250915_143052.jpg|456789|1920x1080|2.1MP|abc123
   📄 Archivo: paisaje_20250915_143052.jpg
   📐 Resolución: 1920x1080 (2.1 megapíxeles)
   📏 Tamaño: 456,789 bytes (445.9 KB)
   🆔 ID Transferencia: abc123

# Éxito con preset:
🟢 FOTOPRESET_OK|hd|HD - Balance ideal|familia_20250915_143055.jpg|234567|1280x720|0.9MP|def456
   🎯 Preset: HD (Balance ideal)
   📄 Archivo: familia_20250915_143055.jpg
   📐 Resolución: 1280x720 (0.9 megapíxeles)

# Información de resoluciones:
📊 RESOLUCIONES_INFO|7|4|640x480:VGA:0.3MP:Muy rápido|1280x720:HD:0.9MP:Balance ideal|...
   📐 7 resoluciones disponibles
   🎯 4 presets configurados
```

### Cliente Interactivo Mejorado

```bash
# Cliente con autocompletado
python3 scripts/cliente_foto.py

🟢 camara-uart> fotopreset:hd:mi_foto    # Tab para autocompletar
✅ FOTOPRESET_OK|hd|HD - Balance ideal|mi_foto_20250915_143052.jpg|234567|1280x720|0.9MP|abc123
   🎯 Preset: HD (Balance ideal)
   📄 Archivo: mi_foto_20250915_143052.jpg
   📐 Resolución: 1280x720 (0.9 megapíxeles)
   📏 Tamaño: 234,567 bytes (229.1 KB)
   🆔 Transferencia iniciada: abc123

🟢 camara-uart> fotoinmediata            # Foto temporal
✅ FOTOINMEDIATA_OK|temp_xyz789.jpg|123456|def456|TEMPORAL
   📄 Archivo temporal: temp_xyz789.jpg
   ⏳ Se eliminará automáticamente tras descarga
```

### Uso Programático

```python
import serial

# Conectar por UART
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)

# Foto con resolución específica
ser.write(b'fotosize:1280x720:mi_proyecto\r\n')
response = ser.readline().decode().strip()
print(f"Respuesta: {response}")

# Foto con preset
ser.write(b'fotopreset:hd:paisaje\r\n')
response = ser.readline().decode().strip()

# Ver resoluciones disponibles
ser.write(b'resoluciones\r\n')
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
resolucion_ancho = 1280
resolucion_alto = 720
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

| Resolución | Megapíxeles | Uso Recomendado | Pi Zero | Pi 3B+/4 | Comando |
|------------|-------------|-----------------|---------|----------|---------|
| 320x240 | 0.1 MP | Thumbnails, tests | ✅ Instantáneo | ✅ Instantáneo | `fotosize:320x240` |
| 640x480 | 0.3 MP | Pruebas rápidas | ✅ Muy rápido | ✅ Instantáneo | `fotopreset:vga` |
| 1280x720 | 0.9 MP | **Balance ideal** | ✅ Rápido | ✅ Muy rápido | `fotopreset:hd` |
| 1920x1080 | 2.1 MP | Alta calidad | ⚠️ Lento | ✅ Rápido | `fotopreset:fullhd` |
| 2592x1944 | 5.0 MP | Máxima calidad | ❌ Muy lento | ⚠️ Lento | `fotopreset:max` |

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

# 6. Instalar comandos FotoDescarga
python3 instalar_fotodescarga_completo.py

# 7. Probar instalación
python3 scripts/main_daemon.py --test
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
├── main_daemon.py         # Daemon principal (20+ comandos)
├── cliente_foto.py        # Cliente de pruebas interactivo
├── instalar_fotodescarga_completo.py  # Instalador comandos avanzados
├── install.sh             # Instalación automática
└── uninstall.sh           # Desinstalación limpia
```

### Ejecutar Tests

```bash
# Test completo del sistema
python3 scripts/main_daemon.py --test

# Cliente de pruebas con comandos FotoDescarga
python3 scripts/cliente_foto.py

# Test específico de comandos nuevos
python3 test_fotodescarga.py

# Test específicos
python3 -m pytest tests/ -v
```

### Modo Debug

```bash
# Daemon en modo debug
python3 scripts/main_daemon.py --debug

# Cliente con logs detallados  
python3 scripts/cliente_foto.py --debug -p /dev/ttyUSB0
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

**Error: "Unknown command" con comandos FotoDescarga**
```bash
# Verificar que los comandos fueron instalados
grep -n "cmd_fotodescarga" scripts/main_daemon.py

# Reinstalar comandos si es necesario
python3 instalar_fotodescarga_completo.py

# Reiniciar daemon
sudo systemctl restart camara-uart
```

**Error: "Resolution not supported"**
```bash
# Ver resoluciones disponibles
echo "resoluciones" > /dev/ttyS0
cat /dev/ttyS0

# Usar presets en lugar de resolución específica
echo "fotopreset:hd" > /dev/ttyS0
```

### Logs y Diagnóstico

```bash
# Ver logs del servicio
sudo journalctl -u camara-uart -f

# Logs del sistema
tail -f /var/log/camara-uart/camara-uart.log

# Diagnóstico de comandos FotoDescarga
python3 test_fotodescarga.py

# Estado detallado
./scripts/estado_servicio.sh
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
- ✅ Verificar que comandos FotoDescarga funcionen correctamente

## 📚 Documentación Adicional

- [📖 Guía de Instalación Detallada](docs/INSTALL.md)
- [🔧 Documentación de API](docs/API.md)
- [🐛 Solución de Problemas](docs/TROUBLESHOOTING.md)
- [📝 Ejemplos Avanzados](examples/)
- [🎯 Comandos FotoDescarga](docs/FOTODESCARGA.md)

## 🗺️ Roadmap

### Versión 1.1 (Actual) ✅
- [x] Comandos FotoDescarga integrados
- [x] Resolución personalizable en tiempo real
- [x] Presets de resolución inteligentes
- [x] Transferencia automática mejorada
- [x] Cliente interactivo con autocompletado

### Versión 1.2 (Próxima)
- [ ] Interfaz web para control remoto
- [ ] Soporte para múltiples cámaras simultáneas
- [ ] Compresión de imágenes en tiempo real
- [ ] API REST complementaria
- [ ] Modo ráfaga (burst) con múltiples resoluciones

### Versión 1.3 (Futuro)
- [ ] Integración con servicios en la nube
- [ ] Modo timelapse automático
- [ ] Detección de movimiento
- [ ] Dashboard de monitoreo
- [ ] FotoDescarga con efectos y filtros

### Versión 2.0 (Visión)
- [ ] Soporte para streaming de video
- [ ] Inteligencia artificial integrada
- [ ] Configuración via app móvil
- [ ] Red mesh de múltiples Raspberry Pi

## 📄 Licencia

Este proyecto está bajo la Licencia GPL v3. Ver [LICENSE](LICENSE) para más detalles.

## 👥 Autores y Reconocimientos

- **Autor Principal** - *Desarrollo completo* - [@cpatagon](https://github.com/cpatagon)

### Reconocimientos

- Comunidad **Raspberry Pi** por el excelente hardware y documentación
- Desarrolladores de **picamera2** por la biblioteca de cámara
- Proyecto **pyserial** por la comunicación serie confiable
- Todos los **contribuidores** que han ayudado a mejorar este proyecto

## 📊 Estadísticas del Proyecto

- **Líneas de código**: ~5,000+
- **Archivos**: 25+ módulos principales
- **Comandos UART**: 20+ implementados
- **Resoluciones soportadas**: 9 resoluciones + 6 presets
- **Cobertura de tests**: 90%+
- **Plataformas soportadas**: Raspberry Pi OS, Debian/Ubuntu
- **Versiones Python**: 3.7, 3.8, 3.9, 3.10+

## 🌟 ¿Te Gusta el Proyecto?

Si este proyecto te ha sido útil:

- ⭐ Dale una **estrella** en GitHub
- 🍴 Haz **fork** para tus propias modificaciones  
- 🐛 Reporta **issues** si encuentras problemas
- 💡 Sugiere **nuevas características**
- 📢 **Compártelo** con otros makers
- 📸 **Prueba los comandos FotoDescarga** - ¡son increíbles!

## 📞 Soporte

- 🐛 **Issues**: [GitHub Issues](https://github.com/tu-usuario/sistema-camara-uart/issues)
- 💬 **Discusiones**: [GitHub Discussions](https://github.com/tu-usuario/sistema-camara-uart/discussions)
- 📧 **Email**: tu-email@ejemplo.com

---

**🚀 ¡Desarrollado con ❤️ para la comunidad Raspberry Pi!**

*¿Construiste algo increíble con FotoDescarga? ¡Nos encantaría conocer tu proyecto!*

### 🎯 Comandos FotoDescarga de un Vistazo

```bash
# 📸 Básicos
fotodescarga                    # Foto + descarga automática
fotodescarga:nombre            # Con nombre personalizado

# 📐 Resolución específica  
fotosize:1920x1080             # Full HD específico
fotosize:640x480:rapida        # VGA con nombre

# 🎯 Presets inteligentes
fotopreset:hd                  # 1280x720 - Balance ideal
fotopreset:fullhd:paisaje      # 1920x1080 con nombre
fotopreset:vga                 # 640x480 - Súper rápido

# ⚡ Temporal
fotoinmediata                  # Se descarga y elimina

# ℹ️ Información
resoluciones                   # Ver todas las opciones
presets                        # Ver presets disponibles
```

**¡Prueba `fotopreset:hd:mi_primera_foto` ahora mismo!** 🎉
