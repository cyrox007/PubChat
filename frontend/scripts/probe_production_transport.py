#!/usr/bin/env python3
"""Unauthenticated external production transport probe, no credentials or PII.

Only HTTP HEAD/GET and a WebSocket upgrade are attempted. The WebSocket is
closed immediately after the HTTP handshake, without an auth frame.
A 101 confirms only the proxy upgrade path, NOT ticket validation or Safari.
"""
import base64
import http.client
import os
import secrets
import socket
import ssl
import time


TIMEOUT = 6
CONTEXT = ssl.create_default_context()
HOSTS = tuple(x.strip() for x in os.environ.get(
    "PUBCHAT_PROBE_HOSTS", "www.pubchat.ru,pubchat.ru"
).split(",") if x.strip())
ENDPOINTS = (
    ("/", "GET"),
    ("/api/csrf/get", "GET"),
    ("/api/identity/v2/me", "GET"),
    ("/api/realtime/v2/tickets", "GET"),
)


def http_check(host, path, method):
    start = time.monotonic()
    connection = http.client.HTTPSConnection(host, timeout=TIMEOUT, context=CONTEXT)
    try:
        connection.request(method, path, headers={"Cache-Control": "no-cache",
            "User-Agent": "PubChat-transport-diagnostics/1.0"})
        response = connection.getresponse()
        elapsed = (time.monotonic() - start) * 1000
        location = response.getheader("Location") or ""
        # URLs may contain sensitive query params; only print status, timing,
        # and whether an unauthenticated redirect was issued.
        print(f"HTTP host={host} method={method} path={path} status={response.status}"
              f" ttfb_ms={elapsed:.0f} redirected={bool(location)}", flush=True)
        response.close()
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        print(f"HTTP host={host} path={path} error={type(exc).__name__}"
              f" t_ms={elapsed:.0f}", flush=True)
    finally:
        connection.close()


def websocket_check(host, path):
    start = time.monotonic()
    raw = None
    connection = None
    try:
        raw = socket.create_connection((host, 443), timeout=TIMEOUT)
        raw.settimeout(TIMEOUT)
        connection = CONTEXT.wrap_socket(raw, server_hostname=host)
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Origin: https://{host}\r\n"
            "User-Agent: PubChat-transport-diagnostics/1.0\r\n\r\n"
        )
        connection.sendall(request.encode("ascii"))
        received = b""
        while b"\r\n\r\n" not in received and len(received) < 32768:
            data = connection.recv(4096)
            if not data:
                break
            received += data
        status = received.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        elapsed = (time.monotonic() - start) * 1000
        print(f"WSS host={host} path={path} handshake={status!r}"
              f" t_ms={elapsed:.0f} tls={connection.version()}", flush=True)
        if " 101 " not in status:
            print("WSS result=not_upgraded; proxy/redirect/route may be responsible",
                  flush=True)
        else:
            print("WSS result=upgrade_ok; ticket/auth/ready/heartbeat NOT tested",
                  flush=True)
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        print(f"WSS host={host} path={path} error={type(exc).__name__}"
              f" t_ms={elapsed:.0f}", flush=True)
    finally:
        if connection is not None:
            connection.close()
        elif raw is not None:
            raw.close()


def run():
    for host in HOSTS:
        start = time.monotonic()
        try:
            ips = sorted({row[4][0] for row in socket.getaddrinfo(
                host, 443, type=socket.SOCK_STREAM
            )})
            # IPs are public service addresses, not client IPs.
            print(f"DNS host={host} addresses={','.join(ips)}"
                  f" lookup_ms={(time.monotonic()-start)*1000:.0f}", flush=True)
        except Exception as exc:
            print(f"DNS host={host} error={type(exc).__name__}", flush=True)
            continue
        for path, method in ENDPOINTS:
            http_check(host, path, method)
        websocket_check(host, "/api/ws/v2/messenger")


if __name__ == "__main__":
    run()
