# =============================================================================
#  config.py  –  All constants, pin numbers, states and language strings
#  HEARTOMETRO  |  Group 1  |  2025
# =============================================================================

# -----------------------------------------------------------------------------
#  HARDWARE PIN NUMBERS
# -----------------------------------------------------------------------------
PPG_ADC_PIN        = 26
BUTTON_UP_PIN      = 7
BUTTON_DOWN_PIN    = 9
BUTTON_SELECT_PIN  = 8
LED_HEARTBEAT_PIN  = 22
I2C_BUS            = 1
I2C_SDA_PIN        = 14
I2C_SCL_PIN        = 15
ROT_A_PIN          = 10
ROT_B_PIN          = 11
ROT_PUSH_PIN       = 12
ROT_DEBOUNCE_MS    = 5
DISPLAY_WIDTH      = 128
DISPLAY_HEIGHT     = 64
DISPLAY_I2C_ADDR   = 0x3C
DISPLAY_I2C_FREQ   = 400_000

# -----------------------------------------------------------------------------
#  NETWORK
# -----------------------------------------------------------------------------
WIFI_SSID     = "KMD657_Group_1"
WIFI_PASSWORD = "ceausescu1989"
MQTT_BROKER   = "192.168.1.253"
MQTT_PORT     = 69

# -----------------------------------------------------------------------------
#  SIGNAL PROCESSING
# -----------------------------------------------------------------------------
SAMPLE_RATE      = 250      # Hz
EMA_ALPHA        = 0.10     # lower = smoother
WINDOW_SIZE      = 750      # adaptive min/max window (~3 s at 250 Hz)
FINGER_THRESHOLD = 500      # ADC span below this → no finger detected
MEAS_DURATION_MS = 30_000   # 30-second measurement window
MIN_RRI_MS       = 300      # floor  (~200 bpm)
MAX_RRI_MS       = 2000     # ceiling (~30 bpm)

# -----------------------------------------------------------------------------
#  BOOT ANIMATION
# -----------------------------------------------------------------------------
DEFAULT_BOOT_SPEED = 2                          # 1=slow 2=normal 3=fast
BOOT_INTERVALS     = {1: 600, 2: 350, 3: 180}  # ms per heart-beat frame
BOOT_PULSES        = 6                          # pulses before "press to start"

# -----------------------------------------------------------------------------
#  ROTARY ENCODER LOOK-UP TABLE
# -----------------------------------------------------------------------------
ENC_TABLE = [0, 1, -1, 0, -1, 0, 0, 1, 1, 0, 0, -1, 0, -1, 1, 0]

# -----------------------------------------------------------------------------
#  APPLICATION STATES
# -----------------------------------------------------------------------------
STATE_BOOT         = -1
STATE_SETUP_NAME   = -2
STATE_SETUP_AGE    = -3
STATE_SETUP_GENDER = -4
STATE_PROFILE_OK   = -5
STATE_MENU         = -6
STATE_ANALYSIS     = -7
STATE_USER         = -8
STATE_HELP         = -9
STATE_LANGUAGES    = -10
STATE_HISTORY      = -11
STATE_SETTINGS     = -12
STATE_SYNC_PROFILE = -13
STATE_HISTORY_DETAIL= -14
STATE_WIFI_CHECK   = 0
STATE_MEASURE      = 1
STATE_ANALYZE      = 2
STATE_RESULTS      = 3

# Measurement modes
MODE_BPM = 0
MODE_HRV = 1

# -----------------------------------------------------------------------------
#  SUPPORTED LANGUAGES
# -----------------------------------------------------------------------------
LANG_CODES = ["EN", "FI", "RO"]

UI_TEXTS = {
    # ------------------------------------------------------------------ EN
    "EN": {
        "app_name":      "HeartoMetro",
        "menu":          ["Analysis", "User", "History", "Help", "Settings"],
        "press_start":   "Enc=Start",
        "starting":      "STARTING...",
        "set_name":      "Initials:",
        "set_age":       "Age:",
        "set_gender":    "Gender:",
        "press_confirm": "Hold Enc=OK",
        "gender_m":      "Male",
        "gender_f":      "Female",
        "prof_saved":    "Profile Saved!",
        "age_lbl":       "Age",
        "gender_lbl":    "Gender",
        "name_lbl":      "Name",
        "analysis_menu": ["BPM Analysis", "HRV Analysis", "Back"],
        "back":          "Enc=Back",
        "select_lang":   "Language:",
        "history_title": "Measurement Log",
        "no_history":    "No records yet.",
        "no_finger":     "No finger",
        "detected":      "detected",
        "measuring":     "Measuring",
        "beats_lbl":     "Beats",
        "est_bpm":       "BPM",
        "sending":       "Sending to",
        "to_kubios":     "Kubios...",
        "wait":          "Please wait.",
        "result_lbl":    "Result:",
        "readiness":     "Readiness",
        "stress":        "Stress Idx",
        "mean_bpm":      "Avg BPM",
        "sdnn":          "SDNN ms",
        "rmssd":         "RMSSD ms",
        "press_retry":   "Enc=Retry",
        "settings_menu": ["Boot Speed", "Beep", "Language", "About", "Back"],
        "boot_speed":    "Boot Speed:",
        "speed_slow":    "Slow",
        "speed_norm":    "Normal",
        "speed_fast":    "Fast",
        "beep_on":       "Beep: ON",
        "beep_off":      "Beep: OFF",
        "about_1":       "HeartoMetro v3",
        "about_2":       "ECG/PPG Monitor",
        "about_3":       "Group 1  2025",
        "wifi_ok":       "WiFi: Connected",
        "wifi_no":       "WiFi: Offline",
        "no_wifi":       "WiFi unavailable",
        "no_wifi2":      "Offline mode.",
        "help_lines": [
            "1. Clip sensor on",
            "   fingertip.",
            "2. Stay still,",
            "   relax finger.",
            "3. Wait 30 s.",
            "4. View results.",
            "Enc=Back",
        ],
    },
    # ------------------------------------------------------------------ FI
    "FI": {
        "app_name":      "HeartoMetro",
        "menu":          ["Analyysi", "Kayttaja", "Historia", "Apua", "Asetukset"],
        "press_start":   "Enc=Aloita",
        "starting":      "KAYNNISTYY...",
        "set_name":      "Nimikirjaimet:",
        "set_age":       "Ika:",
        "set_gender":    "Sukupuoli:",
        "press_confirm": "Hold Enc=OK",
        "gender_m":      "Mies",
        "gender_f":      "Nainen",
        "prof_saved":    "Tallennettu!",
        "age_lbl":       "Ika",
        "gender_lbl":    "Sukupuoli",
        "name_lbl":      "Nimi",
        "analysis_menu": ["BPM Analyysi", "HRV Analyysi", "Takaisin"],
        "back":          "Enc=Takaisin",
        "select_lang":   "Kieli:",
        "history_title": "Mittausloki",
        "no_history":    "Ei merkintoja.",
        "no_finger":     "Ei sormea",
        "detected":      "havaittu",
        "measuring":     "Mitataan",
        "beats_lbl":     "Lyontia",
        "est_bpm":       "BPM",
        "sending":       "Lahetetaan",
        "to_kubios":     "Kubios...",
        "wait":          "Odota.",
        "result_lbl":    "Tulos:",
        "readiness":     "Valmius",
        "stress":        "Stressi",
        "mean_bpm":      "Keskim BPM",
        "sdnn":          "SDNN ms",
        "rmssd":         "RMSSD ms",
        "press_retry":   "Enc=Uusiksi",
        "settings_menu": ["Kaynnistysnop.", "Aanet", "Kieli", "Tiedot", "Takaisin"],
        "boot_speed":    "Nopeus:",
        "speed_slow":    "Hidas",
        "speed_norm":    "Normaali",
        "speed_fast":    "Nopea",
        "beep_on":       "Aani: ON",
        "beep_off":      "Aani: OFF",
        "about_1":       "HeartoMetro v3",
        "about_2":       "PPG-mittari",
        "about_3":       "Ryhma 1  2025",
        "wifi_ok":       "WiFi: Yhdistetty",
        "wifi_no":       "WiFi: Offline",
        "no_wifi":       "WiFi ei saatavilla",
        "no_wifi2":      "Offline-tila.",
        "help_lines": [
            "1. Laita anturi",
            "   sormenpaahan.",
            "2. Pysy paikallaan,",
            "   rentoudu.",
            "3. Odota 30 s.",
            "4. Katso tulokset.",
            "Enc=Takaisin",
        ],
    },
    # ------------------------------------------------------------------ RO
    "RO": {
        "app_name":      "HeartoMetro",
        "menu":          ["Analiza", "Utilizator", "Istoric", "Ajutor", "Setari"],
        "press_start":   "Enc=Start",
        "starting":      "PORNIRE...",
        "set_name":      "Initiale:",
        "set_age":       "Varsta:",
        "set_gender":    "Gen:",
        "press_confirm": "Hold Enc=OK",
        "gender_m":      "Masculin",
        "gender_f":      "Feminin",
        "prof_saved":    "Profil Salvat!",
        "age_lbl":       "Varsta",
        "gender_lbl":    "Gen",
        "name_lbl":      "Nume",
        "analysis_menu": ["Analiza BPM", "Analiza HRV", "Inapoi"],
        "back":          "Enc=Inapoi",
        "select_lang":   "Limba:",
        "history_title": "Jurnal",
        "no_history":    "Fara inregistrari.",
        "no_finger":     "Fara deget",
        "detected":      "detectat",
        "measuring":     "Masurare",
        "beats_lbl":     "Batai",
        "est_bpm":       "BPM",
        "sending":       "Trimitere la",
        "to_kubios":     "Kubios...",
        "wait":          "Asteptati.",
        "result_lbl":    "Rezultat:",
        "readiness":     "Pregatire",
        "stress":        "Ind. Stres",
        "mean_bpm":      "BPM Mediu",
        "sdnn":          "SDNN ms",
        "rmssd":         "RMSSD ms",
        "press_retry":   "Enc=Reluare",
        "settings_menu": ["Viteza Pornire", "Sunet", "Limba", "Despre", "Inapoi"],
        "boot_speed":    "Viteza:",
        "speed_slow":    "Lent",
        "speed_norm":    "Normal",
        "speed_fast":    "Rapid",
        "beep_on":       "Sunet: ON",
        "beep_off":      "Sunet: OFF",
        "about_1":       "HeartoMetro v3",
        "about_2":       "Monitor PPG",
        "about_3":       "Grupa 1  2025",
        "wifi_ok":       "WiFi: Conectat",
        "wifi_no":       "WiFi: Offline",
        "no_wifi":       "WiFi indisponibil",
        "no_wifi2":      "Mod offline.",
        "help_lines": [
            "1. Pune senzorul",
            "   pe deget.",
            "2. Stai linistit,",
            "   relaxeaza-te.",
            "3. Asteapta 30 s.",
            "4. Vezi rezultate.",
            "Enc=Inapoi",
        ],
    },
}
