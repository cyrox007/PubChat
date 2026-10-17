import json
import unittest
from unittest.mock import patch

from app import create_app
from utils.http_metrics import HttpRuntimeMetrics, should_observe_http_path


class HttpRuntimeMetricsContractTests(unittest.TestCase):
    def test_bounded_snapshot_contains_only_aggregate_status_and_latency(self):
        metrics = HttpRuntimeMetrics(
            sample_size=3,
            min_health_sample=2,
            alert_5xx_percent=50.0,
            alert_p95_ms=1000.0,
        )
        with patch("utils.http_metrics.time.perf_counter", side_effect=[1.0, 1.010, 2.0, 2.020, 3.0, 3.030, 4.0, 4.040]):
            for status in (200, 404, 503, 201):
                started = metrics.request_started()
                metrics.request_finished(started, status)
            payload = metrics.snapshot()

        self.assertEqual(payload["scope"], "current_process")
        self.assertEqual(payload["total_requests_since_process_start"], 4)
        self.assertEqual(payload["sample"]["requests"], 3)
        self.assertEqual(payload["sample"]["status_classes"]["2xx"], 1)
        self.assertEqual(payload["sample"]["status_classes"]["4xx"], 1)
        self.assertEqual(payload["sample"]["status_classes"]["5xx"], 1)
        self.assertEqual(payload["in_flight_requests"], 0)
        self.assertFalse(payload["aggregation"]["cross_process"])

        privacy = payload["privacy"]
        self.assertFalse(privacy["contains_paths"])
        self.assertFalse(privacy["contains_query_strings"])
        self.assertFalse(privacy["contains_headers"])
        self.assertFalse(privacy["contains_request_bodies"])
        self.assertFalse(privacy["contains_account_ids"])
        self.assertFalse(privacy["contains_ip_addresses"])

        serialized = json.dumps(payload).lower()
        for forbidden in (
            "/identity/",
            "authorization: bearer",
            "secret@example.com",
            "account-123",
            "203.0.113.10",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_health_requires_minimum_sample_and_detects_5xx_pressure(self):
        metrics = HttpRuntimeMetrics(
            sample_size=10,
            min_health_sample=2,
            alert_5xx_percent=50.0,
            alert_p95_ms=1000.0,
        )
        with patch("utils.http_metrics.time.perf_counter", side_effect=[1.0, 1.010, 2.0, 2.020]):
            started = metrics.request_started()
            metrics.request_finished(started, 200)
            self.assertFalse(metrics.snapshot()["health_evaluable"])

            started = metrics.request_started()
            metrics.request_finished(started, 500)
            payload = metrics.snapshot()

        self.assertTrue(payload["health_evaluable"])
        self.assertTrue(payload["near_error_threshold"])
        self.assertFalse(payload["healthy"])

    def test_operations_static_and_health_paths_do_not_self_observe(self):
        self.assertFalse(should_observe_http_path("/admin/operations/http"))
        self.assertFalse(should_observe_http_path("/admin/operations/postgres-pool"))
        self.assertFalse(should_observe_http_path("/static/app.js"))
        self.assertFalse(should_observe_http_path("/uploads/images/example.png"))
        self.assertFalse(should_observe_http_path("/health"))
        self.assertTrue(should_observe_http_path("/identity/v2/session"))
        self.assertTrue(should_observe_http_path("/spaces/v1"))

    def test_admin_http_metrics_route_is_installed(self):
        paths = {route.path for route in create_app().routes}
        self.assertIn("/admin/operations/http", paths)


if __name__ == "__main__":
    unittest.main()
