# Sensor Status — Solar Monitor

> **Last updated:** Initial commit (hardware integration phase)

## Status Summary

| Sensor | Status | Notes |
|--------|--------|-------|
| ESP32 DevKit V1 | ✅ **WORKING** | Serial communication confirmed on COM3. I2C bus operational. |
| LDR Module | ✅ **WORKING** | Produces varying analog readings (0–4095) based on ambient light. Tested successfully. |
| BH1750 | ✅ **WORKING** | Detected at I2C address 0x23. Produces calibrated lux readings (~20, 85, 88 lux observed). |
| DHT11 | ⚠️ **FAULTY** | Produces unrealistic readings (~1–2 °C, low humidity). Wiring and code verified — the sensor unit itself is defective. Will be replaced with another DHT11. |
| INA219 | 🔧 **TESTING** | Soldered onto the board. I2C communication has **not** been confirmed yet. Hardware integration is being performed one wire at a time. VIN+/VIN− are **not** connected to the solar panel. |
| DS18B20 | 📋 **PLANNED** | Not purchased / not connected. Intended for solar-panel surface temperature measurement. |

## How Each Status Was Established

### ESP32
- Uploaded test sketches via Arduino IDE.
- Serial output confirmed at 115200 baud on COM3.
- I2C scanner sketch detected connected devices.

### LDR
- Connected AO to GPIO 34.
- `analogRead(34)` returns varying values when light conditions change.
- Confirmed working across different light levels.

### BH1750
- I2C scanner detected device at address **0x23**.
- BH1750 library initialisation succeeded.
- Lux readings change with ambient lighting.

### DHT11
- Wired to GPIO 4 with appropriate pull-up.
- `dht.readTemperature()` and `dht.readHumidity()` return values, but they are physically incorrect (~1–2 °C indoors).
- Conclusion: the sensor module is defective. Code and wiring are correct.

### INA219
- Physically soldered.
- I2C communication has **not** been tested yet.
- Will be tested first with only VCC, GND, SDA, SCL connected (no solar panel).
- Solar panel connection to VIN+ / VIN− will follow after I2C is confirmed.

### DS18B20
- Not yet acquired / connected.
- Planned for future integration.
