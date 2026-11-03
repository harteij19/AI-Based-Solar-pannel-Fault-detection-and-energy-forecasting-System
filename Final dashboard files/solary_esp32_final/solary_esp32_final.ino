/*
 * Solary ESP32 DevKit V1 telemetry firmware.
 * DHT11: GPIO 4; LDR: GPIO 34; INA219: SDA 21, SCL 22, address 0x40.
 *
 * INA219 VIN+ must connect to source positive and VIN- to load positive;
 * source and load grounds must be common. The reported input-side voltage
 * is bus voltage plus shunt voltage. It represents panel voltage only when
 * the panel is the source at VIN+ and the load is connected at VIN-.
 * Never connect panel voltage directly to an ESP32 GPIO.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_INA219.h>
#include <time.h>
#include <math.h>
#include "wifi_config.h"

const char* DEVICE_ID = "esp32-01";

constexpr uint8_t DHT_PIN = 4;
constexpr uint8_t LDR_PIN = 34;
constexpr uint8_t I2C_SDA_PIN = 21;
constexpr uint8_t I2C_SCL_PIN = 22;
constexpr unsigned long READING_INTERVAL_MS = 5000;
constexpr unsigned long HTTP_TIMEOUT_MS = 5000;
constexpr int WIFI_MAX_RETRIES = 20;
constexpr int HTTP_MAX_RETRIES = 2;

DHT dht(DHT_PIN, DHT11);
Adafruit_INA219 ina219;

bool ina219Detected = false;
bool wifiConnected = false;
unsigned long previousMillis = 0;
unsigned long readingCount = 0;
unsigned long sendSuccessCount = 0;
unsigned long sendFailCount = 0;

void connectWiFi() {
  Serial.println("[WiFi] Connecting...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < WIFI_MAX_RETRIES) {
    delay(500);
    Serial.print(".");
    ++retries;
  }

  wifiConnected = WiFi.status() == WL_CONNECTED;
  if (wifiConnected) {
    Serial.println();
    Serial.print("[WiFi] Connected. ESP32 IP: ");
    Serial.println(WiFi.localIP());
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  } else {
    Serial.println();
    Serial.println("[WiFi] Connection failed; readings will continue locally.");
  }
}

void appendFloatOrNull(String& json, const char* key, float value,
                       unsigned int decimals, bool valid) {
  json += ",\"";
  json += key;
  json += "\":";
  if (valid && isfinite(value)) {
    json += String(value, decimals);
  } else {
    json += "null";
  }
}

bool sendToBackend(float temperature, float humidity, int ldrRaw,
                   float voltage, float currentMA, float powerMW) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] Wi-Fi disconnected; reconnecting.");
    connectWiFi();
    if (!wifiConnected) {
      ++sendFailCount;
      return false;
    }
  }

  String json;
  json.reserve(240);
  json = "{\"device_id\":\"";
  json += DEVICE_ID;
  json += "\"";

  const time_t now = time(nullptr);
  if (now > 1700000000) {
    struct tm utcTime;
    char timestamp[25];
    gmtime_r(&now, &utcTime);
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &utcTime);
    json += ",\"timestamp\":\"";
    json += timestamp;
    json += "\"";
  } else {
    json += ",\"timestamp\":null";
    Serial.println("[TIME] NTP not synchronized; backend will timestamp receipt.");
  }

  appendFloatOrNull(json, "temperature_c", temperature, 1,
                    isfinite(temperature) && temperature >= -40.0f && temperature <= 85.0f);
  appendFloatOrNull(json, "humidity_pct", humidity, 1,
                    isfinite(humidity) && humidity >= 0.0f && humidity <= 100.0f);
  json += ",\"ldr_raw\":";
  if (ldrRaw >= 0 && ldrRaw <= 4095) {
    json += String(ldrRaw);
  } else {
    json += "null";
  }
  json += ",\"lux\":null";

  appendFloatOrNull(json, "voltage_v", voltage, 3,
                    ina219Detected && isfinite(voltage) &&
                    voltage >= -0.5f && voltage <= 30.0f);
  appendFloatOrNull(json, "current_ma", currentMA, 2,
                    ina219Detected && isfinite(currentMA) &&
                    currentMA >= -1000.0f && currentMA <= 3200.0f);
  appendFloatOrNull(json, "power_mw", powerMW, 2,
                    ina219Detected && isfinite(powerMW) &&
                    powerMW >= 0.0f && powerMW <= 32000.0f);
  json += "}";

  for (int attempt = 0; attempt < HTTP_MAX_RETRIES; ++attempt) {
    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.setConnectTimeout(HTTP_TIMEOUT_MS);
    if (!http.begin(SERVER_URL)) {
      Serial.println("[HTTP] Could not initialize the backend URL.");
      break;
    }
    http.addHeader("Content-Type", "application/json");

    Serial.print("[HTTP] Sending to ");
    Serial.print(SERVER_URL);
    if (attempt > 0) {
      Serial.print(" (retry ");
      Serial.print(attempt);
      Serial.print(")");
    }
    Serial.println();

    const int httpCode = http.POST(json);
    if (httpCode >= 200 && httpCode < 300) {
      Serial.print("[HTTP] Response: ");
      Serial.println(httpCode);
      Serial.print("[HTTP] Body: ");
      Serial.println(http.getString().substring(0, 160));
      http.end();
      ++sendSuccessCount;
      return true;
    }

    if (httpCode > 0) {
      Serial.print("[HTTP] Response: ");
      Serial.println(httpCode);
      Serial.print("[HTTP] Error body: ");
      Serial.println(http.getString().substring(0, 200));
      if (httpCode >= 400 && httpCode < 500) {
        http.end();
        break;
      }
    } else {
      Serial.print("[HTTP] Connection failed: ");
      Serial.println(http.errorToString(httpCode));
    }
    http.end();

    if (attempt + 1 < HTTP_MAX_RETRIES) {
      delay(1000);
    }
  }

  ++sendFailCount;
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println();
  Serial.println("Solary ESP32 final telemetry firmware");

  analogReadResolution(12);
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  dht.begin();
  Serial.println("[DHT11] Initialized on GPIO 4");
  Serial.println("[LDR] Ready on GPIO 34 (12-bit ADC)");

  if (ina219.begin()) {
    ina219.setCalibration_32V_2A();
    ina219Detected = true;
    Serial.println("[INA219] Detected at 0x40; 32V/2A calibration set");
    Serial.println("[INA219] Verify VIN+/VIN- source and load wiring before trusting readings");
  } else {
    Serial.println("[INA219] Not detected at 0x40; electrical fields will be null");
  }

  connectWiFi();
  Serial.print("[Server] ");
  Serial.println(SERVER_URL);
  Serial.println("[Setup] Open Serial Monitor at 115200 baud.");
}

void loop() {
  const unsigned long currentMillis = millis();
  if (currentMillis - previousMillis < READING_INTERVAL_MS) {
    return;
  }
  previousMillis = currentMillis;
  ++readingCount;

  const float temperature = dht.readTemperature();
  const float humidity = dht.readHumidity();
  const int ldrRaw = analogRead(LDR_PIN);

  float voltage = NAN;
  float currentMA = NAN;
  float powerMW = NAN;
  if (ina219Detected) {
    const float busVoltage = ina219.getBusVoltage_V();
    const float shuntVoltageMV = ina219.getShuntVoltage_mV();
    voltage = busVoltage + shuntVoltageMV / 1000.0f;
    currentMA = ina219.getCurrent_mA();
    powerMW = ina219.getPower_mW();
  }
  Serial.println("----- SENSOR DATA -----");
  Serial.print("Reading #: ");
  Serial.println(readingCount);
  Serial.print("Temperature (C): ");
  if (isfinite(temperature)) {
    Serial.println(temperature, 1);
  } else {
    Serial.println("unavailable");
  }
  Serial.print("Humidity (%): ");
  if (isfinite(humidity)) {
    Serial.println(humidity, 1);
  } else {
    Serial.println("unavailable");
  }
  Serial.print("LDR raw: ");
  Serial.println(ldrRaw);
  Serial.println("Lux: unavailable (no lux sensor configured)");
  if (ina219Detected) {
    Serial.print("INA219 input voltage (V): ");
    if (isfinite(voltage)) {
      Serial.println(voltage, 3);
    } else {
      Serial.println("invalid");
    }
    Serial.print("INA219 current (mA): ");
    if (isfinite(currentMA)) {
      Serial.println(currentMA, 2);
    } else {
      Serial.println("invalid");
    }
    Serial.print("INA219 power (mW): ");
    if (isfinite(powerMW)) {
      Serial.println(powerMW, 2);
    } else {
      Serial.println("invalid");
    }
  } else {
    Serial.println("INA219 voltage/current/power: unavailable");
  }

  sendToBackend(temperature, humidity, ldrRaw, voltage, currentMA, powerMW);
  Serial.print("[Stats] Success: ");
  Serial.print(sendSuccessCount);
  Serial.print(" | Failed: ");
  Serial.println(sendFailCount);
  Serial.println();
}
