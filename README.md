# AI-Based Solar Panel Fault Detection & Energy Forecasting System

> **Project Stage:** Hardware & Sensor Integration (Active Development)

## Objective

Build an end-to-end system that:

1. **Collects** environmental and electrical data from a solar panel using an ESP32 microcontroller and multiple sensors.
2. **Processes** the raw sensor data and stores it as a structured dataset.
3. **Applies machine-learning models** for:
   - Solar energy generation forecasting (time-series prediction).
   - Anomaly / fault detection on the solar panel.
4. **Visualises** results through a dashboard.

> **Note:** The ML models and dashboard are **planned** components.  
> The repository currently contains only the hardware documentation and sensor-acquisition firmware.

---

## Current Hardware Architecture

| Component | Model / Part | Interface | Status |
|-----------|-------------|-----------|--------|
| Microcontroller | ESP32 DevKit V1 (DOIT) | USB Serial (COM3) | ✅ Working |
| Temperature & Humidity | DHT11 | GPIO 4 (digital) | ⚠️ Faulty — replacement pending |
| Analog Light Sensor | LDR Module | GPIO 34 (analog) | ✅ Working |
| Digital Light Sensor | BH1750 | I2C (0x23) | ✅ Working |
| Voltage / Current / Power | INA219 | I2C (0x40) | 🔧 Not yet tested |
| Panel Temperature | DS18B20 | OneWire | 📋 Planned |

### I2C Bus

- **SDA:** GPIO 21  
- **SCL:** GPIO 22  
- Shared by BH1750 and INA219.

---

## Sensor Details

### DHT11 (GPIO 4)
- Measures temperature (°C) and humidity (%).
- **Current unit is faulty** — produces ~1–2 °C readings.  
- Code support is retained so the replacement sensor works without changes.

### LDR (GPIO 34)
- Analog output → ESP32 12-bit ADC (0–4095).
- Digital output is **not used**.
- Provides a **relative** light-level reading. The raw ADC value is **not** lux.

### BH1750 (I2C 0x23)
- Provides calibrated lux readings.
- Tested successfully (example readings: ~20 lux, 85 lux, 88 lux).
- Library: *BH1750 by Christopher Laws*.

### INA219 (I2C 0x40)
- Will measure bus voltage (V), current (mA), and power (mW) from the solar panel.
- **Not yet tested** — soldered but I2C communication not yet confirmed.
- VIN+ / VIN− carry the solar-panel measurement current; they are **not** I2C lines.
- The ESP32 is powered **separately** (USB); it must **never** be placed in series with the solar panel.

### DS18B20 (Planned)
- Will measure solar-panel surface temperature via OneWire.
- Not currently connected.

---

## ESP32 Pin Mapping

| ESP32 Pin | Connected To | Signal | Notes |
|-----------|-------------|--------|-------|
| GPIO 4 | DHT11 OUT | Digital | Temperature & Humidity |
| GPIO 34 | LDR AO | Analog (ADC) | Raw light level (0–4095) |
| GPIO 21 | BH1750 SDA / INA219 SDA | I2C Data | Shared bus |
| GPIO 22 | BH1750 SCL / INA219 SCL | I2C Clock | Shared bus |
| 3.3 V | BH1750 VCC / INA219 VCC | Power | — |
| GND | BH1750 GND / INA219 GND | Ground | — |

---

## Data Flow (Current → Planned)

```
Solar / Environmental Sensors
        │
        ▼
    ESP32 (firmware)
        │
        ▼
  Serial output (115200 baud)
        │
        ▼
  Python serial reader  ← (to be built)
        │
        ▼
  CSV / Database        ← (to be built)
        │
        ▼
  Data Preprocessing    ← (to be built)
        │
        ▼
  Machine Learning      ← (to be built)
   ├─ Energy Forecasting
   └─ Anomaly Detection
        │
        ▼
  Dashboard             ← (to be built)
```

---

## Planned ML Pipeline

The following approaches are **under consideration** and have **not** been implemented yet:

| Task | Candidate Models |
|------|------------------|
| Energy Forecasting | LSTM, Prophet |
| Anomaly Detection | Isolation Forest, Autoencoder |

**Planned feature set:**

- Temperature (°C)
- Humidity (%)
- LDR raw light level
- BH1750 lux
- Solar panel voltage (V)
- Solar panel current (mA)
- Solar panel power (mW)
- Timestamp
- Historical energy generation

---

## Planned Dashboard

A web-based or desktop dashboard is planned to:

- Display real-time sensor readings.
- Show energy-generation trends.
- Highlight detected faults or anomalies.
- Present ML model predictions.

No dashboard code exists yet.

---

## Repository Structure

```
/
├── README.md                     ← You are here
├── hardware/
│   ├── pinout.md                 ← ESP32 pin mapping
│   ├── wiring.md                 ← Wiring instructions
│   └── sensor_status.md          ← Current sensor status
├── firmware/
│   └── esp32/
│       └── solar_monitor/
│           └── solar_monitor.ino ← Main sensor sketch
├── data/
│   └── README.md                 ← Data collection (placeholder)
├── ml/
│   └── README.md                 ← ML models (placeholder)
├── dashboard/
│   └── README.md                 ← Dashboard (placeholder)
└── docs/
    └── project_architecture.md   ← System architecture
```

---

## Contributing

This is a college major project. The repository is structured so that team members can work independently:

| Area | Directory | Description |
|------|-----------|-------------|
| Hardware & Firmware | `hardware/`, `firmware/` | Sensor wiring, ESP32 code |
| Data Collection | `data/` | Serial readers, raw data, datasets |
| Machine Learning | `ml/` | Model training, evaluation, notebooks |
| Dashboard | `dashboard/` | Visualisation and UI |

### Guidelines

- Create a **branch** for any major change.
- Document new **dependencies** (libraries, Python packages, etc.).
- Do **not** commit Wi-Fi credentials, API keys, or secrets.
- Update the relevant `README.md` when adding components.

---

## License

This project is developed for academic Major project - Harteij V K Raju,Jeevan,Lohith G M,Rohan M.
