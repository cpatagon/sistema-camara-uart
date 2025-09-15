# cliente_transfer.py
import serial

def recibir_archivo(puerto="/dev/ttyUSB0", baudrate=115200):
    ser = serial.Serial(puerto, baudrate, timeout=2)

    # Esperar header
    header = ser.readline().decode().strip()
    print(f"Header recibido: {header}")
    timestamp, size = header.split("|")
    size = int(size)

    # Confirmar READY
    ser.write(b"READY\n")

    # Recibir chunks
    recibido = b""
    while len(recibido) < size:
        chunk = ser.read(256)
        if not chunk:
            break
        recibido += chunk
        ser.write(b"ACK\n")

    # Confirmar final
    ser.write(b"DONE\n")

    # Mensaje final
    resp = ser.readline().decode().strip()
    print(f"Servidor: {resp}")

    # Guardar archivo
    with open(f"recibido_{timestamp}.jpg", "wb") as f:
        f.write(recibido)
    print("Archivo guardado correctamente")

if __name__ == "__main__":
    recibir_archivo()
