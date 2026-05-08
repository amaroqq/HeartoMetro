# =============================================================================
#  calculations.py  –  Signal processing, HRV math, HR classification
#  HEARTOMETRO  |  Group 1  |  2025
# =============================================================================

import math
import time
import os
import ujson as json
from machine import Pin, ADC
from fifo import Fifo
from piotimer import Piotimer

from config import (
    ENC_TABLE, ROT_DEBOUNCE_MS,
    PPG_ADC_PIN, LED_HEARTBEAT_PIN,
    SAMPLE_RATE, EMA_ALPHA, WINDOW_SIZE,
    FINGER_THRESHOLD, MIN_RRI_MS, MAX_RRI_MS,
    STATE_MEASURE,
)


# =============================================================================
#  ROTARY ENCODER
# =============================================================================
class RotaryEncoder:
    """Quadrature decoder.  Puts +1 (CW) or -1 (CCW) into a Fifo."""

    def __init__(self, pin_a, pin_b, fifo):
        self._a    = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self._b    = Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self._fifo = fifo
        self._last = (self._a.value() << 1) | self._b.value()
        self._pos  = 0
        self._last_irq = time.ticks_ms()
        self._a.irq(self._isr, Pin.IRQ_RISING | Pin.IRQ_FALLING, hard=True)
        self._b.irq(self._isr, Pin.IRQ_RISING | Pin.IRQ_FALLING, hard=True)

    def _isr(self, _pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_irq) < ROT_DEBOUNCE_MS:
            return
        self._last_irq = now
        cur = (self._a.value() << 1) | self._b.value()
        self._pos += ENC_TABLE[(self._last << 2) | cur]
        self._last = cur
        if self._pos >= 4:
            try: self._fifo.put(1)
            except RuntimeError: pass
            self._pos = 0
        elif self._pos <= -4:
            try: self._fifo.put(-1)
            except RuntimeError: pass
            self._pos = 0


# =============================================================================
#  PPG SENSOR FIFO  (timer-driven ADC sampling)
# =============================================================================
class SensorFifo(Fifo):
    def __init__(self, size, adc_pin):
        super().__init__(size)
        self._adc = ADC(adc_pin)

    def handler(self, _tid):
        try: self.put(self._adc.read_u16())
        except RuntimeError: pass


# =============================================================================
#  SIGNAL PROCESSOR
#  Holds all EMA filter state, min/max tracking and beat detection.
#  Call process_sample() for every raw ADC value from the timer.
# =============================================================================
class SignalProcessor:

    def __init__(self, led_pin, state_ref):
        """
        led_pin   – GPIO number for the heartbeat LED
        state_ref – a 1-element list [STATE_*] shared with the app so beat
                    detection knows when measurement is active
        """
        self.led        = Pin(led_pin, Pin.OUT)
        self._state_ref = state_ref   # mutable reference: [app.state]

        self._filtered     = 0.0
        self._warmed       = False
        self._cycle        = 0
        self._hist         = [0] * WINDOW_SIZE
        self._hist_idx     = 0

        self.min_val       = 0
        self.max_val       = 65535
        self.span          = 0
        self._threshold    = 0.0

        self._beat_active  = False
        self._last_beat_ms = 0

        self.rri_buffer    = []   # collected RRI values in ms
        self.filtered_data = 0.0  # public: current smoothed value (for waveform)

    def reset_measurement(self):
        """Clear RRI buffer before a new measurement."""
        self.rri_buffer    = []
        self._beat_active  = False
        self._last_beat_ms = 0

    def process_sample(self, raw):
        if not self._warmed:
            self._filtered = float(raw)
            self._warmed   = True
        else:
            self._filtered = EMA_ALPHA * raw + (1.0 - EMA_ALPHA) * self._filtered

        self.filtered_data = self._filtered
        self._hist[self._hist_idx] = int(self._filtered)
        self._hist_idx = (self._hist_idx + 1) % WINDOW_SIZE
        self._cycle   += 1

        # Update min/max every 50 samples
        if self._cycle % 50 == 0:
            valid = self._hist if self._cycle >= WINDOW_SIZE else self._hist[:self._hist_idx]
            if valid:
                self.min_val = min(valid)
                self.max_val = max(valid)
                self.span    = self.max_val - self.min_val

        self._beat_detect()

    def _beat_detect(self):
        if self.span < FINGER_THRESHOLD:
            self._beat_active = False
            self.led.off()
            return

        self._threshold = (self.max_val + self.min_val) / 2.0
        hysteresis      = max(1, self.span) * 0.05

        if self._state_ref[0] == STATE_MEASURE and self._cycle > WINDOW_SIZE // 4:
            if self._filtered >= self._threshold and not self._beat_active:
                self._beat_active = True
                self.led.on()
                now = time.ticks_ms()
                if self._last_beat_ms > 0:
                    rri = time.ticks_diff(now, self._last_beat_ms)
                    if MIN_RRI_MS <= rri <= MAX_RRI_MS:
                        self.rri_buffer.append(rri)
                self._last_beat_ms = now
            elif self._filtered < (self._threshold - hysteresis):
                self._beat_active = False
                self.led.off()


# =============================================================================
#  HRV CALCULATIONS
# =============================================================================
def compute_hrv(rri):
    """
    Return (mean_bpm, sdnn_ms, rmssd_ms) from a list of RRI values in ms.
    Returns (0, 0, 0) if fewer than 2 samples.
    """
    n = len(rri)
    if n < 2:
        return 0, 0, 0
    mean_rri = sum(rri) / n
    mean_bpm = int(60_000 / mean_rri) if mean_rri > 0 else 0
    sdnn     = int(math.sqrt(sum((x - mean_rri) ** 2 for x in rri) / n))
    rmssd    = int(math.sqrt(
        sum((rri[i + 1] - rri[i]) ** 2 for i in range(n - 1)) / (n - 1)
    ))
    return mean_bpm, sdnn, rmssd

def hr_label(bpm, age, gender_is_male):
    """
    Classify BPM relative to age/gender-adjusted maximum HR (Tanaka formula).
    Returns a short string label.
    """
    if bpm <= 0:
        return "N/A"
    max_hr = 208 - (0.7 * age)
    pct    = bpm / max_hr * 100
    if pct < 40:   return "Very Low"
    if pct < 55:   return "Low"
    if pct < 70:   return "Normal"
    if pct < 85:   return "Elevated"
    return "High"


# =============================================================================
#  HISTORY STORE  (last 10 measurements in RAM, last 3 HRV in flash)
# =============================================================================
class HistoryStore:
    MAX = 10

    def __init__(self):
        self._records = []

    def add(self, rec):
        """Add a dict with keys: time, mode, bpm, sdnn, rmssd, name."""
        self._records.insert(0, rec)
        if len(self._records) > self.MAX:
            self._records.pop()
            
        if rec.get("mode") == "HRV":
            self._rotate_and_save()

    def update_latest_kubios(self, analysis):
        if self._records:
            self._records[0]["kubios"] = analysis
            # If the record is HRV, update the file on flash to include kubios data
            if self._records[0].get("mode") == "HRV":
                try:
                    with open("hrv_1.json", "w") as f:
                        json.dump(self._records[0], f)
                except Exception:
                    pass

    def _rotate_and_save(self):
        # Rotate the last 3 files
        try: os.remove("hrv_3.json")
        except OSError: pass
        
        try: os.rename("hrv_2.json", "hrv_3.json")
        except OSError: pass
        
        try: os.rename("hrv_1.json", "hrv_2.json")
        except OSError: pass
        
        try:
            # Add an exact NTP Unix timestamp explicitly before saving
            # MicroPython epoch is 2000-01-01, standard unix is 1970, diff is 946684800
            # ntptime sets the time correctly, we just offset it to standardized unix
            self._records[0]["ntp_timestamp"] = int(time.time() + 946684800)
            with open("hrv_1.json", "w") as f:
                json.dump(self._records[0], f)
        except Exception as e:
            print("History save err:", e)

    def all(self):
        return self._records

    def count(self):
        return len(self._records)
