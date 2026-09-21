# ESP32 Pin Mapping — Solar Monitor

## I2C Bus (Shared)

> **GPIO 21 (SDA)** and **GPIO 22 (SCL)** are shared I2C lines used by both the BH1750 and INA219.

## Pin Table

| Component | Component Pin | ESP32 Connection | Purpose | Status |
|-----------|--------------|------------------|---------|--------|
| DHT11 | OUT (Data) | GPIO 4 (D4) | Temperature & Humidity | ⚠️ Faulty sensor |
| LDR Module | AO (Analog Out) | GPIO 34 (D34) | Relative light level (raw ADC) | ✅ Working |
| BH1750 | SDA | GPIO 21 (D21) | I2C Data | ✅ Working |
| BH1750 | SCL | GPIO 22 (D22) | I2C Clock | ✅ Working |
| BH1750 | VCC | 3.3 V | Power supply | ✅ Working |
| BH1750 | GND | GND | Ground | ✅ Working |
| BH1750 | ADDR | Not connected | Address select (defaults to 0x23) | — |
| INA219 | SDA | GPIO 21 (D21) | I2C Data (shared) | 🔧 Not yet tested |
| INA219 | SCL | GPIO 22 (D22) | I2C Clock (shared) | 🔧 Not yet tested |
| INA219 | VCC | 3.3 V | Power supply | 🔧 Not yet tested |
| INA219 | GND | GND | Ground | 🔧 Not yet tested |
| INA219 | VIN+ | Solar panel (via fuse) | Current measurement input | ⏳ Not connected |
| INA219 | VIN− | DC load (+) | Current measurement output | ⏳ Not connected |

## Notes

- **LDR digital output (DO)** is not used; only the analog output is connected.
- **INA219 VIN+ / VIN−** carry the solar panel measurement current. They are **not** I2C lines.
- **ESP32** is powered via USB, **not** through the solar panel circuit.
- **DS18B20** is a planned sensor and is not yet connected to any pin.
