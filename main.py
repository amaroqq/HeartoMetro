# =============================================================================
#  main.py  –  Entry point.  Wires all modules together and runs the loop.
#  HEARTOMETRO  |  Group 1  |  2025
#
#  File layout:
#    main.py          – this file: hardware init + main loop
#    config.py        – all pin numbers, constants, states, language strings
#    calculations.py  – signal processing, HRV math, HistoryStore
#    mqtt_wifi.py     – WiFi connection, NTP sync, MQTT client
#    menu.py          – all UI screens + input handling
# =============================================================================

import time
import micropython
from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
from fifo import Fifo
from piotimer import Piotimer

from config import (
    I2C_BUS, I2C_SCL_PIN, I2C_SDA_PIN, DISPLAY_I2C_FREQ,
    DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_I2C_ADDR,
    LED_HEARTBEAT_PIN, PPG_ADC_PIN, SAMPLE_RATE,
    STATE_BOOT, STATE_MEASURE,
)
from calculations import SignalProcessor, SensorFifo, HistoryStore
from mqtt_wifi import NetworkManager
from menu import UI

micropython.alloc_emergency_exception_buf(200)


# =============================================================================
#  HARDWARE INITIALISATION
# =============================================================================
def init_oled():
    """
    Create I2C bus and SSD1306 display.
    Auto-detects I2C address and falls back to 100 kHz if 400 kHz fails.
    """
    i2c = I2C(I2C_BUS,
              scl=Pin(I2C_SCL_PIN),
              sda=Pin(I2C_SDA_PIN),
              freq=DISPLAY_I2C_FREQ)
    devices = i2c.scan()
    if not devices:
        i2c = I2C(I2C_BUS,
                  scl=Pin(I2C_SCL_PIN),
                  sda=Pin(I2C_SDA_PIN),
                  freq=100_000)
        devices = i2c.scan()

    if DISPLAY_I2C_ADDR in devices:
        addr = DISPLAY_I2C_ADDR
    elif devices:
        addr = devices[0]
    else:
        raise OSError("OLED not found. Check SDA/SCL wiring.")

    return SSD1306_I2C(DISPLAY_WIDTH, DISPLAY_HEIGHT, i2c, addr=addr)


# =============================================================================
#  MAIN
# =============================================================================
def main():
    # ---- OLED ----
    oled = init_oled()
    oled.fill(0)
    oled.text("HeartoMetro", 15, 26)
    oled.text("Loading...",   20, 40)
    oled.show()

    # ---- Shared state  (1-element list so all modules share one reference) ----
    app_state = [STATE_BOOT]

    # ---- Signal processor  (needs state ref so beat detect is active only in STATE_MEASURE) ----
    sig = SignalProcessor(LED_HEARTBEAT_PIN, app_state)

    # ---- Sensor FIFO + timer ----
    sensor = SensorFifo(150, PPG_ADC_PIN)
    tmr    = Piotimer(mode=Piotimer.PERIODIC,
                      freq=SAMPLE_RATE,
                      callback=sensor.handler)

    # ---- History ----
    history = HistoryStore()

    # ---- Network manager  (needs app proxy for readiness/stress/state writes) ----
    class _AppProxy:
        """Minimal proxy so NetworkManager can write back results."""
        def __init__(self):
            self.readiness = "--"
            self.stress    = "--"
        @property
        def state(self):     return app_state[0]
        @state.setter
        def state(self, v):  app_state[0] = v

    app_proxy = _AppProxy()
    net = NetworkManager(app_proxy)

    # ---- UI (owns all screen logic and the InputManager) ----
    ui = UI(oled, sig, net, history, app_state)

    # Link proxy results back to UI so results screen can read them
    # (ui.readiness / ui.stress are set by NetworkManager via app_proxy,
    #  but we also need them to be the same objects → share via proxy)
    # We patch UI.readiness/stress to delegate to app_proxy:
    #   Simpler: just let NetworkManager write ui.readiness / ui.stress directly.
    net._app = ui          # replace proxy with full UI object (UI has all needed attrs)

    # ---- Timing ----
    last_ui  = time.ticks_ms()
    last_net = time.ticks_ms()

    try:
        while True:
            # 1. Drain ADC FIFO as fast as possible
            while not sensor.empty():
                sig.process_sample(sensor.get())

            now = time.ticks_ms()

            # 2. UI task (~12 FPS)
            if time.ticks_diff(now, last_ui) >= 80:
                ui.tick()
                last_ui = now

            # 3. Network task (~10 Hz, only when WiFi is up)
            if ui.wifi_ok and time.ticks_diff(now, last_net) >= 100:
                net.tick()
                last_net = now

            time.sleep_ms(2)

    except KeyboardInterrupt:
        print("[Heartometro] Stopped.")
    finally:
        tmr.deinit()
        sig.led.off()
        oled.fill(0)
        oled.show()
        net.disconnect()


# =============================================================================
#  ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    main()

