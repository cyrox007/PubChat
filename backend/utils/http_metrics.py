from __future__ import annotations

import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass


SAMPLE_SIZE = max(100, min(10000, int(os.getenv("HTTP_METRICS_SAMPLE_SIZE", "2000"))))
MIN_HEALTH_SAMPLE = max(
    1,
    min(SAMPLE_SIZE, int(os.getenv("HTTP_METRICS_MIN_HEALTH_SAMPLE", "20"))),
)
ALERT_5XX_PERCENT = max(0.1, min(100.0, float(os.getenv("HTTP_ALERT_5XX_PERCENT", "5"))))
ALERT_P95_MS = max(50.0, min(60000.0, float(os.getenv("HTTP_ALERT_P95_MS", "2000"))))


@dataclass(frozen=True, slots=True)
class HttpSample:
    status_class: str
    latency_ms: float


class HttpRuntimeMetrics:
    """Bounded, privacy-minimal HTTP metrics for one application process."""

    def __init__(
        self,
        sample_size: int | None = None,
        *,
        min_health_sample: int | None = None,
        alert_5xx_percent: float | None = None,
        alert_p95_ms: float | None = None,
    ) -> None:
        self._sample_size = max(1, int(sample_size or SAMPLE_SIZE))
        self._min_health_sample = max(1, min(self._sample_size, int(min_health_sample or MIN_HEALTH_SAMPLE)))
        self._alert_5xx_percent = max(0.1, min(100.0, float(alert_5xx_percent or ALERT_5XX_PERCENT)))
        self._alert_p95_ms = max(1.0, float(alert_p95_ms or ALERT_P95_MS))
        self._samples: deque[HttpSample] = deque(maxlen=self._sample_size)
        self._started_monotonic = time.monotonic()
        self._total_requests = 0
        self._in_flight = 0
        self._peak_in_flight = 0
        self._lock = threading.Lock()

    @staticmethod
    def _status_class(status_code: int) -> str:
        code = max(0, int(status_code))
        if 100 <= code <= 599:
            return f"{code // 100}xx"
        return "other"

    def request_started(self) -> float:
        with self._lock:
            self._in_flight += 1
            self._peak_in_flight = max(self._peak_in_flight, self._in_flight)
        return time.perf_counter()

    def request_finished(self, started: float, status_code: int) -> None:
        latency_ms = max(0.0, (time.perf_counter() - started) * 1000.0)
        sample = HttpSample(
            status_class=self._status_class(status_code),
            latency_ms=latency_ms,
        )
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            self._total_requests += 1
            self._samples.append(sample)

    def request_aborted(self, started: float) -> None:
        # Unhandled exceptions are represented as 5xx for operational health.
        self.request_finished(started, 500)

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        rank = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
        return round(ordered[rank], 2)

    def snapshot(self) -> dict:
        with self._lock:
            samples = list(self._samples)
            total_requests = self._total_requests
            in_flight = self._in_flight
            peak_in_flight = self._peak_in_flight

        counts = {name: 0 for name in ("1xx", "2xx", "3xx", "4xx", "5xx", "other")}
        latencies = []
        for sample in samples:
            counts[sample.status_class] = counts.get(sample.status_class, 0) + 1
            latencies.append(sample.latency_ms)

        sample_count = len(samples)
        error_5xx_percent = (
            round((counts["5xx"] / sample_count) * 100.0, 3)
            if sample_count
            else 0.0
        )
        p95_ms = self._percentile(latencies, 0.95)
        enough_for_health = sample_count >= self._min_health_sample
        near_error_threshold = bool(
            enough_for_health and error_5xx_percent >= self._alert_5xx_percent
        )
        near_latency_threshold = bool(
            enough_for_health and p95_ms >= self._alert_p95_ms
        )

        return {
            "scope": "current_process",
            "uptime_seconds": round(max(0.0, time.monotonic() - self._started_monotonic), 1),
            "total_requests_since_process_start": total_requests,
            "in_flight_requests": in_flight,
            "peak_in_flight_requests": peak_in_flight,
            "sample": {
                "capacity": self._sample_size,
                "requests": sample_count,
                "status_classes": counts,
                "error_5xx_percent": error_5xx_percent,
                "latency_ms": {
                    "p50": self._percentile(latencies, 0.50),
                    "p95": p95_ms,
                    "p99": self._percentile(latencies, 0.99),
                    "max": round(max(latencies), 2) if latencies else 0.0,
                },
            },
            "thresholds": {
                "min_health_sample": self._min_health_sample,
                "alert_5xx_percent": self._alert_5xx_percent,
                "alert_p95_ms": self._alert_p95_ms,
            },
            "health_evaluable": enough_for_health,
            "near_error_threshold": near_error_threshold,
            "near_latency_threshold": near_latency_threshold,
            "healthy": not (near_error_threshold or near_latency_threshold),
            "aggregation": {
                "cross_process": False,
                "note": "Each application process owns an independent in-memory HTTP sample.",
            },
            "privacy": {
                "contains_paths": False,
                "contains_query_strings": False,
                "contains_headers": False,
                "contains_request_bodies": False,
                "contains_account_ids": False,
                "contains_ip_addresses": False,
            },
        }


http_runtime_metrics = HttpRuntimeMetrics()


def should_observe_http_path(path: str) -> bool:
    # Static/user-content traffic, health reads and the operations surface itself
    # would distort application API health and make metrics reads self-observing.
    return not (
        path.startswith("/static/")
        or path.startswith("/uploads/")
        or path.startswith("/admin/operations/")
        or path in {"/health", "/healthz", "/ready", "/readyz"}
    )
