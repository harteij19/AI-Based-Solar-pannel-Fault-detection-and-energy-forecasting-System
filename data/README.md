# Data

This directory will contain:

- **Serial data reader** — Python script to read sensor data from the ESP32 via serial port.
- **Raw data** — Unprocessed sensor readings collected over time.
- **Processed datasets** — Cleaned and structured data ready for ML training.

## Status

🚧 **Not yet started.** The ESP32 firmware outputs structured serial data that can be captured by a Python script using `pyserial`.

## Planned Structure

```
data/
├── README.md
├── serial_reader.py      ← (to be built)
├── raw/                   ← raw serial captures
└── processed/             ← cleaned CSV datasets
```

## Dependencies (Planned)

- Python 3.x
- `pyserial`
- `pandas`
