# HeartoMetro: Recovery and Stress Meter

**HeartoMetro** (Group 1) is a heart rate detection and analysis system designed as a proof-of-concept recovery and stress meter. It utilizes the Raspberry Pi Pico W to process photoplethysmography (PPG) signals locally and integrates with cloud services for advanced physiological analysis.

## 🚀 Key Features
- **Local Heart Rate Detection**: Real-time heart rate and HRV (Heart Rate Variability) calculation using peak-detection algorithms.
- **HRV Analysis**: Calculates SDNN (Standard Deviation of NN intervals) and RMSSD (Root Mean Square of Successive Differences).
- **Cloud Integration**: Connects via WiFi/MQTT to the Kubios Cloud HRV service for advanced Stress Index and Readiness status.
- **Rich User Interface**: Features a 128x64 OLED display and a rotary encoder with push-button controls.
- **Multi-Language Support**: Full UI available in English (EN), Finnish (FI), and Romanian (RO).
- **History Tracking**: Saves measurement logs to local storage and synchronizes patient records with a central database.

## 🛠️ Hardware Requirements
| Component | Description |
| :--- | :--- |
| **Microcontroller** | Raspberry Pi Pico W (Dual-core ARM, 2.4 GHz WiFi) |
| **Pulse Sensor** | Crowtail Pulse Sensor v2.0 (Optical PPG) |
| **Display** | SSD1306 128x64 Monochrome OLED |
| **Control** | Digital Rotary Encoder with push button |
| **Prototyping** | Metropolia UAS Custom Protoboard with Grove connectors |

## 💻 Software Stack
- **Language**: MicroPython
- **Development IDE**: Thonny IDE
- **Communication**: MQTT protocol for cloud/database exchange
- **Dependencies**: 
  - `ssd1306.py`: OLED driver
  - `fifo.py`: Data buffer management
  - `piotimer.py`: Precise ADC sampling timers

## 🏗️ System Architecture
1. **Signal Acquisition**: The Pulse sensor detects blood volume changes via light absorption.
2. **Local Processing**: The Pico W samples the ADC at 250 Hz, applying an EMA (Exponential Moving Average) filter for smoothing.
3. **Local Analysis**: Beat detection identifies inter-beat-intervals (IBI) and calculates baseline HRV metrics.
4. **Cloud Exchange**: Data is sent to Kubios Cloud via MQTT; the system receives back advanced metrics like "Readiness" and "Stress Index."
5. **Display**: Results are shown on the OLED and stored in the `HistoryStore`.

## 📂 File Structure
- `main.py`: Entry point; initializes hardware and runs the main task loop.
- `config.py`: Central configuration for pins, constants, and UI translations.
- `calculations.py`: Core logic for signal processing, HRV mathematics, and history management.
- `menu.py`: Manages the UI state machine, screens, and input handling.
- `mqtt_wifi.py`: Handles WiFi connectivity, NTP time sync, and MQTT messaging.

## 📖 Usage
1. **Setup**: Clip the pulse sensor to a fingertip, earlobe, or other peripheral site.
2. **Start**: Use the rotary encoder to navigate the menu to **Analysis** and select **HRV Analysis**.
3. **Measure**: Stay still and relax for 30 seconds while the device records your pulse.
4. **Analyze**: View local results (BPM, SDNN). To see cloud-based stress levels, hold the encoder to **Send to Kubios**.
5. **History**: Review previous measurements in the **History** menu.
