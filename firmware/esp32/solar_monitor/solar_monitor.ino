/*
 * ============================================================
 *  AI-Based Solar Panel Fault Detection & Energy Forecasting
 *  ESP32 Combined Sensor Monitoring Firmware
 * ============================================================
 *
 *  Microcontroller : ESP32 DevKit V1 (DOIT ESP32 DEVKIT V1)
 *  Serial          : 115200 baud (COM3)
 *
 *  Sensors:
 *    - DHT11    → GPIO 4   (Temperature & Humidity)
 *    - LDR      → GPIO 34  (Analog light level, raw ADC)
 *    - BH1750   → I2C 0x23 (Lux)
 *    - INA219   → I2C 0x40 (Voltage, Current, Power)
 *
 *  I2C Bus:
 *    SDA = GPIO 21
 *    SCL = GPIO 22
 *
 *  STATUS (as of initial commit):
 *    ESP32   — WORKING
 *    LDR     — WORKING
 *    BH1750  — WORKING
 *    DHT11   — FAULTY (replacement pending)
 *    INA219  — NOT YET TESTED
 *    DS18B20 — PLANNED (not connected)
 *
 *  NOTES:
 *    - DHT11 support is kept in the code so that a replacement
 *      sensor works without any software changes.
 *    - INA219 initialisation is attempted every boot; if the
 *      sensor is not found the sketch continues without it.
 *    - The LDR value is a raw 12-bit ADC reading (0-4095).
 *      Do NOT interpret it as lux.
 *    - ESP32 must NOT be placed in series with the solar panel
 *      measurement path.  It is powered separately via USB.
 *
 * ============================================================
 */

// ── Libraries ───────────────────────────────────────────────
#include <Wire.h>          // I2C communication
#include <DHT.h>           // DHT temperature & humidity sensor
#include <BH1750.h>        // BH1750 digital light sensor (Christopher Laws library)
#include <Adafruit_INA219.h> // INA219 current/voltage/power sensor

// ── Pin Definitions ─────────────────────────────────────────
#define DHTPIN   4         // DHT11 data pin (GPIO 4)
#define DHTTYPE  DHT11     // Sensor type
#define LDR_PIN  34        // LDR analog output (GPIO 34)

// I2C pins (shared by BH1750 and INA219)
#define I2C_SDA  21        // GPIO 21
#define I2C_SCL  22        // GPIO 22

// ── Sensor Objects ──────────────────────────────────────────
DHT dht(DHTPIN, DHTTYPE);
BH1750 lightMeter;
Adafruit_INA219 ina219;

// ── Availability Flags ──────────────────────────────────────
// These flags are set during setup() and checked in loop()
// to avoid reading from sensors that are not connected.
bool bh1750Available = false;
bool ina219Available = false;

// ── Timing ──────────────────────────────────────────────────
unsigned long previousMillis = 0;
const unsigned long readingInterval = 2000; // milliseconds between readings

// ============================================================
//  SETUP
// ============================================================
void setup() {
  // ── Serial ────────────────────────────────────────────────
  Serial.begin(115200);
  delay(1000); // give Serial time to initialise
  Serial.println();
  Serial.println("========================================");
  Serial.println("  Solar Monitor — Sensor Initialisation");
  Serial.println("========================================");
  Serial.println();

  // ── I2C Bus ───────────────────────────────────────────────
  Wire.begin(I2C_SDA, I2C_SCL);
  Serial.println("[I2C]    Bus initialised (SDA=GPIO21, SCL=GPIO22)");

  // ── DHT11 ─────────────────────────────────────────────────
  dht.begin();
  Serial.println("[DHT11]  Initialised on GPIO 4");
  Serial.println("         NOTE: Current sensor is FAULTY — readings may be unreliable.");

  // ── LDR ───────────────────────────────────────────────────
  // GPIO 34 is input-only on ESP32; no pinMode needed for analogRead.
  Serial.println("[LDR]    Ready on GPIO 34 (analog input)");

  // ── BH1750 ────────────────────────────────────────────────
  if (lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE)) {
    bh1750Available = true;
    Serial.println("[BH1750] Initialised at I2C address 0x23");
  } else {
    bh1750Available = false;
    Serial.println("[BH1750] *** NOT FOUND — check wiring ***");
  }

  // ── INA219 ────────────────────────────────────────────────
  if (ina219.begin()) {
    ina219.setCalibration_32V_2A();
    ina219Available = true;
    Serial.println("[INA219] Initialised at I2C address 0x40");
  } else {
    ina219Available = false;
    Serial.println("[INA219] *** NOT FOUND — sensor not connected or not detected ***");
  }

  // ── Summary ───────────────────────────────────────────────
  Serial.println();
  Serial.println("Sensor Status Summary:");
  Serial.println("  ESP32   : WORKING");
  Serial.println("  DHT11   : INITIALISED (sensor known faulty)");
  Serial.print(  "  BH1750  : "); Serial.println(bh1750Available ? "WORKING" : "NOT FOUND");
  Serial.print(  "  LDR     : WORKING");
  Serial.println();
  Serial.print(  "  INA219  : "); Serial.println(ina219Available ? "DETECTED" : "NOT FOUND");
  Serial.println();
  Serial.println("========================================");
  Serial.println("  Starting sensor readings...");
  Serial.println("========================================");
  Serial.println();
}

// ============================================================
//  LOOP
// ============================================================
void loop() {
  unsigned long currentMillis = millis();

  // Only read sensors at the defined interval
  if (currentMillis - previousMillis < readingInterval) {
    return;
  }
  previousMillis = currentMillis;

  // ── DHT11 Readings ────────────────────────────────────────
  float temperature = dht.readTemperature();  // °C
  float humidity    = dht.readHumidity();      // %

  // ── LDR Reading ───────────────────────────────────────────
  int ldrValue = analogRead(LDR_PIN);  // 0–4095 (12-bit ADC)

  // ── BH1750 Reading ────────────────────────────────────────
  float lux = -1;
  if (bh1750Available) {
    lux = lightMeter.readLightLevel();
  }

  // ── INA219 Readings ───────────────────────────────────────
  float busVoltage = -1;
  float current_mA = -1;
  float power_mW   = -1;
  if (ina219Available) {
    busVoltage = ina219.getBusVoltage_V();
    current_mA = ina219.getCurrent_mA();
    power_mW   = ina219.getPower_mW();
  }

  // ── Print Sensor Data ─────────────────────────────────────
  Serial.println("========================================");
  Serial.println("          SENSOR DATA");
  Serial.println("========================================");
  Serial.println();

  // DHT11
  Serial.println("DHT11:");
  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("  Temperature : READ ERROR");
    Serial.println("  Humidity    : READ ERROR");
  } else {
    Serial.print(  "  Temperature : "); Serial.print(temperature); Serial.println(" °C");
    Serial.print(  "  Humidity    : "); Serial.print(humidity);    Serial.println(" %");
  }
  Serial.println();

  // LDR
  Serial.println("LDR:");
  Serial.print(  "  Analog Value: "); Serial.println(ldrValue);
  Serial.println();

  // BH1750
  Serial.println("BH1750:");
  if (bh1750Available) {
    Serial.print(  "  Light       : "); Serial.print(lux); Serial.println(" lux");
  } else {
    Serial.println("  Light       : SENSOR NOT AVAILABLE");
  }
  Serial.println();

  // INA219
  Serial.println("INA219:");
  if (ina219Available) {
    Serial.print(  "  Voltage     : "); Serial.print(busVoltage); Serial.println(" V");
    Serial.print(  "  Current     : "); Serial.print(current_mA); Serial.println(" mA");
    Serial.print(  "  Power       : "); Serial.print(power_mW);   Serial.println(" mW");
  } else {
    Serial.println("  Voltage     : NOT CONNECTED");
    Serial.println("  Current     : NOT CONNECTED");
    Serial.println("  Power       : NOT CONNECTED");
  }

  // ── Key=Value block (easy to parse from Python) ──────────
  Serial.println();
  Serial.println("----------------------------------------");
  Serial.print(  "Temperature=");  Serial.println(isnan(temperature) ? String("NaN") : String(temperature));
  Serial.print(  "Humidity=");     Serial.println(isnan(humidity)    ? String("NaN") : String(humidity));
  Serial.print(  "LDR=");          Serial.println(ldrValue);
  Serial.print(  "Lux=");          Serial.println(lux);
  Serial.print(  "Voltage=");      Serial.println(busVoltage);
  Serial.print(  "Current_mA=");   Serial.println(current_mA);
  Serial.print(  "Power_mW=");     Serial.println(power_mW);
  Serial.println("========================================");
  Serial.println();
}
