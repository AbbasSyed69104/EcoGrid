import unittest
from src.ecogrid import EventBus, SmartMeterIntegration, EventType


class TestSmartMeterIntegration(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.service = SmartMeterIntegration(self.bus)

    def test_valid_reading(self):
        reading = self.service.ingest("SM-001", "SELLER-001", 10, 4)
        self.assertIsNotNone(reading)
        self.assertEqual(reading.excess_kwh, 6)

    def test_negative_reading_rejected(self):
        reading = self.service.ingest("SM-001", "SELLER-001", -1, 4)
        self.assertIsNone(reading)

    def test_energy_event_created(self):
        self.service.ingest("SM-001", "SELLER-001", 10, 4)
        self.assertEqual(len(self.bus.history), 1)
        self.assertEqual(
            self.bus.history[0].event_type,
            EventType.ENERGY_AVAILABLE
        )


if __name__ == "__main__":
    unittest.main()
