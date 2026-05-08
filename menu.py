# =============================================================================
#  menu.py  –  All UI screens, input reading and display helpers
#  HEARTOMETRO  |  Group 1  |  2025
# =============================================================================

import time
import framebuf
from machine import Pin
from fifo import Fifo

from config import (
    ROT_A_PIN, ROT_B_PIN, ROT_PUSH_PIN,
    DISPLAY_WIDTH, DISPLAY_HEIGHT, LANG_CODES, UI_TEXTS,
    BOOT_INTERVALS, BOOT_PULSES, MEAS_DURATION_MS,
    STATE_BOOT, STATE_SETUP_NAME, STATE_SETUP_AGE, STATE_SETUP_GENDER,
    STATE_PROFILE_OK, STATE_MENU, STATE_ANALYSIS, STATE_USER,
    STATE_HELP, STATE_LANGUAGES, STATE_HISTORY, STATE_SETTINGS,
    STATE_SYNC_PROFILE, STATE_HISTORY_DETAIL,
    STATE_WIFI_CHECK, STATE_MEASURE, STATE_ANALYZE, STATE_RESULTS,
    MODE_BPM, MODE_HRV,
)
from calculations import RotaryEncoder, compute_hrv, hr_label

# =============================================================================
#  HEART BITMAPS  (16 × 16, MONO_HLSB)
# =============================================================================
_heart_big = bytearray([
    0x00,0x00,0x1C,0x38,0x3E,0x7C,0x7F,0xFE,
    0x7F,0xFE,0x7F,0xFE,0x3F,0xFC,0x1F,0xF8,
    0x0F,0xF0,0x07,0xE0,0x03,0xC0,0x01,0x80,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
])
_heart_small = bytearray([
    0x00,0x00,0x00,0x00,0x00,0x00,0x0C,0x30,
    0x1E,0x78,0x1E,0x78,0x0F,0xF0,0x07,0xE0,
    0x03,0xC0,0x01,0x80,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
])
FB_HEART_BIG   = framebuf.FrameBuffer(_heart_big,   16, 16, framebuf.MONO_HLSB)
FB_HEART_SMALL = framebuf.FrameBuffer(_heart_small, 16, 16, framebuf.MONO_HLSB)


# =============================================================================
#  LOW-LEVEL DISPLAY HELPERS
# =============================================================================
def draw_scrollable_menu(oled, title, items, selected, visible=3):
    oled.text(title, 0, 0)
    oled.hline(0, 10, DISPLAY_WIDTH, 1)
    n     = len(items)
    start = max(0, min(selected - 1, n - visible))
    end   = min(n, start + visible)
    for idx in range(start, end):
        prefix = ">" if idx == selected else " "
        oled.text("{} {}".format(prefix, items[idx]), 0, 14 + (idx - start) * 16)
    if n > visible:
        bar_h = int(DISPLAY_HEIGHT * visible / n)
        bar_y = int((DISPLAY_HEIGHT - 14) * selected / n) + 14
        oled.fill_rect(127, bar_y, 1, bar_h, 1)


# =============================================================================
#  INPUT MANAGER
#  Reads encoder once per UI tick and differentiates between Short and Long Press
# =============================================================================
class InputManager:

    def __init__(self):
        self._enc_sw      = Pin(ROT_PUSH_PIN, Pin.IN, Pin.PULL_UP)
        self._enc_fifo    = Fifo(30)
        self._encoder     = RotaryEncoder(ROT_A_PIN, ROT_B_PIN, self._enc_fifo)

        # debounce state
        self._enc_sw_last = 1
        self._enc_sw_fell = 0
        self._enc_sw_used = False

    def read(self):
        """Return (delta, short_press, long_press).  Call exactly once per tick."""
        sp, lp = self._read_sw()
        return self._drain_encoder(), sp, lp

    def _drain_encoder(self):
        total = 0
        aux = 0
        while self._enc_fifo.has_data():
            aux = self._enc_fifo.get()
            if aux == 65535: aux = -1
            total += aux
        if total > 0: return -1
        if total < 0: return 1
        return 0

    def _read_sw(self):
        val = self._enc_sw.value()
        now = time.ticks_ms()
        sp = False
        lp = False

        if val == 0 and self._enc_sw_last == 1:
            self._enc_sw_fell = now
            self._enc_sw_used = False

        if val == 0 and not self._enc_sw_used:
            # Trigger long press while holding down
            if time.ticks_diff(now, self._enc_sw_fell) >= 600:
                self._enc_sw_used = True
                lp = True
        elif val == 1 and self._enc_sw_last == 0:
            # Trigger short press upon release if held briefly
            if not self._enc_sw_used:
                if time.ticks_diff(now, self._enc_sw_fell) >= 50:
                    sp = True

        self._enc_sw_last = val
        return sp, lp


# =============================================================================
#  UI  (all screens)
# =============================================================================
class UI:

    def __init__(self, oled, sig, net, history, app_state):
        self.oled      = oled
        self.sig       = sig
        self.net       = net
        self.history   = history
        self._st       = app_state

        self._input    = InputManager()

        # ---- User profile ----
        self.user_name       = "AAA"
        self.user_age        = 25
        self.user_gender_idx = 0
        self.user_gender     = ""

        # ---- Language & settings ----
        self.lang_idx    = 0
        self.lang        = LANG_CODES[0]
        self.boot_speed  = 2
        self.beep_on     = False

        # ---- Results ----
        self.local_bpm   = 0
        self.local_sdnn  = 0
        self.local_rmssd = 0
        self.hr_lbl      = "--"
        self.readiness   = "--"
        self.stress      = "--"
        self.wifi_ok     = False

        # ---- Boot animation ----
        self._pulse_frame = 0
        self._pulse_tick  = time.ticks_ms()
        self._boot_done   = False

        # ---- Measurement ----
        self.measure_mode = MODE_BPM
        self._meas_start  = 0
        self._post_done   = False
        self._wave_buf    = [32] * 64
        self._wave_idx    = 0
        self._wave_tick   = 0

        # ---- Menu / navigation ----
        self._menu_sel    = 0
        self._sub_sel     = 0
        self._settings_sel= 0
        self._splash_end  = 0
        self._hist_page   = 0
        self._detail_sel  = 0

        # ---- Name entry ----
        self._name_chars  = [ord('A'), ord('A'), ord('A')]
        self._name_pos    = 0

        # ---- Profile editor sub-phase ----
        self._user_phase  = 0

        # ---- WiFi check timing ----
        self._wifi_start   = 0
        self._wifi_timeout = 6000
        self._sync_start   = 0

        self._sync_gender_label()

    # ------------------------------------------------------------------
    #  HELPERS
    # ------------------------------------------------------------------
    def _t(self):
        return UI_TEXTS[self.lang]

    def _sync_gender_label(self):
        t = self._t()
        self.user_gender = [t["gender_m"], t["gender_f"]][self.user_gender_idx]

    def _gender_is_male(self):
        return self.user_gender in {UI_TEXTS[l]["gender_m"] for l in LANG_CODES}

    def _name_str(self):
        return "".join(chr(c) for c in self._name_chars)

    def _formatted_time(self):
        lt = time.localtime()
        return "{:02d}/{:02d}/{:04d} {:02d}:{:02d}".format(
            lt[2], lt[1], lt[0], lt[3], lt[4])

    def _state(self):
        return self._st[0]

    def _set_state(self, s):
        self._st[0] = s

    def _draw_status_bar(self, title):
        self.oled.text(title, 0, 0)
        self.oled.text("W" if self.wifi_ok else " ", 120, 0)
        self.oled.hline(0, 9, DISPLAY_WIDTH, 1)

    def _draw_waveform(self, now):
        if time.ticks_diff(now, self._wave_tick) >= 25:
            self._wave_tick = now
            span = max(1, self.sig.span)
            norm = int((self.sig.filtered_data - self.sig.min_val) / span * 31)
            norm = max(0, min(31, norm))
            self._wave_buf[self._wave_idx] = 31 - norm
            self._wave_idx = (self._wave_idx + 1) % 64
        for px in range(64):
            idx = (self._wave_idx + px) % 64
            y   = 12 + self._wave_buf[idx]
            self.oled.pixel(64 + px, y, 1)
            if px > 0:
                prev = 12 + self._wave_buf[(self._wave_idx + px - 1) % 64]
                lo, hi = (y, prev) if y < prev else (prev, y)
                for yy in range(lo, hi + 1):
                    self.oled.pixel(64 + px, yy, 1)

    # ------------------------------------------------------------------
    #  NAME ENTRY WIDGET
    # ------------------------------------------------------------------
    def _draw_name_entry(self, delta, short_press, long_press):
        t = self._t()
        self.oled.text(t["set_name"], 0, 0)
        self.oled.hline(0, 9, DISPLAY_WIDTH, 1)
        if delta:
            c = self._name_chars[self._name_pos]
            c = (c - ord('A') + delta) % 26 + ord('A')
            self._name_chars[self._name_pos] = c
        for i, ch in enumerate(self._name_chars):
            x = 20 + i * 30
            self.oled.text(chr(ch), x, 26)
            if i == self._name_pos:
                self.oled.hline(x, 35, 8, 1)
        self.oled.text("Enc=Next Char", 0, 48)
        self.oled.text("Hold Enc=OK",   0, 56)
        
        if short_press:
            self._name_pos = (self._name_pos + 1) % 3
        if long_press:
            self.user_name = self._name_str()
            return True
        return False

    # ------------------------------------------------------------------
    #  MAIN TICK  –  called ~12 times/second from main.py
    # ------------------------------------------------------------------
    def tick(self):
        self.oled.fill(0)
        now                            = time.ticks_ms()
        delta, short_press, long_press = self._input.read()
        s                              = self._state()
        t                              = self._t()

        # ============================================================  BOOT
        if s == STATE_BOOT:
            interval = BOOT_INTERVALS[self.boot_speed]
            if time.ticks_diff(now, self._pulse_tick) >= interval:
                self._pulse_tick  = now
                self._pulse_frame += 1
                if self._pulse_frame >= BOOT_PULSES:
                    self._boot_done = True
            self.oled.text(t["app_name"], 20, 2)
            if not self._boot_done:
                fb = FB_HEART_BIG if (self._pulse_frame % 2 == 0) else FB_HEART_SMALL
                self.oled.blit(fb, 56, 28)
                for d in range(min(self._pulse_frame, 5)):
                    self.oled.pixel(52 + d * 5, 54, 1)
            else:
                self.oled.blit(FB_HEART_BIG, 56, 20)
                self.oled.text(t["press_start"], 0, 48)
                if short_press or long_press:
                    self.oled.fill(0)
                    self.oled.text(t["starting"], 20, 30)
                    self.oled.show()
                    time.sleep_ms(800)
                    self.net.start_wifi()
                    self._wifi_start = time.ticks_ms()
                    self._set_state(STATE_WIFI_CHECK)
                    return

        # ============================================================  WIFI CHECK
        elif s == STATE_WIFI_CHECK:
            elapsed   = time.ticks_diff(now, self._wifi_start)
            remaining = max(0, (self._wifi_timeout - elapsed) // 1000)
            if self.net.is_connected():
                self.net.confirm_connected()
                self.wifi_ok = True
                self.oled.text(t["wifi_ok"], 0, 20)
                self.oled.show()
                time.sleep_ms(800)
                self._set_state(STATE_SETUP_NAME)
                return
            elif elapsed >= self._wifi_timeout:
                self.wifi_ok = False
                self.oled.text(t["no_wifi"],  10, 16)
                self.oled.text(t["no_wifi2"], 10, 28)
                self.oled.show()
                time.sleep_ms(1200)
                self._set_state(STATE_SETUP_NAME)
                return
            else:
                self.oled.text("Connecting...", 10, 16)
                self.oled.text("{:d}s".format(remaining), 56, 30)
                dots = "." * ((elapsed // 400) % 4)
                self.oled.text(dots, 60, 44)

        # ============================================================  SETUP NAME
        elif s == STATE_SETUP_NAME:
            if self._draw_name_entry(delta, short_press, long_press):
                self._set_state(STATE_SETUP_AGE)

        # ============================================================  SETUP AGE
        elif s == STATE_SETUP_AGE:
            if delta:
                self.user_age = max(1, min(99, self.user_age + delta))
            self.oled.text(t["set_age"], 0, 0)
            self.oled.hline(0, 9, DISPLAY_WIDTH, 1)
            self.oled.text("< {:2d} >".format(self.user_age), 35, 28)
            self.oled.text(t["press_confirm"], 0, 52)
            if short_press or long_press:
                self._set_state(STATE_SETUP_GENDER)

        # ============================================================  SETUP GENDER
        elif s == STATE_SETUP_GENDER:
            genders = [t["gender_m"], t["gender_f"]]
            if delta:
                self.user_gender_idx = (self.user_gender_idx + delta) % 2
            self.user_gender = genders[self.user_gender_idx]
            self.oled.text(t["set_gender"], 0, 0)
            self.oled.hline(0, 9, DISPLAY_WIDTH, 1)
            self.oled.text("< {} >".format(self.user_gender), 10, 28)
            self.oled.text(t["press_confirm"], 0, 52)
            if short_press or long_press:
                self.net.sync_patient(self.user_name)
                self._sync_start = now
                self._set_state(STATE_SYNC_PROFILE)

        # ============================================================  SYNC PATIENT (DB)
        elif s == STATE_SYNC_PROFILE:
            elapsed = time.ticks_diff(now, self._sync_start)
            self.oled.text("Syncing DB...", 10, 30)
            
            # Continue if sync finished, encountered error, or timeout reached
            if self.net.sync_state in [3, -1] or elapsed > 5000 or not self.wifi_ok:
                self._splash_end = time.ticks_add(now, 1500)
                self._set_state(STATE_PROFILE_OK)

        # ============================================================  PROFILE SPLASH
        elif s == STATE_PROFILE_OK:
            self._draw_status_bar(t["prof_saved"])
            self.oled.text("{}: {}".format(t["name_lbl"],   self.user_name),  0, 14)
            self.oled.text("{}: {}".format(t["age_lbl"],    self.user_age),   0, 26)
            self.oled.text("{}: {}".format(t["gender_lbl"], self.user_gender),0, 38)
            self.oled.text(t["wifi_ok"] if self.wifi_ok else t["wifi_no"],    0, 50)
            if time.ticks_diff(now, self._splash_end) >= 0:
                self._set_state(STATE_MENU)

        # ============================================================  MAIN MENU
        elif s == STATE_MENU:
            if delta:
                self._menu_sel = (self._menu_sel + delta) % len(t["menu"])
            draw_scrollable_menu(self.oled, t["app_name"], t["menu"], self._menu_sel)
            if short_press or long_press:
                self._sub_sel = 0
                sel = self._menu_sel
                if   sel == 0: self._set_state(STATE_ANALYSIS)
                elif sel == 1:
                    self._user_phase = 0
                    self._name_pos   = 0
                    self._name_chars = [ord(c) for c in self.user_name]
                    self._set_state(STATE_USER)
                elif sel == 2:
                    self._hist_page = 0
                    self._set_state(STATE_HISTORY)
                elif sel == 3: self._set_state(STATE_HELP)
                elif sel == 4:
                    self._settings_sel = 0
                    self._set_state(STATE_SETTINGS)

        # ============================================================  ANALYSIS SUB-MENU
        elif s == STATE_ANALYSIS:
            options = t["analysis_menu"]
            if delta:
                self._sub_sel = (self._sub_sel + delta) % len(options)
            draw_scrollable_menu(self.oled, t["menu"][0], options, self._sub_sel)
            if short_press or long_press:
                if self._sub_sel == 2:
                    self._set_state(STATE_MENU)
                else:
                    self.measure_mode = MODE_BPM if self._sub_sel == 0 else MODE_HRV
                    self.sig.reset_measurement()
                    self._meas_start  = now
                    self._post_done   = False
                    self._wave_buf    = [32] * 64
                    self._wave_idx    = 0
                    self.local_bpm    = 0
                    self.local_sdnn   = 0
                    self.local_rmssd  = 0
                    self.hr_lbl       = "--"
                    self.readiness    = "--"
                    self.stress       = "--"
                    self._set_state(STATE_MEASURE)

        # ============================================================  MEASURE
        elif s == STATE_MEASURE:
            elapsed   = time.ticks_diff(now, self._meas_start)
            remaining = max(0, (MEAS_DURATION_MS - elapsed) // 1000)
            mode_lbl  = "BPM" if self.measure_mode == MODE_BPM else "HRV"

            # Time expired – compute final results
            if elapsed >= MEAS_DURATION_MS and not self._post_done:
                self._post_done = True
                if self.sig.rri_buffer:
                    self.local_bpm, self.local_sdnn, self.local_rmssd = \
                        compute_hrv(self.sig.rri_buffer)
                    self.hr_lbl = hr_label(
                        self.local_bpm, self.user_age, self._gender_is_male())
                    self.history.add({
                        "time":  self._formatted_time(),
                        "mode":  mode_lbl,
                        "bpm":   self.local_bpm,
                        "sdnn":  self.local_sdnn,
                        "rmssd": self.local_rmssd,
                        "name":  self.user_name,
                        "kubios": None  # Will be populated after kubios response
                    })

            if self._post_done:
                self._draw_status_bar("{} {}".format(mode_lbl, t["result_lbl"]))
                self.oled.text("{}: {} ({})".format(
                    t["mean_bpm"], self.local_bpm, self.hr_lbl), 0, 12)
                if self.measure_mode == MODE_HRV:
                    self.oled.text("{}: {}".format(t["sdnn"],  self.local_sdnn),  0, 24)
                    self.oled.text("{}: {}".format(t["rmssd"], self.local_rmssd), 0, 36)
                # else:
                #     self.oled.text("{}: {}".format(
                #         t["beats_lbl"], len(self.sig.rri_buffer)), 0, 24)
                
                hint = "Hold=Send" if self.wifi_ok else t["press_retry"]
                self.oled.text("{} {}".format(t["press_retry"], hint), 0, 54)
                
                if long_press and self.wifi_ok:
                    self.sig.led.off()
                    self.net.send_to_kubios(
                        self.sig.rri_buffer, self.user_name,
                        self.user_age, self._gender_is_male(),
                        self.local_sdnn, self.local_rmssd)
                    self._set_state(STATE_ANALYZE)
                elif short_press or (long_press and not self.wifi_ok):
                    self.sig.led.off()
                    self._post_done = False
                    self._set_state(STATE_ANALYSIS)

            elif self.sig.span < 500:   # no finger
                self._draw_status_bar("{} {}".format(mode_lbl, t["measuring"]))
                self.oled.text(t["no_finger"], 20, 22)
                self.oled.text(t["detected"],  20, 32)
                self.oled.text(t["back"],       0, 54)
                if short_press or long_press:
                    self.sig.led.off()
                    self._set_state(STATE_ANALYSIS)

            else:
                self._draw_status_bar("{} {}s".format(mode_lbl, remaining))
                self._draw_waveform(now)
                self.oled.vline(62, 11, 42, 1)
                if self.measure_mode == MODE_BPM:
                    live = int(60_000 / (sum(self.sig.rri_buffer) /
                               max(1, len(self.sig.rri_buffer)))) \
                           if self.sig.rri_buffer else 0
                    self.oled.text(t["est_bpm"],               0, 14)
                    self.oled.text("{:3d}".format(live),       0, 24)
                    # self.oled.text(t["beats_lbl"],             0, 36)
                    # self.oled.text("{:3d}".format(
                    #     len(self.sig.rri_buffer)),             0, 46)
                else:
                    if len(self.sig.rri_buffer) >= 2:
                        bpm, sdnn, _ = compute_hrv(self.sig.rri_buffer)
                        self.oled.text(t["est_bpm"],           0, 14)
                        self.oled.text("{:3d}".format(bpm),   0, 24)
                        self.oled.text(t["sdnn"],              0, 36)
                        self.oled.text("{:3d}".format(sdnn),  0, 46)
                    else:
                        self.oled.text(t["est_bpm"], 0, 14)
                        self.oled.text("---",        0, 24)
                if self.sig.led.value():
                    self.oled.blit(FB_HEART_SMALL, 44, 11)
                bar_w = int((remaining / 30) * DISPLAY_WIDTH)
                self.oled.rect(0, 57, DISPLAY_WIDTH, 6, 1)
                if bar_w > 0:
                    self.oled.fill_rect(0, 57, bar_w, 6, 1)
                if short_press or long_press:
                    self.sig.led.off()
                    self._set_state(STATE_ANALYSIS)

        # ============================================================  SENDING
        elif s == STATE_ANALYZE:
            self._draw_status_bar(t["app_name"])
            self.oled.text(t["sending"],   10, 16)
            self.oled.text(t["to_kubios"], 10, 28)
            self.oled.text(t["wait"],      10, 40)
            self.oled.text("." * ((now // 400) % 5), 60, 52)
            self._set_state(STATE_RESULTS)

        # ============================================================  KUBIOS RESULTS
        elif s == STATE_RESULTS:
            self._draw_status_bar(t["result_lbl"])
            self.oled.text("{}: {} ({})".format(
                t["mean_bpm"], self.local_bpm, self.hr_lbl), 0, 12)
            self.oled.text("{}: {}".format(t["readiness"], self.readiness), 0, 26)
            self.oled.text("{}: {}".format(t["stress"],    self.stress),    0, 38)
            self.oled.text(t["press_retry"], 0, 54)
            if short_press or long_press:
                self._set_state(STATE_MEASURE)

        # ============================================================  USER EDITOR
        elif s == STATE_USER:
            t = self._t()
            phase = self._user_phase
            if phase == 0:
                if self._draw_name_entry(delta, short_press, long_press):
                    self._user_phase = 1
                    self._set_state(STATE_USER)
            elif phase == 1:
                if delta:
                    self.user_age = max(1, min(99, self.user_age + delta))
                self.oled.text(t["set_age"], 0, 0)
                self.oled.hline(0, 9, DISPLAY_WIDTH, 1)
                self.oled.text("< {:2d} >".format(self.user_age), 35, 28)
                self.oled.text(t["press_confirm"], 0, 52)
                if short_press or long_press:
                    self._user_phase = 2
            elif phase == 2:
                genders = [t["gender_m"], t["gender_f"]]
                if delta:
                    self.user_gender_idx = (self.user_gender_idx + delta) % 2
                self.user_gender = genders[self.user_gender_idx]
                self.oled.text(t["set_gender"], 0, 0)
                self.oled.hline(0, 9, DISPLAY_WIDTH, 1)
                self.oled.text("< {} >".format(self.user_gender), 10, 28)
                self.oled.text(t["press_confirm"], 0, 52)
                if short_press or long_press:
                    self.net.sync_patient(self.user_name)
                    self._sync_start  = now
                    self._user_phase  = 3
            elif phase == 3:
                elapsed = time.ticks_diff(now, self._sync_start)
                self.oled.text("Syncing DB...", 10, 30)
                if self.net.sync_state in [3, -1] or elapsed > 5000 or not self.wifi_ok:
                    self._splash_end = time.ticks_add(now, 1500)
                    self._user_phase = 4
            elif phase == 4:
                self.oled.text(t["prof_saved"], 10, 10)
                self.oled.text("{}: {}".format(t["name_lbl"],   self.user_name),  0, 26)
                self.oled.text("{}: {}".format(t["age_lbl"],    self.user_age),   0, 38)
                self.oled.text("{}: {}".format(t["gender_lbl"], self.user_gender),0, 50)
                if time.ticks_diff(now, self._splash_end) >= 0:
                    self._user_phase = 0
                    self._set_state(STATE_MENU)

        # ============================================================  HISTORY
        elif s == STATE_HISTORY:
            records = self.history.all()
            self._draw_status_bar(t["history_title"])
            if not records:
                self.oled.text(t["no_history"], 0, 24)
                self.oled.text(t["back"], 0, 56)
                if short_press or long_press:
                    self._set_state(STATE_MENU)
            else:
                if delta:
                    self._hist_page = (self._hist_page + delta) % len(records)
                rec   = records[self._hist_page]
                total = len(records)
                self.oled.text("{}/{} {}".format(
                    self._hist_page + 1, total, rec["mode"]), 0, 12)
                self.oled.text(rec["time"], 0, 24)
                self.oled.text("{}: {} BPM".format(rec["name"], rec["bpm"]), 0, 36)
                if rec["mode"] == "HRV":
                    self.oled.text("SD:{} RMS:{}".format(
                        rec["sdnn"], rec["rmssd"]), 0, 46)
                
                self.oled.text("Enc=View Hold=Back", 0, 56)
                if short_press:
                    self._detail_sel = 0
                    self._set_state(STATE_HISTORY_DETAIL)
                elif long_press:
                    self._set_state(STATE_MENU)

        # ============================================================  HISTORY DETAIL
        elif s == STATE_HISTORY_DETAIL:
            rec = self.history.all()[self._hist_page]
            kubios = rec.get("kubios")
            if kubios:
                def fmt(k, v):
                    if v is None: return "{}: N/A".format(k)
                    if isinstance(v, float): return "{}: {:.2f}".format(k, v)
                    return "{}: {}".format(k, v)
                
                items = [
                    fmt("Readiness", kubios.get("readiness")),
                    fmt("Stress", kubios.get("stress_index")),
                    fmt("PNS", kubios.get("pns_index")),
                    fmt("SNS", kubios.get("sns_index")),
                    fmt("Mean HR", kubios.get("mean_hr_bpm")),
                    fmt("RMSSD", kubios.get("rmssd_ms")),
                    fmt("SDNN", kubios.get("sdnn_ms")),
                    fmt("LF/HF", kubios.get("freq_domain", {}).get("LF_HF_power")),
                ]
            else:
                items = ["No Detailed", "Kubios Data", "Available"]

            if delta:
                self._detail_sel = (self._detail_sel + delta) % len(items)
            draw_scrollable_menu(self.oled, "Kubios Data", items, self._detail_sel)
            
            self.oled.text(t["back"], 0, 56)
            if short_press or long_press:
                self._set_state(STATE_HISTORY)

        # ============================================================  HELP
        elif s == STATE_HELP:
            for idx, line in enumerate(t["help_lines"]):
                self.oled.text(line, 0, idx * 8)
            if short_press or long_press:
                self._set_state(STATE_MENU)

        # ============================================================  LANGUAGES
        elif s == STATE_LANGUAGES:
            if delta:
                self._sub_sel = (self._sub_sel + delta) % len(LANG_CODES)
            self.oled.text(t["select_lang"], 0, 0)
            self.oled.hline(0, 9, DISPLAY_WIDTH, 1)
            self.oled.text("< {} >".format(LANG_CODES[self._sub_sel]), 40, 28)
            self.oled.text(t["press_confirm"], 0, 52)
            if short_press or long_press:
                self.lang_idx = self._sub_sel
                self.lang     = LANG_CODES[self.lang_idx]
                self._sync_gender_label()
                self._set_state(STATE_SETTINGS)

        # ============================================================  SETTINGS
        elif s == STATE_SETTINGS:
            items = t["settings_menu"]
            if delta:
                self._settings_sel = (self._settings_sel + delta) % len(items)
            draw_scrollable_menu(self.oled, "Settings", items, self._settings_sel)
            if short_press or long_press:
                sel = self._settings_sel
                if sel == 0:
                    self.boot_speed = (self.boot_speed % 3) + 1
                    speed_lbl = [t["speed_slow"], t["speed_norm"], t["speed_fast"]]
                    self.oled.fill(0)
                    self.oled.text(t["boot_speed"], 0, 16)
                    self.oled.text(speed_lbl[self.boot_speed - 1], 40, 32)
                    self.oled.show()
                    time.sleep_ms(800)
                elif sel == 1:
                    self.beep_on = not self.beep_on
                    self.oled.fill(0)
                    self.oled.text(t["beep_on"] if self.beep_on else t["beep_off"],
                                   20, 30)
                    self.oled.show()
                    time.sleep_ms(700)
                elif sel == 2:
                    self._sub_sel = self.lang_idx
                    self._set_state(STATE_LANGUAGES)
                    return
                elif sel == 3:
                    self.oled.fill(0)
                    self.oled.text(t["about_1"], 10, 10)
                    self.oled.text(t["about_2"], 10, 24)
                    self.oled.text(t["about_3"], 10, 38)
                    self.oled.text(
                        t["wifi_ok"] if self.wifi_ok else t["wifi_no"], 10, 52)
                    self.oled.show()
                    time.sleep_ms(2500)
                elif sel == len(items) - 1:
                    self._set_state(STATE_MENU)

        self.oled.show()
