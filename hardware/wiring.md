# Wiring Guide — Solar Monitor

## Overview

All sensors connect to a single **ESP32 DevKit V1 (DOIT)** board.  
The I2C bus (GPIO 21 SDA, GPIO 22 SCL) is shared between the BH1750 and INA219.

---

## DHT11 → ESP32

| DHT11 Pin | ESP32 Pin |
|-----------|-----------|
| VCC | 3.3 V |
| DATA | GPIO 4 |
| GND | GND |

> ⚠️ The current DHT11 unit is **faulty** and will be replaced.  
> A 10 kΩ pull-up resistor between DATA and VCC is recommended (some modules have one built in).

---

## LDR Module → ESP32

| LDR Pin | ESP32 Pin |
|---------|-----------|
| VCC | 3.3 V |
| AO | GPIO 34 |
| GND | GND |

- Only the **analog output (AO)** is used.
- The **digital output (DO)** is not connected.

---

## BH1750 → ESP32

| BH1750 Pin | ESP32 Pin |
|------------|-----------|
| VCC | 3.3 V |
| GND | GND |
| SDA | GPIO 21 |
| SCL | GPIO 22 |
| ADDR | Not connected |

- ADDR left disconnected → default I2C address **0x23**.
- Confirmed working via I2C scanner.

---

## INA219 → ESP32

| INA219 Pin | ESP32 Pin / Connection |
|------------|------------------------|
| VCC | 3.3 V |
| GND | GND |
| SDA | GPIO 21 (shared I2C) |
| SCL | GPIO 22 (shared I2C) |
| VIN+ | Solar panel + (via fuse) — **NOT YET CONNECTED** |
| VIN− | DC load + — **NOT YET CONNECTED** |

> 🔧 **INA219 has been soldered but I2C communication has not yet been confirmed.**  
> The solar panel will not be connected to VIN+ / VIN− until I2C is verified.

### Future Electrical Path

```
Solar Panel (+) → Fuse → INA219 VIN+ → INA219 VIN− → DC Load (+)
Solar Panel (−) → DC Load (−)
```

> ⚠️ The ESP32 is powered **separately** through USB / battery.  
> It must **never** be placed in series with the solar panel measurement path.

---

## DS18B20 (Planned)

- **Not currently connected.**
- Will use OneWire protocol.
- Pin assignment to be determined during integration.

---

## Wiring Diagram

A visual wiring diagram will be added after all sensors are integrated and tested.
