import time
import serial

PORT = "COM5"

ser = serial.Serial(
    port=PORT,
    baudrate=115200,
    timeout=1.0,
    write_timeout=2.0,
)

print("Opened", PORT)
time.sleep(2.0)

def read_for(seconds):
    end = time.time() + seconds
    while time.time() < end:
        line = ser.readline()
        if line:
            print("<<", line.decode("utf-8", errors="replace").strip())

def send(cmd):
    print(">>", cmd)
    ser.write((cmd + "\n").encode("utf-8"))
    ser.flush()

read_for(3.0)

send("SET:1,0,0,0,0,0")
read_for(3.0)

send("SET:0,1,0,0,0,0")
read_for(3.0)

ser.close()
print("Closed")