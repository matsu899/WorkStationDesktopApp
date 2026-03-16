from app.esp_controller import EspController
import time

esp = EspController(port_name="COM4", baudrate=115200)

esp.log_message.connect(print)
esp.error_received.connect(lambda m: print("[ESP ERROR]", m))
esp.ok_received.connect(lambda m: print("[ESP OK]", m))
esp.ready_received.connect(lambda: print("[ESP] READY"))
esp.state_received.connect(lambda s: print("[ESP STATE]", s))
esp.gate_triggered.connect(lambda g: print("[ESP TRIG]", g))

print("Trying connect...")
ok = esp.connect_port()
print("Connect result:", ok)
print("Connected:", esp.is_connected)

time.sleep(2)

if ok:
    esp.all_on()
    time.sleep(1)
    esp.clear_sections()
    time.sleep(1)
    esp.disconnect_port()