# Project Architecture — AI-Based Solar Panel Fault Detection & Energy Forecasting

## System Overview

This project is an end-to-end pipeline from physical sensor data collection through machine-learning analysis to visual reporting.

## Data Pipeline

```
Solar / Environmental Sensors
        │
        ▼
    ESP32 Microcontroller
        │
        ▼
    Sensor Readings
    (Temperature, Humidity, Light, Voltage, Current, Power)
        │
        ▼
    Serial / Future Wi-Fi Transmission
        │
        ▼
    Data Collection (Python serial reader)
        │
        ▼
    Data Preprocessing
    (Cleaning, normalisation, feature engineering)
        │
        ▼
    Structured Dataset (CSV / Database)
        │
        ▼
    Machine Learning
    ├── Energy Forecasting
    └── Anomaly / Fault Detection
        │
        ▼
    Dashboard / Reporting
```

## Current Status

| Layer | Status |
|-------|--------|
| Sensor Hardware | Partially integrated (see `hardware/sensor_status.md`) |
| ESP32 Firmware | Initial version complete (`firmware/esp32/solar_monitor/`) |
| Serial Data Reader | Not yet built |
| Data Storage | Not yet built |
| Preprocessing | Not yet built |
| ML Models | Not yet built |
| Dashboard | Not yet built |

## Planned Feature Set

The final dataset is expected to contain the following features:

| Feature | Source | Unit |
|---------|--------|------|
| Temperature | DHT11 | °C |
| Humidity | DHT11 | % |
| LDR Light Level | LDR (analog) | Raw ADC (0–4095) |
| Lux | BH1750 | lux |
| Solar Panel Voltage | INA219 | V |
| Solar Panel Current | INA219 | mA |
| Solar Panel Power | INA219 | mW |
| Timestamp | System clock | ISO 8601 |
| Historical Energy | Computed | Wh (cumulative) |

## Planned ML Approaches

> ⚠️ **None of these models have been implemented yet.**

### Energy Forecasting

| Model | Rationale |
|-------|-----------|
| LSTM (Long Short-Term Memory) | Captures long-term temporal dependencies in energy production |
| Prophet | Handles trend and seasonality; robust to missing data |

### Anomaly / Fault Detection

| Model | Rationale |
|-------|-----------|
| Isolation Forest | Unsupervised; effective for tabular outlier detection |
| Autoencoder | Learns normal operating patterns; flags deviations as anomalies |

## Component Ownership

| Directory | Responsibility |
|-----------|----------------|
| `hardware/` | Wiring, pinout, sensor status documentation |
| `firmware/` | ESP32 Arduino sketches |
| `data/` | Data collection scripts, raw data, processed datasets |
| `ml/` | Model training, evaluation, Jupyter notebooks |
| `dashboard/` | Visualisation and user interface |
| `docs/` | Architecture, design decisions, references |
