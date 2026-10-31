import unittest
from backend.app.api.health import health

class HealthEndpointTests(unittest.TestCase):
    def test_health_payload(self):
        self.assertEqual(health(), {"status": "ok", "service": "backend"})

if __name__ == "__main__":
    unittest.main()
