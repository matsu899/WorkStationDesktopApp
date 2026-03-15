# app/esp_controller.py

from __future__ import annotations

import time
from typing import Iterable, Optional, List

import serial
import serial.tools.list_ports

from PyQt6.QtCore import QObject, pyqtSignal, QThread


NUM_SECTIONS = 6


class EspReaderThread(QThread):
    line_received = pyqtSignal(str)
    connection_lost = pyqtSignal(str)

    def __init__(self, ser: serial.Serial):
        super().__init__()
        self._ser = ser
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            try:
                if self._ser is None or not self._ser.is_open:
                    self.connection_lost.emit("Serial port is closed.")
                    return

                raw = self._ser.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    self.line_received.emit(line)

            except serial.SerialException as e:
                self.connection_lost.emit(f"Serial error: {e}")
                return
            except Exception as e:
                self.connection_lost.emit(f"Unexpected serial read error: {e}")
                return


class EspController(QObject):
    gate_triggered = pyqtSignal(int)      # 1..6
    ready_received = pyqtSignal()
    state_received = pyqtSignal(list)     # [bool, bool, ...]
    ok_received = pyqtSignal(str)
    error_received = pyqtSignal(str)
    log_message = pyqtSignal(str)
    connected_changed = pyqtSignal(bool)

    def __init__(
        self,
        port_name: Optional[str] = None,
        baudrate: int = 115200,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.port_name = port_name
        self.baudrate = baudrate

        self._ser: Optional[serial.Serial] = None
        self._reader: Optional[EspReaderThread] = None
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @staticmethod
    def list_ports() -> List[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect_port(self, port_name: Optional[str] = None) -> bool:
        if port_name:
            self.port_name = port_name

        if not self.port_name:
            self.error_received.emit("No COM port selected.")
            return False

        self.disconnect_port()

        try:
            self._ser = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                timeout=0.2,
                write_timeout=0.5,
            )

            # Give ESP some time after opening port
            time.sleep(0.2)

            self._reader = EspReaderThread(self._ser)
            self._reader.line_received.connect(self._handle_line)
            self._reader.connection_lost.connect(self._handle_connection_lost)
            self._reader.start()

            self._set_connected(True)
            self.log_message.emit(f"Connected to ESP on {self.port_name} @ {self.baudrate}.")
            return True

        except serial.SerialException as e:
            self._ser = None
            self.error_received.emit(f"Could not open {self.port_name}: {e}")
            self._set_connected(False)
            return False
        except Exception as e:
            self._ser = None
            self.error_received.emit(f"Unexpected connect error: {e}")
            self._set_connected(False)
            return False

    def disconnect_port(self):
        if self._reader is not None:
            self._reader.stop()
            self._reader.wait(1000)
            self._reader = None

        if self._ser is not None:
            try:
                if self._ser.is_open:
                    self._ser.close()
            except Exception:
                pass
            self._ser = None

        if self._is_connected:
            self.log_message.emit("ESP disconnected.")

        self._set_connected(False)

    def send_raw(self, command: str) -> bool:
        if not self._ser or not self._ser.is_open:
            self.error_received.emit("ESP is not connected.")
            return False

        try:
            msg = command.strip() + "\n"
            self._ser.write(msg.encode("utf-8"))
            self._ser.flush()
            self.log_message.emit(f">> {command.strip()}")
            return True
        except serial.SerialException as e:
            self.error_received.emit(f"Failed to send command: {e}")
            self.disconnect_port()
            return False
        except Exception as e:
            self.error_received.emit(f"Unexpected send error: {e}")
            return False

    def clear_sections(self) -> bool:
        return self.send_raw("CLR")

    def all_on(self) -> bool:
        return self.send_raw("ALLON")

    def set_sections_mask(self, mask: Iterable[bool]) -> bool:
        values = list(mask)
        if len(values) != NUM_SECTIONS:
            self.error_received.emit(f"Expected {NUM_SECTIONS} section values.")
            return False

        payload = ",".join("1" if x else "0" for x in values)
        return self.send_raw(f"SET:{payload}")

    def set_sections_by_numbers(self, sections: Iterable[int]) -> bool:
        mask = [False] * NUM_SECTIONS
        for s in sections:
            if 1 <= s <= NUM_SECTIONS:
                mask[s - 1] = True
            else:
                self.error_received.emit(f"Invalid section number: {s}")
                return False

        return self.set_sections_mask(mask)

    def request_sync_test(self) -> bool:
        # optional helper if you later add e.g. PING to ESP
        return self.send_raw("CLR")

    def _handle_line(self, line: str):
        self.log_message.emit(f"<< {line}")

        if line == "READY":
            self.ready_received.emit()
            return

        if line.startswith("TRIG:"):
            payload = line[5:].strip()
            try:
                section = int(payload)
                if 1 <= section <= NUM_SECTIONS:
                    self.gate_triggered.emit(section)
                else:
                    self.error_received.emit(f"Received invalid TRIG value: {line}")
            except ValueError:
                self.error_received.emit(f"Failed to parse trigger message: {line}")
            return

        if line.startswith("STATE:"):
            payload = line[6:].strip()
            try:
                tokens = [x.strip() for x in payload.split(",")]
                if len(tokens) != NUM_SECTIONS:
                    raise ValueError("wrong token count")

                state = []
                for t in tokens:
                    if t == "1":
                        state.append(True)
                    elif t == "0":
                        state.append(False)
                    else:
                        raise ValueError(f"invalid token {t}")

                self.state_received.emit(state)
            except Exception:
                self.error_received.emit(f"Failed to parse state message: {line}")
            return

        if line.startswith("OK:"):
            self.ok_received.emit(line)
            return

        if line.startswith("ERR:"):
            self.error_received.emit(line)
            return

    def _handle_connection_lost(self, message: str):
        self.error_received.emit(message)
        self.disconnect_port()

    def _set_connected(self, value: bool):
        if self._is_connected != value:
            self._is_connected = value
            self.connected_changed.emit(value)