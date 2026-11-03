/*
 * ============================================================
 *  AI-Based Solar Panel Fault Detection & Energy Forecasting
 *  ESP32 Sensor Monitoring Firmware with WiFi HTTP Reporting
 * ============================================================
 *
 *  Microcontroller : ESP32 DevKit V1 (DOIT ESP32 DEVKIT V1)
 *  Serial          : 115200 baud
 *
 *  Sensors:
 *    - DHT11    → GPIO 4   (Temperature & Humidity)
 *    - LDR      → GPIO 34  (Analog light level, raw ADC 0-4095)
 *    - INA219   → I2C 0x40 (detected if present; values withheld pending validation)
 *
 *  I2C Bus:
 *    SDA = GPIO 21
 *    SCL = GPIO 22
 *
 *  WiFi: Connects to local network and sends readings via HTTP POST
 *
 *  IMPORTANT:
 *    - ESP32 is powered via USB, NOT through the solar panel circuit
 *    - INA219 values remain disabled until actual measurements are validated
 *    - DHT11 may need replacement if producing bad readings
 *    - LDR value is raw 12-bit ADC (0-4095), NOT lux
 *
 * ============================================================
 */

// ── Libraries ───────────────────────────────────────────────
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_INA219.h>
#include <time.h>
#include "wifi_config.h"

// Device identifier
const char* DEVICE_ID = "esp32-01";

// Reading interval in milliseconds (how often to read sensors and send data)
const unsigned long READING_INTERVAL_MS = 5000;  // 5 seconds

// HTTP request timeout in milliseconds
const int HTTP_TIMEOUT_MS = 5000;

// Maximum WiFi connection retries before continuing without WiFi
const int WIFI_MAX_RETRIES = 20;

// Maximum HTTP send retries per reading
const int HTTP_MAX_RETRIES = 2;

// ── Pin Definitions ─────────────────────────────────────────
#define DHT_PIN   4        // DHT11 data pin (GPIO 4)
#define DHT_TYPE  DHT11    // Sensor type
#define LDR_PIN   34       // LDR analog output (GPIO 34, input-only)
#define I2C_SDA   21       // I2C Data
#define I2C_SCL   22       // I2C Clock

// ── Sensor Objects ──────────────────────────────────────────
DHT dht(DHT_PIN, DHT_TYPE);
Adafruit_INA219 ina219;

// ── State ───────────────────────────────────────────────────
bool ina219Available = false;
bool ina219Detected = false;
bool wifiConnected   = false;
unsigned long previousMillis = 0;
unsigned long sendSuccessCount = 0;
unsigned long sendFailCount    = 0;
unsigned long readingCount     = 0;

// ============================================================
//  WiFi Connection
// ============================================================
void connectWiFi() {
  Serial.println("[WiFi] Connecting to configured network...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < WIFI_MAX_RETRIES) {
    delay(500);
    Serial.print(".");
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println();
    Serial.print("[WiFi] Connected! IP: ");
    Serial.println(WiFi.localIP());
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  } else {
    wifiConnected = false;
    Serial.println();
    Serial.println("[WiFi] *** CONNECTION FAILED ***");
    Serial.println("[WiFi] Sensor readings will continue (Serial only).");
    Serial.println("[WiFi] Check SSID and password, then restart.");
  }
}

// ============================================================
//  HTTP POST — Send sensor data to backend
// ============================================================
bool sendToBackend(float temperature, float humidity, int ldrRaw,
                   float voltage, float currentMA, float powerMW) {

  if (WiFi.status() != WL_CONNECTED) {
    // Try to reconnect
    Serial.println("[HTTP] WiFi disconnected. Attempting reconnection...");
    connectWiFi();
    if (!wifiConnected) return false;
  }

  // Build JSON payload
  String json = "{";
  json += "\"device_id\":\"" + String(DEVICE_ID) + "\"";

  time_t now = time(nullptr);
  if (now > 1700000000) {
    struct tm utcTime;
    char timestamp[25];
    gmtime_r(&now, &utcTime);
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &utcTime);
    json += ",\"timestamp\":\"" + String(timestamp) + "\"";
  } else {
    Serial.println("[TIME] NTP not synchronized; backend will timestamp receipt.");
  }

  // Temperature (skip if NaN — sensor error)
  if (!isnan(temperature)) {
    json += ",\"temperature_c\":" + String(temperature, 1);
  }

  // Humidity (skip if NaN)
  if (!isnan(humidity)) {
    json += ",\"humidity_pct\":" + String(humidity, 1);
  }

  // LDR (always valid, 0-4095)
  json += ",\"ldr_raw\":" + String(ldrRaw);

  // INA219 (only include if sensor is available and values are valid)
  if (ina219Available && !isnan(voltage) && voltage >= 0) {
    json += ",\"voltage_v\":" + String(voltage, 3);
  }
  if (ina219Available && !isnan(currentMA) && currentMA >= 0) {
    json += ",\"current_ma\":" + String(currentMA, 2);
  }
  if (ina219Available && !isnan(powerMW) && powerMW >= 0) {
    json += ",\"power_mw\":" + String(powerMW, 2);
  }

  json += "}";

  // Send HTTP POST with retries
  for (int attempt = 0; attempt < HTTP_MAX_RETRIES; attempt++) {
    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.setConnectTimeout(HTTP_TIMEOUT_MS);

    Serial.print("[HTTP] Sending to ");
    Serial.print(SERVER_URL);
    if (attempt > 0) {
      Serial.print(" (retry ");
      Serial.print(attempt);
      Serial.print(")");
    }
    Serial.println();

    int httpCode = http.POST(json);

    if (httpCode > 0) {
      Serial.print("[HTTP] Response: ");
      Serial.println(httpCode);

      if (httpCode >= 200 && httpCode < 300) {
        String response = http.getString();
        Serial.print("[HTTP] Body: ");
        Serial.println(response.substring(0, 120));  // Print first 120 chars
        http.end();
        sendSuccessCount++;
        return true;
      } else {
        Serial.print("[HTTP] Server error: ");
        Serial.println(http.getString().substring(0, 200));
        if (httpCode >= 400 && httpCode < 500) {
          Serial.println("[HTTP] Request rejected; check endpoint and JSON payload.");
          http.end();
          break;
        }
      }
    } else {
      Serial.print("[HTTP] Connection failed: ");
      Serial.println(http.errorToString(httpCode));
    }

    http.end();

    // Wait briefly before retry
    if (attempt < HTTP_MAX_RETRIES - 1) {
      delay(1000);
    }
  }

  sendFailCount++;
  return false;
}

// ============================================================
//  SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("================================================");
  Serial.println("  Solar Monitor — ESP32 WiFi Sensor Node");
  Serial.println("  AI-Based Solar Panel Fault Detection");
  Serial.println("================================================");
  Serial.println();

  // ── ADC Resolution ─────────────────────────────────────────
  analogReadResolution(12);  // 0-4095

  // ── I2C Bus ────────────────────────────────────────────────
  Wire.begin(I2C_SDA, I2C_SCL);
  Serial.println("[I2C]    Bus initialised (SDA=GPIO21, SCL=GPIO22)");

  // ── DHT11 ──────────────────────────────────────────────────
  dht.begin();
  Serial.println("[DHT11]  Initialised on GPIO 4");

  // ── LDR ────────────────────────────────────────────────────
  // GPIO 34 is input-only; no pinMode needed for analogRead
  Serial.println("[LDR]    Ready on GPIO 34 (12-bit ADC)");

  // ── INA219 ─────────────────────────────────────────────────
  if (ina219.begin()) {
    ina219.setCalibration_32V_2A();
    ina219Detected = true;
    ina219Available = false;
    Serial.println("[INA219] Detected at I2C 0x40; measurements withheld pending validation");
  } else {
    ina219Available = false;
    Serial.println("[INA219] NOT FOUND — VIN+/VIN- not connected to panel");
    Serial.println("         (This is expected until physical wiring is complete)");
  }

  // ── WiFi ───────────────────────────────────────────────────
  connectWiFi();

  // ── Summary ────────────────────────────────────────────────
  Serial.println();
  Serial.println("──── Sensor Status ────");
  Serial.println("  ESP32   : OK");
  Serial.println("  DHT11   : Initialised");
  Serial.println("  LDR     : OK");
  Serial.print(  "  INA219  : ");
  Serial.println(ina219Detected ? "DETECTED (VALUES WITHHELD)" : "NOT FOUND");
  Serial.print(  "  WiFi    : ");
  Serial.println(wifiConnected ? "CONNECTED" : "DISCONNECTED");
  Serial.println();
  Serial.print("  Server  : ");
  Serial.println(SERVER_URL);
  Serial.print("  Interval: ");
  Serial.print(READING_INTERVAL_MS);
  Serial.println(" ms");
  Serial.println("──────────────────────");
  Serial.println();
  Serial.println("Starting sensor loop...");
  Serial.println();
}

// ============================================================
//  LOOP — Non-blocking sensor reading + HTTP sending
// ============================================================
void loop() {
  unsigned long currentMillis = millis();

  // Only read and send at the configured interval
  if (currentMillis - previousMillis < READING_INTERVAL_MS) {
    return;
  }
  previousMillis = currentMillis;
  readingCount++;

  // ── Read DHT11 ─────────────────────────────────────────────
  float temperature = dht.readTemperature();   // °C
  float humidity    = dht.readHumidity();       // %

  // ── Read LDR ───────────────────────────────────────────────
  int ldrRaw = analogRead(LDR_PIN);  // 0-4095

  // ── Read INA219 ────────────────────────────────────────────
  float voltage   = NAN;
  float currentMA = NAN;
  float powerMW   = NAN;

  if (ina219Available) {
    voltage   = ina219.getBusVoltage_V();
    currentMA = ina219.getCurrent_mA();
    powerMW   = ina219.getPower_mW();
  }

  // ── Serial Output (human-readable) ─────────────────────────
  Serial.println("──────── SENSOR DATA ────────");
  Serial.print("Reading #");
  Serial.println(readingCount);

  Serial.print("  Temperature: ");
  if (isnan(temperature)) {
    Serial.println("READ ERROR");
  } else {
    Serial.print(temperature, 1);
    Serial.println(" °C");
  }

  Serial.print("  Humidity:    ");
  if (isnan(humidity)) {
    Serial.println("READ ERROR");
  } else {
    Serial.print(humidity, 1);
    Serial.println(" %");
  }

  Serial.print("  LDR ADC:     ");
  Serial.println(ldrRaw);

  if (ina219Available) {
    Serial.print("  Voltage:     ");
    Serial.print(voltage, 3);
    Serial.println(" V");
    Serial.print("  Current:     ");
    Serial.print(currentMA, 2);
    Serial.println(" mA");
    Serial.print("  Power:       ");
    Serial.print(powerMW, 2);
    Serial.println(" mW");
  } else {
    Serial.println("  INA219:      NOT CONNECTED");
  }

  // ── Send via HTTP ──────────────────────────────────────────
  if (wifiConnected || WiFi.status() == WL_CONNECTED) {
    bool ok = sendToBackend(temperature, humidity, ldrRaw,
                            voltage, currentMA, powerMW);
    Serial.print("[Stats] Success: ");
    Serial.print(sendSuccessCount);
    Serial.print(" | Failed: ");
    Serial.println(sendFailCount);
  } else {
    Serial.println("[WiFi] Not connected — data printed to Serial only");
  }

  Serial.println("─────────────────────────────");
  Serial.println();
}
