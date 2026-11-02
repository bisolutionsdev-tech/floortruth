# Shared-password demo access

FloorTruth is **ungated by default**, including on a hosted service. For a hosted
synthetic demo, the optional gate asks visitors for one shared password before
they can use the UI or API. The gate does not identify individual reviewers or
change the simulated approval workflow.

To prepare the gate, choose two independent, high-entropy random values. Generate
each locally using a secure random generator, for example
`python -c "import secrets; print(secrets.token_urlsafe(32))"`. Do not share
the generated values in chat, commit them to the repository, or include them
in logs or screenshots. Supply them through the hosting service's secret
environment configuration:

| Variable | Value |
| --- | --- |
| `FLOORTRUTH_DEMO_ACCESS` | `true` to enable the gate. The default `false` leaves the application ungated. |
| `FLOORTRUTH_DEMO_PASSWORD` | Shared demo password, at least 12 characters; use a randomly generated value. |
| `FLOORTRUTH_SESSION_SECRET` | A different random value of at least 32 characters for signing sessions. |

When enabled, missing, short, or identical password and signing secret values
cause requests to fail closed with HTTP 503. An unrecognized gate setting also
fails closed. Changing either value invalidates existing sessions. Authorized
visitors receive an eight-hour signed `Secure`, `HttpOnly`, `SameSite=Strict`
cookie. **HTTPS is required**: a browser will not send that cookie over normal
HTTP, including the default local `http://127.0.0.1:8000` URL.

With the gate enabled, unauthenticated `GET /api/health` returns only
`{"ok": true}`, and `HEAD /api/health` returns an empty 200 response for hosting
health checks. A logged-in visitor sees the full health response, including
provider status. Invalid gate configuration still returns 503. No hosting
settings are changed by this code.

Login attempts are limited in memory per observed client address (10 attempts
per five minutes). This is per process, resets on restart, and can group
visitors behind a proxy; it is not distributed brute-force protection. The gate
uses a shared password and shared demo data, has no individual accounts or
roles, and does not make its simulated reviewer identity authentic. Keep the
demo synthetic and avoid relying on it as a production identity system.
