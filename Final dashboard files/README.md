# AI-Based Solar Panel Fault Detection & Energy Forecasting System

## Project architecture

This workspace contains a working Vite + React dashboard and a FastAPI backend for local monitoring, data ingestion, anomaly checks, and model-integration scaffolding.

- Frontend: `frontend/`
- Backend: `backend/`
- ESP32 firmware: `solary_esp32_final/solary_esp32_final.ino`
- Fault detection model package: `Fault_Detection_Integration/`

## Verified status

The React/Vite dashboard and FastAPI backend are retained. The final combined sketch is `solary_esp32_final/solary_esp32_final.ino`; physical delivery and INA219 measurements must still be verified on hardware:

- The dashboard builds successfully and loads its pages.
- The FastAPI backend exposes `/api/ingest` for timestamped ESP32 readings and persists received history under `backend/data/sensor_history.json`.
- The final ESP32 sketch reads DHT11 + LDR and probes INA219 at `0x40`, then posts the backend's exact field names. INA219 values remain hidden by default until the measurement path is physically verified and backend validation is enabled.
- The anomaly engine is present and configured with documented thresholds.
- The forecasting endpoint is present and returns a baseline 12H/24H forecast with clear labelling as non-ML.
- The model upload API is implemented. Install the pinned backend requirements in its project venv to use the classifier.

## Prerequisites

- Node.js 18+
- Python 3.12 (verified with the pinned TensorFlow CPU runtime)
- A local Wi-Fi network for device-to-backend testing
- ESP32 DevKit V1 and the listed sensors

## Backend startup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

API docs on this PC: http://127.0.0.1:8000/docs. Binding to `0.0.0.0` allows devices on a routable LAN to connect; use the laptop's actual reachable IPv4 address in the ESP32 config, never `0.0.0.0`.

## Frontend startup

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 on this PC. For access from another LAN device, open `http://<PC-LAN-IPv4>:5173`; the dashboard derives its API hostname from the browser address unless a custom API URL was saved in Configuration.

If Configuration contains an old custom API URL, set it to `http://192.168.43.28:8000` while that remains the laptop's address, or clear the override so the dashboard follows the page host.

## ESP32 firmware and configuration

The combined firmware is `solary_esp32_final/solary_esp32_final.ino`. The two existing sketches are retained as backups.

Required pin mapping:

- DHT11 data: GPIO 4
- LDR analog: GPIO 34
- INA219 SDA: GPIO 21
- INA219 SCL: GPIO 22

The sketch supports:

- Wi-Fi connection to the local network
- DHT11 temperature/humidity reads
- LDR raw ADC readout
- INA219 voltage/current/power measurements when detected; missing or out-of-range values are sent as JSON `null`. INA219 uses `setCalibration_32V_2A()`.
- HTTP POST to `/api/ingest`
- NTP timestamps when synchronized; otherwise the backend timestamps receipt
- two HTTP attempts per reading, response details, and success/failure counters

Before flashing:

1. On this laptop, `ipconfig /all` currently reports Ethernet IPv4 `192.168.43.28`, mask `255.255.240.0` (`192.168.32.0/20`), gateway `192.168.32.1`. Wi-Fi is currently disconnected. This confirms the laptop address, not ESP32 reachability.
2. The ESP32 must join a Wi-Fi network that can route to `192.168.43.28`; both devices on the same LAN is simplest. A phone hotspot/guest Wi-Fi may isolate clients or NAT them away from the laptop's Ethernet network. The laptop Wi-Fi adapter is currently disconnected, so the existing `VIVO V29 5G` config has not been verified to reach Ethernet. If it is not routed, use the router/Wi-Fi network that serves the Ethernet LAN or connect the laptop to the ESP32's network and use that interface's current address.
3. In `solary_esp32_final`, copy `wifi_config.example.h` to `wifi_config.h`. Set the correct reachable-network credentials and `SERVER_URL` (`http://192.168.43.28:8000/api/ingest` only while that address remains assigned). The local config is Git-ignored.
4. Install the ESP32 Arduino board package, `DHT sensor library`, and `Adafruit INA219` library. In Arduino IDE, open `solary_esp32_final/solary_esp32_final.ino`, select **Tools → Board → esp32 → DOIT ESP32 DEVKIT V1** (or **ESP32 Dev Module** if that exact entry is unavailable), then select **Tools → Port → COM3**. Windows currently detects a Silicon Labs CP210x USB-to-UART adapter on COM3; if it is not the ESP32, use the COM port that appears when the board is connected. Upload.
5. Open Serial Monitor at **115200 baud**. Expect `[INA219] Detected at 0x40` when present, `[WiFi] Connected. ESP32 IP: ...`, `[HTTP] Response: 200`, and `[Stats] Success: 1 | Failed: 0`. A connection-refused error means the host/port is unreachable; HTTP 422 means payload validation failed.
6. For INA219, with power disconnected before changing wiring, connect source positive to VIN+, load positive to VIN-, and share source/load ground. The measured input voltage is `bus voltage + shunt voltage`; it is panel voltage only with the panel on the source side. Never connect panel voltage to an ESP32 GPIO.

Windows currently classifies Ethernet as **Public**. In elevated PowerShell, if the ESP32 has an address in the laptop's `192.168.32.0/20` subnet, run `New-NetFirewallRule -DisplayName "Solary API 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Public -RemoteAddress 192.168.32.0/20`. Otherwise replace that remote range with the ESP32 IP printed in Serial Monitor. Do not expose development ports to public networks.

## API endpoints

Key routes:

- `GET /health`
- `GET /api/readings`
- `GET /api/history`
- `GET /api/anomalies`
- `GET /api/anomalies/thresholds`
- `POST /api/anomalies/test`
- `GET /api/forecast?horizon=12|24`
- `GET /api/sensor-health`
- `POST /api/ingest`
- `GET /api/faults`
- `POST /api/faults/predict`

`GET /api/readings` reports fresh readings as `ESP32` and old ones as `ESP32 (STALE)`. `GET /api/history` returns retained real readings only. `GET /api/sensor-health` distinguishes sensor data freshness and INA219 validation status. The backend accepts optional `temperature_c`, `humidity_pct`, `ldr_raw`, `lux`, `voltage_v`, `current_ma`, and `power_mw`; invalid fields receive HTTP 422. Missing or null timestamps are assigned by the server.

INA219 measurements are withheld by default. After physically checking the sensor's placement and comparing voltage/current against a suitable meter/load, set `$env:SOLARY_INA219_MEASUREMENTS_VALIDATED='true'` in the backend PowerShell process before starting Uvicorn. Then the existing dashboard Live Monitoring cards and history expose real voltage/current/power; until then those values remain unavailable rather than showing unvalidated numbers. No lux sensor is installed in this wiring, so firmware sends `lux: null`. Disconnect panel/load power before changing wiring; never put a multimeter in current mode directly across the panel.

When the ESP32 is USB-connected but its Wi-Fi cannot route to the laptop Ethernet, the optional `backend/serial_bridge.ps1` can forward the existing sketch's actual serial measurements to `/api/ingest`: close Arduino Serial Monitor, keep the board connected on COM3, then run `.\serial_bridge.ps1 -PortName COM3` from the backend folder. This is a USB serial relay, not proof that ESP32 Wi-Fi HTTP works; keep it running for live dashboard updates. Stop with Ctrl+C.

Troubleshooting: HTTP 404 means check the exact `/api/ingest` path; HTTP 422 includes the invalid payload detail. ESP32 connection failures or timeouts usually indicate a wrong PC Wi-Fi IPv4, devices on different networks, Uvicorn not listening on `0.0.0.0`, or a missing Windows Firewall rule. A browser CORS error usually means the dashboard origin is not localhost or a private IPv4 address, or the custom API URL in Configuration is wrong. `0.0.0.0` is only the server bind address, never the URL used by the ESP32 or browser. If localhost reports `DEMO` while the PC's LAN IPv4 reports `ESP32`, check `Get-NetTCPConnection -State Listen -LocalPort 8000`: stop the loopback-only Uvicorn process and keep one server started with the project venv and `--host 0.0.0.0`. Separate Uvicorn processes have separate in-memory stores.

## AI model status and limitations

The project contains a trained image-classification model package at `Fault_Detection_Integration/model/FINAL_88_32_MODEL.weights.h5` and a matching script in `Fault_Detection_Integration/predict_final.py`.

Confirmed from source:

- Model type: MobileNetV2 classifier
- Fault classes: MultiHotSpot, SingleHotSpot, StringOpenCircuit
- Input workflow: original solar panel image + YOLO-format `.txt` annotation file
- Cropping strategy: bounding-box-based context crop with 30% padding

The classifier runtime is pinned in `backend/requirements.txt` and `Fault_Detection_Integration/requirements.txt`. The dashboard's image-upload interface remains separate from ESP32 telemetry.

## Forecasting methodology

The current forecast implementation is a baseline, not a trained ML model.

- Horizon options: 12h and 24h
- Output: hourly `predicted_power_w` and `energy_kwh`
- Source label: `BASELINE`
- Limitation: it uses a sinusoidal daylight heuristic and does not use actual weather or trained forecast models

This matches the project requirement to keep the forecast clearly labelled as an estimate rather than as actual production weather prediction.

## Sensor and demo-data behavior

- Demo data: clearly flagged as `DEMO` and used only before any real upload.
- Live data: flagged as `ESP32` when a server-received reading is less than 30 seconds old.
- Stale data: flagged as `ESP32 (STALE)` after 30 seconds without an upload.
- Missing and invalid fields are distinct: missing values are listed in `missing_fields`; invalid payloads receive HTTP 422.
- INA219 electrical measurements are sent by firmware when detected, but are withheld by the API unless `SOLARY_INA219_MEASUREMENTS_VALIDATED=true` is explicitly configured after physical validation.
- Stored history is capped at 17,280 entries (24 hours at five-second sampling), saved every ten readings, and loaded after backend restart. History charts are limited to 288 points.

## Test instructions

From the backend virtual environment:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -c "from main import app; print('OK')"
python -m unittest discover -s tests -v
```

Backend syntax and API smoke test:

```powershell
cd backend
.\.venv\Scripts\python.exe -m py_compile main.py
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/readings
Invoke-RestMethod http://127.0.0.1:8000/api/history
Invoke-RestMethod 'http://127.0.0.1:8000/api/forecast?horizon=12'
```

Controlled ingestion smoke test (this creates a real stored API reading, but does not prove physical ESP32 integration):

```powershell
$payload = @{ device_id = 'api-smoke-test'; timestamp = [DateTime]::UtcNow.ToString('o'); temperature_c = 24.5; humidity_pct = 48; ldr_raw = 1730 } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/ingest -Method Post -ContentType 'application/json' -Body $payload
Invoke-RestMethod http://127.0.0.1:8000/api/readings
Invoke-RestMethod http://127.0.0.1:8000/api/history
```

Frontend build verification:

```powershell
cd frontend
npm install
npm run build
```

## Known limitations

- INA219 electrical validation is still pending physical wiring and live-load measurements; until then the backend intentionally withholds these values from dashboard readings.
- Real fault inference still requires a valid solar-panel image and matching YOLO annotation sample; the compatible TensorFlow runtime is installed in the project virtual environment.
- The dashboard intentionally distinguishes model predictions, baseline estimates, and simulated data.

## Final status

Completed and verified:

- dashboard build
- backend health and readings API
- ingestion validation and data-label behaviour
- forecast baseline and 12H/24H toggle
- alert status pages and sensor-health contract

Blocked or pending hardware/software work:

- live INA219 validation under actual load
- real AI inference from the trained model on a valid test sample
- physical ESP32-to-backend-to-dashboard validation on the same LAN
- INA219 measurement validation under a real panel/load circuit
