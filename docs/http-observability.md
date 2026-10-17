# HTTP observability

PubChat exposes privacy-minimal, per-process HTTP health metrics to administrators at `GET /admin/operations/http`.

The runtime sample is intentionally bounded and contains only:

- HTTP status class (`1xx` ... `5xx`, never the exact route or response body);
- request latency;
- current and peak in-flight request counts;
- total requests observed since the process started;
- p50/p95/p99/max latency and 5xx percentage for the bounded sample.

The collector does **not** retain request paths, query strings, headers, request/response bodies, Account/Persona identifiers, cookies, tokens, or IP addresses. Static files, public uploads, health endpoints and `/admin/operations/*` are excluded so operational reads do not observe themselves or distort API health.

## Process scope

Metrics are held in memory and are explicitly `scope=current_process`. A multi-worker deployment therefore has one independent bounded sample per application process. The endpoint is useful for local process health and incident diagnosis, but it is not cluster-wide telemetry and is not an SLO declaration.

## Configuration

Optional environment variables:

- `HTTP_METRICS_SAMPLE_SIZE` — rolling sample capacity, default `2000`, bounded to `100..10000`;
- `HTTP_METRICS_MIN_HEALTH_SAMPLE` — observations required before health is evaluated, default `20`;
- `HTTP_ALERT_5XX_PERCENT` — unhealthy 5xx percentage threshold, default `5`;
- `HTTP_ALERT_P95_MS` — unhealthy p95 latency threshold in milliseconds, default `2000`.

These values affect only the health projection. They do not shed traffic, retry requests, change rate limits, or alter responses.

## Admin UI

The existing **Admin → Operations** page loads HTTP health alongside PostgreSQL, realtime Redis and external-delivery metrics. Before the minimum sample is reached it displays a collecting state rather than declaring the process healthy.
