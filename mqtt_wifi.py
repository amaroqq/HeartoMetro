# =============================================================================
#  mqtt_wifi.py  –  WiFi connection, NTP sync, MQTT client
#  HEARTOMETRO  |  Group 1  |  2025
# =============================================================================

import network
import ujson as json
import ubinascii
import time

from config import WIFI_SSID, WIFI_PASSWORD, MQTT_BROKER, MQTT_PORT, STATE_RESULTS

try:
    from umqtt.simple import MQTTClient
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

try:
    import ntptime
    NTP_AVAILABLE = True
except ImportError:
    NTP_AVAILABLE = False


# =============================================================================
#  NETWORK MANAGER
#  Owns WiFi, MQTT and NTP.  The app calls methods on this object;
#  results are written back via the shared `app` reference.
# =============================================================================
class NetworkManager:

    def __init__(self, app):
        """app – the Heartometro instance (provides .state, .readiness, etc.)"""
        self._app  = app
        self.wlan  = None
        self.mac   = ""
        self.mqtt  = None
        self.ok    = False   # True once WiFi is confirmed connected
        
        # Patient Sync State: 0=idle, 1=fetching list, 2=adding, 3=done, -1=error
        self.sync_state = 0
        self.patient_id = None
        self.target_patient_name = ""

    # ------------------------------------------------------------------
    #  WiFi
    # ------------------------------------------------------------------
    def start_wifi(self):
        """Begin non-blocking WiFi connection attempt."""
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        try:
            mac_b    = self.wlan.config('mac')
            self.mac = ubinascii.hexlify(mac_b).decode().upper()
        except Exception:
            self.mac = "UNKNOWN"
        if not self.wlan.isconnected():
            try:
                self.wlan.connect(WIFI_SSID, WIFI_PASSWORD)
            except Exception:
                pass

    def is_connected(self):
        return bool(self.wlan and self.wlan.isconnected())

    def confirm_connected(self):
        """Call once WiFi is confirmed up.  Sets self.ok and syncs NTP."""
        self.ok = True
        self._sync_ntp()

    # ------------------------------------------------------------------
    #  NTP
    # ------------------------------------------------------------------
    def _sync_ntp(self):
        if NTP_AVAILABLE:
            try:
                ntptime.settime()
            except Exception:
                pass

    # ------------------------------------------------------------------
    #  MQTT tick  (call from main loop ~10 Hz when wifi is ok)
    # ------------------------------------------------------------------
    def tick(self):
        """Maintain MQTT connection and check for incoming messages."""
        if not self.is_connected() or not MQTT_AVAILABLE:
            return
        if not self.mqtt:
            self._connect_mqtt()
        else:
            try:
                self.mqtt.check_msg()
            except Exception:
                self.mqtt = None

    def _connect_mqtt(self):
        try:
            self.mqtt = MQTTClient(self.mac, MQTT_BROKER,
                                   port=MQTT_PORT, keepalive=60)
            self.mqtt.set_callback(self._on_message)
            self.mqtt.connect()
            self.mqtt.subscribe(b"kubios/response")
            self.mqtt.subscribe(b"database/response")
            self.mqtt.publish(b"database/devices/add", json.dumps({
                "mac":         self.mac,
                "device_name": "Heartometro_{}".format(self.mac[-4:]),
            }))
        except Exception:
            self.mqtt = None

    # ------------------------------------------------------------------
    #  Patient API Methods
    # ------------------------------------------------------------------
    def sync_patient(self, name):
        """Begin patient sync flow based on database API."""
        if not self.mqtt:
            self.sync_state = -1
            return
        self.sync_state = 1
        self.target_patient_name = name
        try:
            self.mqtt.publish(b"database/patients/list", json.dumps({"mac": self.mac}))
        except Exception:
            self.sync_state = -1

    # ------------------------------------------------------------------
    #  Incoming MQTT messages
    # ------------------------------------------------------------------
    def _on_message(self, topic, msg):
        topic = topic.decode()
        try:
            payload = json.loads(msg.decode())
            if payload.get("mac") != self.mac:
                return
                
            if topic == "database/response":
                data = payload.get("data")
                message = payload.get("message")
                
                # Handling Patients List Response
                if self.sync_state == 1 and isinstance(data, list):
                    found = False
                    for p in data:
                        if p.get("Name") == self.target_patient_name:
                            self.patient_id = p.get("ID")
                            self.sync_state = 3
                            found = True
                            break
                    if not found:
                        self.sync_state = 2
                        try:
                            self.mqtt.publish(b"database/patients/add", json.dumps({
                                "mac": self.mac, 
                                "patient_name": self.target_patient_name
                            }))
                        except Exception:
                            self.sync_state = -1
                            
                # Handling Patient Add Response
                elif self.sync_state == 2 and message == "OK" and isinstance(data, int):
                    self.patient_id = data
                    self.sync_state = 3
                    
            elif topic == "kubios/response":
                data = payload.get("data", {})
                if data.get("status") == "ok":
                    analysis = data.get("analysis", {})
                    
                    r = analysis.get("readiness")
                    self._app.readiness = "{:.1f}%".format(r) if r is not None else "N/A"
                    
                    s = analysis.get("stress_index")
                    self._app.stress = "{:.2f}".format(s) if s is not None else "N/A"
                    
                    # Embed full kubios payload into the latest local history record
                    records = self._app.history.all()
                    if records:
                        records[0]["kubios"] = analysis
                else:
                    self._app.readiness = "ERR"
                    self._app.stress    = "ERR"
                self._app.state = STATE_RESULTS
                
        except Exception:
            pass

    # ------------------------------------------------------------------
    #  Send measurement to Kubios + database
    # ------------------------------------------------------------------
    def send_to_kubios(self, rri_buffer, user_name, user_age, gender_is_male, sdnn=0, rmssd=0):
        """
        Publish RRI data to Kubios and a summary to the database.
        If MQTT is unavailable, switches app to results screen immediately.
        """
        if not self.mqtt:
            self._app.state = STATE_RESULTS
            return
        try:
            # 1. Send to Kubios API Proxy
            self.mqtt.publish(b"kubios/request", json.dumps({
                "mac":      self.mac,
                "type":     "RRI",
                "data":     rri_buffer,
                "analysis": {"type": "readiness"},
            }))
            
            # 2. Save strictly formatted document to Database API
            if rri_buffer:
                avg_ppi = sum(rri_buffer) / len(rri_buffer)
                
                db_payload = {
                    "mac":       self.mac,
                    "timestamp": int(time.time() + 1609459200),
                    "mean_hr":   int(60_000 / avg_ppi),
                    "mean_ppi":  int(avg_ppi),
                    "sdnn":      int(sdnn),
                    "rmssd":     int(rmssd)
                }
                if self.patient_id is not None:
                    db_payload["patient_id"] = self.patient_id
                    
                self.mqtt.publish(b"database/records/add", json.dumps(db_payload))
                
        except Exception:
            self._app.state = STATE_RESULTS

    # ------------------------------------------------------------------
    #  Cleanup
    # ------------------------------------------------------------------
    def disconnect(self):
        if self.mqtt:
            try: self.mqtt.disconnect()
            except: pass
