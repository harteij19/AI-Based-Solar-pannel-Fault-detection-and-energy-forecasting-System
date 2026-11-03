import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

import main


class SensorApiTests(unittest.TestCase):
    def setUp(self):
        self.original_store = main.store
        self.original_history_file = main.HISTORY_FILE
        self.original_anomaly_state = main.anomaly_state
        self.original_ina219_validation = main.INA219_MEASUREMENTS_VALIDATED
        self.temp_dir = tempfile.TemporaryDirectory()
        main.HISTORY_FILE = Path(self.temp_dir.name) / "sensor_history.json"
        main.store = main.SensorStore()
        main.INA219_MEASUREMENTS_VALIDATED = False
        main.anomaly_state = {
            "status": "Sensor Unavailable",
            "alerts": [],
            "last_check": None,
            "consecutive_warnings": 0,
            "consecutive_criticals": 0,
        }

    def tearDown(self):
        main.store = self.original_store
        main.HISTORY_FILE = self.original_history_file
        main.anomaly_state = self.original_anomaly_state
        main.INA219_MEASUREMENTS_VALIDATED = self.original_ina219_validation
        self.temp_dir.cleanup()

    def ingest(self, timestamp=None, **values):
        payload = main.SensorPayload(
            device_id="unit-test-esp32",
            timestamp=timestamp or datetime.now(timezone.utc),
            **values,
        )
        return main.ingest_sensor_data(payload)

    def test_ingest_is_returned_as_fresh_esp32_reading(self):
        timestamp = datetime.now(timezone.utc)
        self.ingest(timestamp=timestamp, temperature_c=28.0, humidity_pct=71.0, ldr_raw=526)

        reading = main.readings()

        self.assertEqual(reading["source"], "ESP32")
        self.assertEqual(reading["temperature_c"], 28.0)
        self.assertEqual(reading["humidity_pct"], 71.0)
        self.assertEqual(reading["ldr_raw"], 526)
        self.assertIsNone(reading["panel_voltage_v"])
        self.assertIsNone(reading["panel_current_a"])
        self.assertIsNone(reading["panel_power_w"])

    def test_history_is_chronological_and_contains_only_ingested_readings(self):
        now = datetime.now(timezone.utc)
        self.ingest(timestamp=now, temperature_c=28.0, ldr_raw=530)
        self.ingest(timestamp=now - timedelta(seconds=5), temperature_c=27.9, ldr_raw=525)

        response = main.history()
        timestamps = [datetime.fromisoformat(point["timestamp"]) for point in response["points"]]

        self.assertEqual(response["source"], "ESP32")
        self.assertEqual(response["count"], 2)
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertEqual([point["temperature_c"] for point in response["points"]], [27.9, 28.0])
        self.assertTrue(all(point["power_w"] is None for point in response["points"]))

    def test_missing_optional_sensors_remain_missing(self):
        result = self.ingest(temperature_c=28.0)

        self.assertEqual(result["reading"]["field_status"]["humidity_pct"], "missing")
        self.assertEqual(result["reading"]["field_status"]["voltage_v"], "missing")
        self.assertIsNone(main.readings()["panel_power_w"])

    def test_unvalidated_ina219_values_are_not_exposed_as_panel_readings(self):
        result = self.ingest(
            temperature_c=28.0,
            ldr_raw=526,
            voltage_v=18.5,
            current_ma=350.0,
            power_mw=6475.0,
        )

        self.assertEqual(
            result["reading"]["unvalidated_fields"],
            ["voltage_v", "current_ma", "power_mw"],
        )
        self.assertEqual(result["reading"]["field_status"]["voltage_v"], "unvalidated")
        self.assertIsNone(main.readings()["panel_voltage_v"])
        self.assertIsNone(main.readings()["panel_current_a"])
        self.assertIsNone(main.readings()["panel_power_w"])
        self.assertEqual(main.sensor_health()["sensors"]["ina219"]["status"], "Awaiting validation")

    def test_validated_ina219_values_are_stored_and_returned_in_dashboard_units(self):
        main.INA219_MEASUREMENTS_VALIDATED = True
        self.ingest(
            temperature_c=28.0,
            humidity_pct=71.0,
            ldr_raw=526,
            voltage_v=18.5,
            current_ma=350.0,
            power_mw=6475.0,
        )

        reading = main.readings()
        point = main.history()["points"][0]

        self.assertEqual(reading["source"], "ESP32")
        self.assertEqual(reading["panel_voltage_v"], 18.5)
        self.assertEqual(reading["panel_current_a"], 0.35)
        self.assertEqual(reading["panel_power_w"], 6.475)
        self.assertEqual(point["voltage_v"], 18.5)
        self.assertEqual(point["current_a"], 0.35)
        self.assertEqual(point["power_w"], 6.475)

    def test_stale_reading_is_not_reported_as_live(self):
        self.ingest(temperature_c=28.0, ldr_raw=526)
        main.store.last_update = datetime.now(timezone.utc) - timedelta(seconds=31)

        reading = main.readings()
        anomaly = main.get_anomalies()

        self.assertEqual(reading["source"], "ESP32 (STALE)")
        self.assertTrue(reading["is_stale"])
        self.assertIn("Stale", anomaly["status"])

    def test_invalid_sensor_ranges_are_rejected(self):
        with self.assertRaises(ValidationError):
            main.SensorPayload(temperature_c=100)
        with self.assertRaises(ValidationError):
            main.SensorPayload(humidity_pct=101)
        with self.assertRaises(ValidationError):
            main.SensorPayload(ldr_raw=4096)
        with self.assertRaises(ValidationError):
            main.SensorPayload(ldr_raw=12.5)

    def test_history_persists_and_reloads(self):
        timestamp = datetime.now(timezone.utc) - timedelta(seconds=20)
        for index in range(10):
            self.ingest(
                timestamp=timestamp + timedelta(seconds=index),
                temperature_c=28.0,
                ldr_raw=526,
            )

        restored = main.SensorStore()

        self.assertEqual(len(restored.history), 10)
        self.assertEqual(restored.latest["device_id"], "unit-test-esp32")

    def test_demo_fallback_is_explicit_and_history_stays_empty(self):
        reading = main.readings()
        response = main.history()

        self.assertEqual(reading["source"], "DEMO")
        self.assertEqual(response, {"source": "EMPTY", "count": 0, "points": []})


if __name__ == "__main__":
    unittest.main()