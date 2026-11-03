"""
Solary Solar Monitoring API
============================
FastAPI backend for AI-Based Solar Panel Fault Detection & Energy Forecasting.

Features:
- Real sensor data ingestion from ESP32 (HTTP POST)
- Demo fallback when no sensors are connected
- Historical data storage (JSON file)
- Electrical anomaly detection with configurable thresholds
- AI fault detection via MobileNetV2 image classifier
- Energy forecasting (baseline model)
- Sensor health and data freshness tracking
"""

from datetime import datetime, timezone, timedelta
from math import sin, pi, exp, isfinite
from random import uniform
from time import time
from pathlib import Path
from typing import Optional
import json
import os
import logging
import shutil
import traceback

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StrictInt, validator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "sensor_history.json"
UPLOADS_DIR = ROOT / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Fault detection model paths
FAULT_MODEL_DIR = PROJECT_ROOT / "Fault_Detection_Integration"
FAULT_WEIGHTS = FAULT_MODEL_DIR / "model" / "FINAL_88_32_MODEL.weights.h5"
FAULT_CLASSES = ["MultiHotSpot", "SingleHotSpot", "StringOpenCircuit"]
INA219_MEASUREMENTS_VALIDATED = os.getenv(
    "SOLARY_INA219_MEASUREMENTS_VALIDATED", "false"
).strip().lower() in {"1", "true", "yes"}

# Solar panel specs (10W panel)
PANEL_VMP = 19.25    # V  (voltage at max power)
PANEL_IMP = 0.52     # A  (current at max power)
PANEL_VOC = 22.5     # V  (open circuit voltage)
PANEL_ISC = 0.55     # A  (short circuit current)
PANEL_PMAX = 10.0    # W  (rated power)

# Stale data threshold
STALE_SECONDS = 30   # readings older than this are marked stale

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("solary")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Solary Solar Monitoring API",
    version="1.0.0",
    description="Backend for AI-Based Solar Panel Fault Detection & Energy Forecasting System"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

START = time()

# ---------------------------------------------------------------------------
# In-memory data stores
# ---------------------------------------------------------------------------

class SensorStore:
    """Thread-safe-ish in-memory store for the latest sensor readings."""
    def __init__(self):
        self.latest: Optional[dict] = None
        self.history: list[dict] = []
        self.max_history = 17280  # 24h at the firmware's 5-second interval
        self._updates_since_save = 0
        self.last_update: Optional[datetime] = None
        self.source: str = "NONE"  # "ESP32", "DEMO", "NONE"
        self._load_history()

    def _load_history(self):
        """Load persisted history from disk."""
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r") as f:
                    history = json.load(f)
                self.history = [item for item in history if isinstance(item, dict)][-self.max_history:]
                if self.history:
                    self.latest = dict(self.history[-1])
                    self.source = self.latest.get("source", "STORED")
                    stored_time = self.latest.get("received_at") or self.latest.get("timestamp")
                    if stored_time:
                        parsed_time = datetime.fromisoformat(stored_time.replace("Z", "+00:00"))
                        self.last_update = parsed_time if parsed_time.tzinfo else parsed_time.replace(tzinfo=timezone.utc)
                logger.info(f"Loaded {len(self.history)} historical readings from disk")
            except Exception as e:
                logger.warning(f"Could not load history: {e}")
                self.history = []

    def _save_history(self):
        """Persist history to disk (called periodically, not every write)."""
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self.history[-self.max_history:], f)
        except Exception as e:
            logger.warning(f"Could not save history: {e}")

    def update(self, reading: dict, source: str = "ESP32"):
        """Store a new sensor reading."""
        reading["source"] = source
        reading["received_at"] = datetime.now(timezone.utc).isoformat()
        self.latest = reading
        self.last_update = datetime.now(timezone.utc)
        self.source = source
        self.history.append(reading)
        # Trim history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        self._updates_since_save += 1
        if self._updates_since_save >= 10:
            self._save_history()
            self._updates_since_save = 0

    def is_stale(self) -> bool:
        if self.last_update is None:
            return True
        return (self.get_data_age_seconds() or 0) > STALE_SECONDS

    def get_age_seconds(self) -> Optional[float]:
        if self.last_update is None:
            return None
        return (datetime.now(timezone.utc) - self.last_update).total_seconds()

    def get_data_age_seconds(self) -> Optional[float]:
        received_age = self.get_age_seconds()
        if received_age is None:
            return None
        device_age = (self.latest or {}).get("device_timestamp_age_seconds")
        return received_age + max(0, device_age or 0)


store = SensorStore()

# Anomaly detection state
anomaly_state = {
    "status": "Sensor Unavailable",
    "alerts": [],
    "last_check": None,
    "consecutive_warnings": 0,
    "consecutive_criticals": 0,
}

# Fault detection model cache
_fault_model = None
_fault_model_loaded = False
_fault_model_error = None

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SensorPayload(BaseModel):
    """Payload sent by ESP32 via HTTP POST."""
    temperature_c: Optional[float] = Field(None, description="DHT11 temperature in Celsius")
    humidity_pct: Optional[float] = Field(None, description="DHT11 humidity percentage")
    ldr_raw: Optional[StrictInt] = Field(None, description="LDR raw ADC value (0-4095)")
    lux: Optional[float] = Field(None, description="BH1750 lux reading")
    voltage_v: Optional[float] = Field(None, description="INA219 bus voltage in V")
    current_ma: Optional[float] = Field(None, description="INA219 current in mA")
    power_mw: Optional[float] = Field(None, description="INA219 power in mW")
    device_id: Optional[str] = Field("esp32-01", description="Device identifier")
    timestamp: Optional[datetime] = Field(None, description="Device measurement time in ISO 8601 UTC")

    class Config:
        extra = "forbid"

    @validator("timestamp")
    def validate_timestamp(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Timestamp must include a timezone, preferably UTC")
        return value

    @validator("device_id")
    def validate_device_id(cls, value):
        if value is not None and not value.strip():
            raise ValueError("device_id cannot be empty")
        return value

    @validator("temperature_c")
    def validate_temperature(cls, v):
        if v is not None and (not isfinite(v) or v < -40 or v > 85):
            raise ValueError(f"Temperature {v}°C outside plausible range (-40 to 85)")
        return v

    @validator("humidity_pct")
    def validate_humidity(cls, v):
        if v is not None and (not isfinite(v) or v < 0 or v > 100):
            raise ValueError(f"Humidity {v}% outside valid range (0 to 100)")
        return v

    @validator("ldr_raw")
    def validate_ldr(cls, v):
        if v is not None and (v < 0 or v > 4095):
            raise ValueError(f"LDR value {v} outside 12-bit ADC range (0 to 4095)")
        return v

    @validator("voltage_v")
    def validate_voltage(cls, v):
        if v is not None and (not isfinite(v) or v < -0.5 or v > 30):
            raise ValueError(f"Voltage {v}V outside plausible range (-0.5 to 30)")
        return v

    @validator("current_ma")
    def validate_current(cls, v):
        if v is not None and (not isfinite(v) or v < -1000 or v > 3200):
            raise ValueError(f"Current {v}mA outside INA219 range")
        return v

    @validator("lux")
    def validate_lux(cls, v):
        if v is not None and (not isfinite(v) or v < 0 or v > 200000):
            raise ValueError(f"Lux value {v} outside plausible range")
        return v

    @validator("power_mw")
    def validate_power(cls, v):
        if v is not None and (not isfinite(v) or v < 0 or v > 32000):
            raise ValueError(f"Power {v}mW outside plausible INA219 range")
        return v


# ---------------------------------------------------------------------------
# Anomaly Detection Engine
# ---------------------------------------------------------------------------

# Configurable thresholds for the 10W panel
ANOMALY_THRESHOLDS = {
    # Voltage thresholds (panel Voc = 22.5V, Vmp = 19.25V)
    "voltage_warning_high": 23.0,      # V - above Voc, possible measurement error
    "voltage_critical_high": 25.0,     # V - definitely abnormal
    "voltage_warning_low_loaded": 14.0,  # V - under-voltage when generating
    "voltage_critical_low_loaded": 10.0, # V - severe under-voltage

    # Current thresholds (panel Isc = 0.55A = 550mA, Imp = 520mA)
    "current_warning_high": 600,       # mA - above Isc
    "current_critical_high": 700,      # mA - definitely abnormal

    # Power thresholds (Pmax = 10W = 10000mW)
    "power_warning_high": 11000,       # mW
    "power_critical_high": 13000,      # mW

    # Temperature thresholds
    "temp_warning_high": 45,           # °C
    "temp_critical_high": 55,          # °C
    "temp_warning_low": 0,             # °C
    "temp_critical_low": -10,          # °C

    # Humidity thresholds
    "humidity_warning_high": 85,       # %
    "humidity_critical_high": 95,      # %

    # Sustained condition counts (number of consecutive readings)
    "sustained_warning_count": 3,
    "sustained_critical_count": 2,
}


def run_anomaly_detection(reading: dict) -> dict:
    """
    Evaluate a sensor reading against thresholds.
    Returns anomaly status with reasons.
    """
    global anomaly_state
    alerts = []
    overall = "Normal"

    now = datetime.now(timezone.utc).isoformat()

    # --- Sensor availability checks ---
    has_voltage = reading.get("voltage_v") is not None
    has_current = reading.get("current_ma") is not None
    has_power = reading.get("power_mw") is not None
    has_temp = reading.get("temperature_c") is not None
    has_humidity = reading.get("humidity_pct") is not None
    has_ldr = reading.get("ldr_raw") is not None

    if not has_voltage and not has_current:
        alerts.append({
            "level": "info",
            "reason": "Electrical sensors (INA219) unavailable — anomaly detection limited to environmental readings",
            "timestamp": now,
        })

    # --- Temperature checks ---
    if has_temp:
        temp = reading["temperature_c"]
        t = ANOMALY_THRESHOLDS
        if temp >= t["temp_critical_high"]:
            alerts.append({"level": "critical", "parameter": "temperature",
                           "reason": f"Temperature critically high: {temp:.1f}°C (threshold: {t['temp_critical_high']}°C)",
                           "value": temp, "threshold": t["temp_critical_high"], "timestamp": now})
            overall = "Critical"
        elif temp >= t["temp_warning_high"]:
            alerts.append({"level": "warning", "parameter": "temperature",
                           "reason": f"Temperature elevated: {temp:.1f}°C (threshold: {t['temp_warning_high']}°C)",
                           "value": temp, "threshold": t["temp_warning_high"], "timestamp": now})
            if overall != "Critical":
                overall = "Warning"
        elif temp <= t["temp_critical_low"]:
            alerts.append({"level": "critical", "parameter": "temperature",
                           "reason": f"Temperature critically low: {temp:.1f}°C (threshold: {t['temp_critical_low']}°C)",
                           "value": temp, "threshold": t["temp_critical_low"], "timestamp": now})
            overall = "Critical"
        elif temp <= t["temp_warning_low"]:
            alerts.append({"level": "warning", "parameter": "temperature",
                           "reason": f"Temperature low: {temp:.1f}°C (threshold: {t['temp_warning_low']}°C)",
                           "value": temp, "threshold": t["temp_warning_low"], "timestamp": now})
            if overall != "Critical":
                overall = "Warning"

    # --- Humidity checks ---
    if has_humidity:
        hum = reading["humidity_pct"]
        t = ANOMALY_THRESHOLDS
        if hum >= t["humidity_critical_high"]:
            alerts.append({"level": "critical", "parameter": "humidity",
                           "reason": f"Humidity critically high: {hum:.1f}% (threshold: {t['humidity_critical_high']}%)",
                           "value": hum, "threshold": t["humidity_critical_high"], "timestamp": now})
            overall = "Critical"
        elif hum >= t["humidity_warning_high"]:
            alerts.append({"level": "warning", "parameter": "humidity",
                           "reason": f"Humidity elevated: {hum:.1f}% (threshold: {t['humidity_warning_high']}%)",
                           "value": hum, "threshold": t["humidity_warning_high"], "timestamp": now})
            if overall != "Critical":
                overall = "Warning"

    # --- Voltage checks (only when INA219 is providing data) ---
    if has_voltage:
        v = reading["voltage_v"]
        t = ANOMALY_THRESHOLDS
        is_generating = has_current and reading["current_ma"] > 10  # > 10mA means under load

        if v >= t["voltage_critical_high"]:
            alerts.append({"level": "critical", "parameter": "voltage",
                           "reason": f"Voltage critically high: {v:.2f}V (threshold: {t['voltage_critical_high']}V). Possible measurement error.",
                           "value": v, "threshold": t["voltage_critical_high"], "timestamp": now})
            overall = "Critical"
        elif v >= t["voltage_warning_high"]:
            alerts.append({"level": "warning", "parameter": "voltage",
                           "reason": f"Voltage above open-circuit rating: {v:.2f}V (Voc: {PANEL_VOC}V)",
                           "value": v, "threshold": t["voltage_warning_high"], "timestamp": now})
            if overall != "Critical":
                overall = "Warning"

        # Only check for low voltage when panel is generating (under load)
        if is_generating:
            if v <= t["voltage_critical_low_loaded"]:
                alerts.append({"level": "critical", "parameter": "voltage",
                               "reason": f"Voltage critically low under load: {v:.2f}V (threshold: {t['voltage_critical_low_loaded']}V)",
                               "value": v, "threshold": t["voltage_critical_low_loaded"], "timestamp": now})
                overall = "Critical"
            elif v <= t["voltage_warning_low_loaded"]:
                alerts.append({"level": "warning", "parameter": "voltage",
                               "reason": f"Voltage low under load: {v:.2f}V (threshold: {t['voltage_warning_low_loaded']}V). Possible shading or degradation.",
                               "value": v, "threshold": t["voltage_warning_low_loaded"], "timestamp": now})
                if overall != "Critical":
                    overall = "Warning"

    # --- Current checks ---
    if has_current:
        c = reading["current_ma"]
        t = ANOMALY_THRESHOLDS
        if c >= t["current_critical_high"]:
            alerts.append({"level": "critical", "parameter": "current",
                           "reason": f"Current critically high: {c:.1f}mA (threshold: {t['current_critical_high']}mA)",
                           "value": c, "threshold": t["current_critical_high"], "timestamp": now})
            overall = "Critical"
        elif c >= t["current_warning_high"]:
            alerts.append({"level": "warning", "parameter": "current",
                           "reason": f"Current above Isc: {c:.1f}mA (Isc: {PANEL_ISC * 1000}mA)",
                           "value": c, "threshold": t["current_warning_high"], "timestamp": now})
            if overall != "Critical":
                overall = "Warning"

    # --- Power checks ---
    if has_power:
        p = reading["power_mw"]
        t = ANOMALY_THRESHOLDS
        if p >= t["power_critical_high"]:
            alerts.append({"level": "critical", "parameter": "power",
                           "reason": f"Power critically high: {p:.0f}mW (threshold: {t['power_critical_high']}mW)",
                           "value": p, "threshold": t["power_critical_high"], "timestamp": now})
            overall = "Critical"
        elif p >= t["power_warning_high"]:
            alerts.append({"level": "warning", "parameter": "power",
                           "reason": f"Power above rated: {p:.0f}mW (Pmax: {PANEL_PMAX * 1000}mW)",
                           "value": p, "threshold": t["power_warning_high"], "timestamp": now})
            if overall != "Critical":
                overall = "Warning"

    # --- Sustained condition tracking ---
    if overall == "Warning":
        anomaly_state["consecutive_warnings"] += 1
        anomaly_state["consecutive_criticals"] = 0
    elif overall == "Critical":
        anomaly_state["consecutive_criticals"] += 1
        anomaly_state["consecutive_warnings"] = 0
    else:
        anomaly_state["consecutive_warnings"] = 0
        anomaly_state["consecutive_criticals"] = 0

    # Mark if electrical sensors are unavailable
    if not has_voltage and not has_current and not has_power:
        if not has_temp and not has_humidity:
            overall = "Sensor Unavailable"
        # If we have env sensors but no electrical, still report but note limitation
        elif overall == "Normal":
            overall = "Normal (electrical sensors unavailable)"

    anomaly_state.update({
        "status": overall,
        "alerts": alerts,
        "last_check": now,
        "has_electrical": has_voltage or has_current,
        "has_environmental": has_temp or has_humidity or has_ldr,
        "thresholds": ANOMALY_THRESHOLDS,
    })

    return anomaly_state


# ---------------------------------------------------------------------------
# Demo data generator (preserved from original)
# ---------------------------------------------------------------------------

def generate_demo_reading() -> dict:
    """Generate synthetic sensor reading for demo mode."""
    t = time() - START
    light_raw = int(max(0, min(4095, 2800 + 800 * sin(t / 18) + uniform(-50, 50))))
    light_pct = round(light_raw / 4095 * 100, 1)
    voltage = 18.2 + 0.25 * sin(t / 15) + uniform(-0.08, 0.08)
    current = 0.31 + 0.06 * sin(t / 13) + uniform(-0.015, 0.015)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "DEMO",
        "temperature_c": round(29.4 + 0.8 * sin(t / 40) + uniform(-0.15, 0.15), 1),
        "humidity_pct": round(54 + 4 * sin(t / 35) + uniform(-1, 1), 1),
        "light_pct": round(light_pct, 1),
        "ldr_raw": light_raw,
        "panel_voltage_v": round(voltage, 2),
        "panel_current_a": round(current, 3),
        "panel_power_w": round(voltage * current, 2),
        "energy_today_kwh": round(1.84 + 0.003 * (t % 300), 2),
        "system_status": "Monitoring (Demo)",
    }


def generate_demo_history() -> list:
    """Generate synthetic 24-hour power history for demo mode."""
    points = []
    for hour in range(24):
        daylight = max(0, sin((hour - 6) * pi / 12))
        points.append({
            "time": f"{hour:02d}:00",
            "power_w": round(4.8 * daylight, 2),
            "voltage_v": round(18.1 + 0.6 * daylight, 2) if daylight else 0,
        })
    return points


# ---------------------------------------------------------------------------
# Fault model loader (lazy)
# ---------------------------------------------------------------------------

def load_fault_model():
    """Lazily load the MobileNetV2 fault classifier. Returns (model, error_msg)."""
    global _fault_model, _fault_model_loaded, _fault_model_error

    if _fault_model_loaded:
        return _fault_model, _fault_model_error

    if not FAULT_WEIGHTS.exists():
        _fault_model_error = f"Model weights not found at {FAULT_WEIGHTS}"
        _fault_model_loaded = True
        logger.warning(_fault_model_error)
        return None, _fault_model_error

    try:
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers

        base_model = keras.applications.MobileNetV2(
            weights="imagenet", include_top=False, input_shape=(224, 224, 3)
        )
        inputs = keras.Input(shape=(224, 224, 3))
        x = keras.applications.mobilenet_v2.preprocess_input(inputs)
        x = base_model(x, training=False)
        x = layers.GlobalAveragePooling2D()(x)
        x = layers.Dropout(0.2)(x)
        outputs = layers.Dense(3, activation="softmax")(x)
        model = keras.Model(inputs, outputs)
        model.load_weights(str(FAULT_WEIGHTS))

        _fault_model = model
        _fault_model_loaded = True
        _fault_model_error = None
        logger.info("Fault detection model loaded successfully")
        return model, None

    except ImportError:
        _fault_model_error = "TensorFlow is not installed. Install with: pip install tensorflow"
        _fault_model_loaded = True
        logger.warning(_fault_model_error)
        return None, _fault_model_error
    except Exception as e:
        _fault_model_error = f"Failed to load model: {str(e)}"
        _fault_model_loaded = True
        logger.error(_fault_model_error)
        return None, _fault_model_error


# ---------------------------------------------------------------------------
# Energy Forecasting (documented baseline)
# ---------------------------------------------------------------------------

def generate_baseline_forecast(horizon: int, latest_reading: Optional[dict] = None) -> dict:
    """
    Generate a baseline energy forecast for the next `horizon` hours.

    Methodology (BASELINE — not a trained model):
    ─────────────────────────────────────────────
    This forecast uses a simple solar-irradiance bell-curve model based on:
      1. A sinusoidal daylight profile (sunrise ~06:00, sunset ~18:00)
      2. The panel's rated power (10W) as the theoretical maximum
      3. A derating factor (0.75) for real-world losses (dust, temperature,
         angle, inverter/converter efficiency)
      4. Current environmental readings (if available) to adjust the profile

    This is NOT a trained ML model. It is a physics-informed heuristic
    baseline suitable for demonstration purposes.

    Limitations:
    - Assumes a fixed sunrise/sunset schedule
    - Does not account for weather, clouds, or seasonal variation
    - Does not use historical generation data
    - DHT11 and LDR readings alone cannot predict future weather
    """
    now = datetime.now()
    current_hour = now.hour + now.minute / 60.0

    # Derating factor — real panels rarely achieve rated power
    derating = 0.75  # accounts for dust, temperature, angle, converter losses

    # If we have a current light reading, use it to scale the "now" point
    light_factor = 1.0
    if latest_reading:
        ldr = latest_reading.get("ldr_raw")
        if ldr is not None and ldr >= 0:
            # LDR raw 0-4095 → normalize to 0-1 (higher = more light for most LDR modules)
            light_factor = min(1.0, ldr / 3500)

    points = []
    for h in range(horizon + 1):
        forecast_hour = current_hour + h
        # Wrap around midnight
        hour_of_day = forecast_hour % 24

        # Sinusoidal daylight model: peak at solar noon (~12:00)
        # Sunrise at 6:00, sunset at 18:00 (12-hour day)
        if 6.0 <= hour_of_day <= 18.0:
            solar_fraction = sin((hour_of_day - 6.0) * pi / 12.0)
        else:
            solar_fraction = 0.0

        predicted_power_w = round(PANEL_PMAX * derating * solar_fraction, 2)
        # For the first point ("now"), apply light factor
        if h == 0 and light_factor < 0.8:
            predicted_power_w = round(predicted_power_w * light_factor, 2)

        energy_kwh = round(predicted_power_w / 1000, 4)  # 1-hour interval

        # Format time label
        display_hour = int(hour_of_day) % 24
        display_min = int((hour_of_day % 1) * 60)

        points.append({
            "hour_ahead": h,
            "time": "Now" if h == 0 else f"+{h}h",
            "clock_time": f"{display_hour:02d}:{display_min:02d}",
            "predicted_power_w": predicted_power_w,
            "energy_kwh": energy_kwh,
        })

    total_energy = round(sum(p["energy_kwh"] for p in points[1:]), 3)

    return {
        "source": "BASELINE",
        "model_type": "sinusoidal_baseline",
        "model_loaded": False,
        "horizon_hours": horizon,
        "interval_hours": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "message": (
            "Baseline forecast using sinusoidal daylight profile with 75% derating. "
            "This is NOT generated by a trained ML model. Values are estimates for demonstration."
        ),
        "methodology": (
            "P(t) = Pmax × 0.75 × sin(π × (hour - 6) / 12) for 06:00-18:00, else 0. "
            f"Pmax = {PANEL_PMAX}W (rated panel power)."
        ),
        "limitations": [
            "Fixed sunrise/sunset (06:00-18:00)",
            "No weather or cloud prediction",
            "No historical data used",
            "Assumes constant derating factor",
        ],
        "points": points,
        "total_energy_kwh": total_energy,
        "units": {"power": "W", "energy": "kWh"},
    }


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "name": "Solary Solar Monitoring API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "/health", "/api/readings", "/api/history", "/api/faults",
            "/api/forecast", "/api/anomalies", "/api/sensor-health",
            "/api/ingest"
        ]
    }


@app.get("/health")
def health():
    has_real_data = store.latest is not None and not store.is_stale()
    return {
        "status": "ok",
        "source": "ESP32" if has_real_data else ("ESP32 (STALE)" if store.latest else "DEMO"),
        "uptime_seconds": round(time() - START, 1),
        "has_real_data": has_real_data,
        "last_update": store.last_update.isoformat() if store.last_update else None,
        "data_age_seconds": round(store.get_data_age_seconds(), 1) if store.get_data_age_seconds() is not None else None,
        "history_count": len(store.history),
    }


# --- Sensor Data Ingestion (from ESP32) ---

@app.post("/api/ingest")
def ingest_sensor_data(payload: SensorPayload):
    """
    Receive sensor readings from ESP32 via HTTP POST.
    Validates the payload and stores the reading.
    """
    now_utc = datetime.now(timezone.utc)
    now = now_utc.isoformat()
    received_values = {
        "temperature_c": payload.temperature_c,
        "humidity_pct": payload.humidity_pct,
        "ldr_raw": payload.ldr_raw,
        "lux": payload.lux,
        "voltage_v": payload.voltage_v,
        "current_ma": payload.current_ma,
        "power_mw": payload.power_mw,
    }
    if payload.timestamp and (payload.timestamp - datetime.now(timezone.utc)).total_seconds() > 300:
        raise HTTPException(422, "timestamp cannot be more than five minutes in the future")
    device_timestamp_age = max(0.0, (now_utc - payload.timestamp.astimezone(timezone.utc)).total_seconds()) if payload.timestamp else None

    if all(received_values[name] is None for name in ("temperature_c", "humidity_pct", "ldr_raw", "lux")) and INA219_MEASUREMENTS_VALIDATED is False:
        raise HTTPException(422, "At least one validated sensor measurement is required")

    reading = {
        "timestamp": payload.timestamp.astimezone(timezone.utc).isoformat() if payload.timestamp else now,
        "timestamp_source": "DEVICE" if payload.timestamp else "SERVER_RECEIVED",
        "device_timestamp_age_seconds": round(device_timestamp_age, 1) if device_timestamp_age is not None else None,
        "device_timestamp_stale": device_timestamp_age > STALE_SECONDS if device_timestamp_age is not None else False,
        "device_id": payload.device_id,
        "field_status": {
            name: ("missing" if value is None else "unvalidated" if name in {"voltage_v", "current_ma", "power_mw"} and not INA219_MEASUREMENTS_VALIDATED else "valid")
            for name, value in received_values.items()
        },
        "missing_fields": [name for name, value in received_values.items() if value is None],
        "unvalidated_fields": [name for name in ("voltage_v", "current_ma", "power_mw") if received_values[name] is not None and not INA219_MEASUREMENTS_VALIDATED],
    }

    # Environmental sensors
    if payload.temperature_c is not None:
        reading["temperature_c"] = round(payload.temperature_c, 1)
    if payload.humidity_pct is not None:
        reading["humidity_pct"] = round(payload.humidity_pct, 1)
    if payload.ldr_raw is not None:
        reading["ldr_raw"] = payload.ldr_raw
        # Convert to percentage for dashboard compatibility
        reading["light_pct"] = round(payload.ldr_raw / 4095 * 100, 1)
    if payload.lux is not None:
        reading["lux"] = round(payload.lux, 1)

    # Electrical sensors (INA219)
    if INA219_MEASUREMENTS_VALIDATED and payload.voltage_v is not None:
        reading["panel_voltage_v"] = round(payload.voltage_v, 3)
        reading["voltage_v"] = round(payload.voltage_v, 3)
    if INA219_MEASUREMENTS_VALIDATED and payload.current_ma is not None:
        reading["panel_current_a"] = round(payload.current_ma / 1000, 4)
        reading["current_ma"] = round(payload.current_ma, 2)
    if INA219_MEASUREMENTS_VALIDATED and payload.power_mw is not None:
        reading["panel_power_w"] = round(payload.power_mw / 1000, 3)
        reading["power_mw"] = round(payload.power_mw, 2)

    # Calculate power from V×I if not provided directly
    if INA219_MEASUREMENTS_VALIDATED and "panel_power_w" not in reading and "panel_voltage_v" in reading and "panel_current_a" in reading:
        reading["panel_power_w"] = round(reading["panel_voltage_v"] * reading["panel_current_a"], 3)
        reading["power_mw"] = round(reading["panel_power_w"] * 1000, 2)

    reading["system_status"] = "Monitoring (Live)"

    # Store the reading
    store.update(reading, source="ESP32")

    # Run anomaly detection
    anomaly_result = run_anomaly_detection(reading)

    logger.info(f"Ingested reading from {payload.device_id}: "
                f"T={reading.get('temperature_c', 'N/A')}°C, "
                f"H={reading.get('humidity_pct', 'N/A')}%, "
                f"LDR={reading.get('ldr_raw', 'N/A')}, "
                f"V={reading.get('panel_voltage_v', 'N/A')}V")

    return {
        "status": "ok",
        "message": "Reading ingested successfully",
        "reading": reading,
        "anomaly_status": anomaly_result["status"],
    }


# --- Readings ---

@app.get("/api/readings")
def readings():
    """Return latest sensor readings. Uses real data if available, demo fallback otherwise."""
    if store.latest is not None and not store.is_stale():
        reading = dict(store.latest)
        reading["source"] = "ESP32"
        reading["data_age_seconds"] = round(store.get_data_age_seconds() or 0, 1)
        reading["is_stale"] = False
        # Ensure all expected fields exist for frontend compatibility
        reading.setdefault("panel_voltage_v", None)
        reading.setdefault("panel_current_a", None)
        reading.setdefault("panel_power_w", None)
        reading.setdefault("energy_today_kwh", None)
        reading.setdefault("light_pct", None)
        reading.setdefault("system_status", "Monitoring (Live)")
        return reading
    elif store.latest is not None:
        # Data exists but is stale
        reading = dict(store.latest)
        reading["source"] = "ESP32 (STALE)"
        reading["data_age_seconds"] = round(store.get_data_age_seconds() or 0, 1)
        reading["is_stale"] = True
        reading["system_status"] = "Stale data — sensor may be disconnected"
        reading.setdefault("panel_voltage_v", None)
        reading.setdefault("panel_current_a", None)
        reading.setdefault("panel_power_w", None)
        reading.setdefault("energy_today_kwh", None)
        reading.setdefault("light_pct", None)
        return reading
    else:
        # No real data — return demo
        return generate_demo_reading()


# --- History ---

@app.get("/api/history")
def history():
    """Return retained sensor readings only; an empty history is never synthesized."""
    if store.history:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = []
        for item in store.history:
            timestamp = item.get("timestamp") or item.get("received_at")
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed >= cutoff:
                    recent.append((item, parsed))
            except (ValueError, AttributeError):
                continue
        recent.sort(key=lambda entry: entry[1])
        if len(recent) > 288:
            all_recent = recent
            stride = (len(all_recent) + 287) // 288
            recent = all_recent[::stride]
            if recent and recent[-1][0] is not all_recent[-1][0]:
                recent[-1] = all_recent[-1]
        points = []
        for r, dt in recent:
            ts = r.get("timestamp", r.get("received_at", ""))
            points.append({
                "time": dt.strftime("%m-%d %H:%M"),
                "timestamp": ts,
                "power_w": r.get("panel_power_w") if INA219_MEASUREMENTS_VALIDATED else None,
                "voltage_v": r.get("panel_voltage_v") if INA219_MEASUREMENTS_VALIDATED else None,
                "current_a": r.get("panel_current_a") if INA219_MEASUREMENTS_VALIDATED else None,
                "temperature_c": r.get("temperature_c"),
                "humidity_pct": r.get("humidity_pct"),
                "light_pct": r.get("light_pct"),
            })

        return {
            "source": "ESP32" if store.source == "ESP32" else "STORED",
            "count": len(points),
            "points": points,
        }
    else:
        return {"source": "EMPTY", "count": 0, "points": []}


# --- Anomaly Detection ---

@app.get("/api/anomalies")
def get_anomalies():
    """Return current anomaly detection status."""
    if store.latest is not None:
        if store.is_stale():
            return {
                "status": "Sensor Unavailable (Stale)",
                "alerts": [{
                    "level": "info",
                    "reason": "The last ESP32 reading is stale; current anomaly status cannot be confirmed.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
                "last_check": store.latest.get("timestamp"),
                "has_electrical": any(store.latest.get(key) is not None for key in ("voltage_v", "current_ma", "power_mw")),
                "has_environmental": any(store.latest.get(key) is not None for key in ("temperature_c", "humidity_pct")),
                "thresholds": ANOMALY_THRESHOLDS,
            }
        # Re-run on latest reading
        result = run_anomaly_detection(store.latest)
    else:
        result = {
            "status": "Sensor Unavailable",
            "alerts": [{
                "level": "info",
                "reason": "No sensor data available. Connect ESP32 to enable anomaly detection.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
            "last_check": None,
            "has_electrical": False,
            "has_environmental": False,
            "thresholds": ANOMALY_THRESHOLDS,
        }
    return result


# --- Fault Detection (AI Model) ---

@app.get("/api/faults")
def faults():
    """Return fault detection status and model info."""
    model, error = load_fault_model()
    return {
        "source": "MODEL" if model else "UNAVAILABLE",
        "model_loaded": model is not None,
        "model_error": error,
        "model_architecture": "MobileNetV2 (224×224, 3-class softmax)" if model else None,
        "model_accuracy_note": "88.32% on project test set (not a real-world guarantee)" if model else None,
        "message": (
            "Model loaded and ready for inference. Upload an image with YOLO annotations to /api/faults/predict."
            if model else
            f"Model not available: {error or 'Unknown error'}"
        ),
        "classes": [
            {"index": i, "name": name, "status": "Ready" if model else "Not evaluated", "confidence_pct": 0}
            for i, name in enumerate(FAULT_CLASSES)
        ],
        "latest_event": "Model loaded — awaiting image upload." if model else "No model inference has been run.",
        "input_requirements": {
            "image": "Solar panel image (JPG/PNG)",
            "annotations": "YOLO-format .txt file with bounding boxes (class_id x_center y_center width height, normalized)",
            "note": "This model was trained on thermal/IR images for hotspot detection. Results on standard RGB images may not be meaningful."
        },
    }


@app.post("/api/faults/predict")
async def predict_fault(
    image: UploadFile = File(..., description="Solar panel image (JPG/PNG)"),
    annotations: UploadFile = File(..., description="YOLO-format .txt annotation file"),
):
    """
    Run fault classification on uploaded image using YOLO bounding boxes.
    Requires both an image and a YOLO annotation file.
    """
    # Validate image file
    if not image.filename:
        raise HTTPException(400, "No image file provided")
    img_ext = Path(image.filename).suffix.lower()
    if img_ext not in (".jpg", ".jpeg", ".png", ".bmp", ".tiff"):
        raise HTTPException(400, f"Unsupported image format: {img_ext}. Use JPG, PNG, BMP, or TIFF.")

    # Validate annotation file
    if not annotations.filename:
        raise HTTPException(400, "No annotation file provided. A YOLO-format .txt file is required.")
    ann_ext = Path(annotations.filename).suffix.lower()
    if ann_ext != ".txt":
        raise HTTPException(400, f"Annotation file must be .txt (YOLO format), got: {ann_ext}")

    # Load model
    model, error = load_fault_model()
    if model is None:
        raise HTTPException(503, f"Fault detection model unavailable: {error}")

    try:
        import numpy as np
        from PIL import Image as PILImage

        # Save uploaded files temporarily
        img_path = UPLOADS_DIR / f"temp_{image.filename}"
        ann_path = UPLOADS_DIR / f"temp_{annotations.filename}"

        img_content = await image.read()
        ann_content = await annotations.read()

        with open(img_path, "wb") as f:
            f.write(img_content)
        with open(ann_path, "wb") as f:
            f.write(ann_content)

        # Open and validate image
        try:
            pil_image = PILImage.open(img_path).convert("RGB")
        except Exception:
            raise HTTPException(400, "Could not open the uploaded image. Ensure it is a valid image file.")

        # Parse YOLO annotations
        with open(ann_path, "r") as f:
            lines = f.readlines()

        if not lines:
            raise HTTPException(400, "Annotation file is empty. Provide YOLO-format bounding boxes.")

        results = []
        for idx, line in enumerate(lines):
            parts = line.strip().split()
            if len(parts) < 5:
                continue

            try:
                x_c = float(parts[1])
                y_c = float(parts[2])
                w = float(parts[3])
                h = float(parts[4])
            except ValueError:
                continue

            # Validate normalized coordinates
            if not (0 <= x_c <= 1 and 0 <= y_c <= 1 and 0 < w <= 1 and 0 < h <= 1):
                continue

            # Create context crop (30% expansion, matching training)
            img_w, img_h = pil_image.size
            cx, cy = x_c * img_w, y_c * img_h
            bw, bh = w * img_w * 1.3, h * img_h * 1.3  # 30% expansion
            x1 = int(max(0, cx - bw / 2))
            y1 = int(max(0, cy - bh / 2))
            x2 = int(min(img_w, cx + bw / 2))
            y2 = int(min(img_h, cy + bh / 2))

            if x2 <= x1 or y2 <= y1:
                continue

            crop = pil_image.crop((x1, y1, x2, y2))
            crop = crop.resize((224, 224))
            arr = np.array(crop, dtype=np.float32)
            arr = np.expand_dims(arr, axis=0)

            probs = model.predict(arr, verbose=0)[0]
            pred_idx = int(np.argmax(probs))
            confidence = float(probs[pred_idx] * 100)

            results.append({
                "region_index": idx,
                "bounding_box": {"x_center": x_c, "y_center": y_c, "width": w, "height": h},
                "predicted_class": FAULT_CLASSES[pred_idx],
                "confidence_pct": round(confidence, 2),
                "probabilities": {
                    name: round(float(p) * 100, 2)
                    for name, p in zip(FAULT_CLASSES, probs)
                },
            })

        # Cleanup temp files
        try:
            img_path.unlink()
            ann_path.unlink()
        except Exception:
            pass

        if not results:
            raise HTTPException(400, "No valid bounding boxes found in the annotation file.")

        return {
            "source": "MODEL",
            "model_loaded": True,
            "image_filename": image.filename,
            "annotation_filename": annotations.filename,
            "regions_analyzed": len(results),
            "results": results,
            "note": "This model was trained on thermal/IR images. Confidence on standard RGB images may not reflect real fault detection accuracy.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fault prediction error: {traceback.format_exc()}")
        raise HTTPException(500, f"Inference error: {str(e)}")


# --- Forecast ---

@app.get("/api/forecast")
def forecast(horizon: int = Query(24, description="Forecast horizon in hours; supported values are 12 and 24")):
    if horizon not in (12, 24):
        raise HTTPException(status_code=400, detail="horizon must be 12 or 24 hours")
    latest = store.latest if store.latest and not store.is_stale() else None
    return generate_baseline_forecast(horizon, latest)


# --- Sensor Health ---

@app.get("/api/sensor-health")
def sensor_health():
    """Report sensor connectivity and data freshness status."""
    has_data = store.latest is not None
    is_stale = store.is_stale()
    latest = store.latest or {}
    def sensor_status(*fields):
        if not has_data:
            return "Not connected"
        if is_stale:
            return "Stale"
        present = [latest.get(field) is not None for field in fields]
        if all(present):
            return "Reporting"
        if any(present):
            return "Partial"
        return "Missing latest reading"

    sensors = {
        "esp32": {
            "status": "Connected" if has_data and not is_stale else ("Stale" if has_data else "Not connected"),
            "last_seen": store.last_update.isoformat() if store.last_update else None,
            "data_age_seconds": round(store.get_data_age_seconds() or 0, 1) if store.get_data_age_seconds() is not None else None,
        },
        "dht11": {
            "status": sensor_status("temperature_c", "humidity_pct"),
            "last_temperature_c": latest.get("temperature_c"),
            "last_humidity_pct": latest.get("humidity_pct"),
        },
        "ldr": {
            "status": sensor_status("ldr_raw"),
            "last_raw_value": latest.get("ldr_raw"),
            "last_light_pct": latest.get("light_pct"),
        },
        "ina219": {
            "status": "Reporting" if INA219_MEASUREMENTS_VALIDATED and latest.get("panel_voltage_v") is not None else "Awaiting validation",
            "last_voltage_v": latest.get("panel_voltage_v") if INA219_MEASUREMENTS_VALIDATED else None,
            "last_current_a": latest.get("panel_current_a") if INA219_MEASUREMENTS_VALIDATED else None,
            "last_power_w": latest.get("panel_power_w") if INA219_MEASUREMENTS_VALIDATED else None,
            "note": None if INA219_MEASUREMENTS_VALIDATED else "INA219 readings are withheld until actual measurements are validated.",
        },
    }

    # Fault model status
    model, error = load_fault_model()
    sensors["fault_model"] = {
        "status": "Loaded" if model else "Not loaded",
        "error": error,
        "classes": FAULT_CLASSES,
    }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall": "Online" if has_data and not is_stale else ("Stale" if has_data else "Offline"),
        "data_source": "ESP32 (STALE)" if has_data and is_stale else store.source,
        "sensors": sensors,
    }


# --- Anomaly Thresholds Configuration ---

@app.get("/api/anomalies/thresholds")
def get_thresholds():
    """Return the current anomaly detection thresholds."""
    return {
        "thresholds": ANOMALY_THRESHOLDS,
        "panel_specs": {
            "rated_power_w": PANEL_PMAX,
            "vmp_v": PANEL_VMP,
            "imp_a": PANEL_IMP,
            "voc_v": PANEL_VOC,
            "isc_a": PANEL_ISC,
        }
    }


# --- Test endpoint for anomaly detection ---

@app.post("/api/anomalies/test")
def test_anomalies(payload: SensorPayload):
    """
    Test anomaly detection with simulated readings.
    Useful for verifying thresholds without real hardware.
    Response is clearly marked as a test.
    """
    reading = {}
    if payload.temperature_c is not None:
        reading["temperature_c"] = payload.temperature_c
    if payload.humidity_pct is not None:
        reading["humidity_pct"] = payload.humidity_pct
    if payload.ldr_raw is not None:
        reading["ldr_raw"] = payload.ldr_raw
    if payload.voltage_v is not None:
        reading["voltage_v"] = payload.voltage_v
    if payload.current_ma is not None:
        reading["current_ma"] = payload.current_ma
    if payload.power_mw is not None:
        reading["power_mw"] = payload.power_mw

    result = run_anomaly_detection(reading)
    result["test_mode"] = True
    result["note"] = "This is a test — results do not affect the live anomaly state."
    return result
