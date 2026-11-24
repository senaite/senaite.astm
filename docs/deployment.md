# Deployment

This page covers production operation of `senaite-astm-server`:
process supervision, log rotation, the admin HTTP endpoint,
PHI scrubbing, and the recovery workflow when the LIMS is down.

## Process supervision

### systemd

```
# /etc/systemd/system/senaite-astm-server.service
[Unit]
Description=SENAITE ASTM Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=senaite
Group=senaite
WorkingDirectory=/opt/senaite-astm
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/senaite-astm/.venv/bin/senaite-astm-server \
    -p 4010 \
    -o /var/lib/senaite-astm/captures \
    -u https://admin:%i@senaite.lab.invalid \
    --admin-port 4011 \
    --logfile /var/log/senaite-astm/server.log
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Notes:

- `Restart=on-failure` recovers from any non-zero exit. The
  code uses `sys.exit(1)` consistently (no negative codes that
  POSIX sign-flips to 255).
- `Type=simple` is correct — the server does not daemonise on
  its own.
- Keep the URL out of the unit file when possible (e.g. use
  `LoadCredential=` or read from a secrets file at startup).

### supervisord

```
[program:senaite-astm-server]
command=/opt/senaite-astm/.venv/bin/senaite-astm-server
        -p 4010
        -o /var/lib/senaite-astm/captures
        -u https://admin:secret@senaite.lab.invalid
        --admin-port 4011
        --logfile /var/log/senaite-astm/server.log
autostart=true
autorestart=true
startsecs=5
user=senaite
redirect_stderr=true
stdout_logfile=/var/log/senaite-astm/supervisor.log
```

## Admin endpoint

`--admin-port N` opens a tiny HTTP server (asyncio, hand-rolled
HTTP/1.1, no external deps) that answers `GET /stats` with a
JSON snapshot:

```
curl http://127.0.0.1:4011/stats
{
  "uptime_seconds": 12345.6,
  "active_sessions": 0,
  "frames_dispatched": 42,
  "last_dispatch_at": 1717336800.123
}
```

Counters:

- `active_sessions` — instrument connections currently open.
- `frames_dispatched` — per-session frame batches handed to the
  pipeline since process start.
- `last_dispatch_at` — Unix timestamp of the most recent
  dispatch, or `null` when no message has been received yet.

Safety:

- Bind defaults to `127.0.0.1` because the endpoint is
  **unauthenticated**.
- `--admin-listen` overrides the bind if the operator
  genuinely needs a non-loopback interface (e.g. a private
  monitoring VLAN).
- Request lines are capped at 2 KiB and read within 5 s to
  prevent slowloris-style resource exhaustion.

### Health checks

A scraper that wants "is the process alive" should poll
`/stats` and assert `uptime_seconds` increases between calls.
A scraper that wants "are messages still flowing" should alert
when `last_dispatch_at` is older than the expected
inter-message gap for the deployed instruments.

## Capture directory and replay

Every accepted session is persisted to the `--output` directory
as `<microsecond-timestamp>.txt`. The filename has microsecond
resolution so two instruments hitting the server within the
same second do not silently overwrite each other.

The capture file is the durable source of truth. If the LIMS
push fails after retries, the capture is still on disk and the
operator can replay it later:

```
senaite-astm-send \
    -i /var/lib/senaite-astm/captures/<file>.txt \
    -u https://admin:secret@senaite.lab.invalid
```

For a recurring "send everything that hasn't been pushed yet"
workflow, pair the capture handler with a sidecar `.ok` marker
file written by your own post-push hook, and a shell loop that
walks the directory for `*.txt` without a matching `*.ok`.

## Log rotation

`--logfile` enables a rotating file handler with sensible
defaults (10 MiB max, 5 backups). The default formatter is
`%(asctime)s %(levelname)-8s %(message)s`.

Repeated invocations of `configure_logging` are idempotent —
no duplicate handlers stack up if the CLI is re-invoked under
the same Python process (matters for test runners and
short-restart supervisors).

## PHI scrubbing

`--scrub-phi` is the privacy guarantee for replays into
non-production LIMSes. The allowlist of P-record fields kept
unredacted is:

- `type`, `seq` — record metadata
- `sex`, `race` — demographics (typically retained for clinical
  context)
- `height`, `weight`, `diet` — clinical observations
- `reserved` — ASTM placeholder, never populated

Every other P-record field is replaced with `<REDACTED>`.
`metadata.astm` and `metadata.lis2a` are also cleared so the
verbatim flat-text payloads do not leak.

Add vendor-specific non-identifying fields to the allowlist
with `--scrub-phi-keep-field KEY` (repeatable). Never widen
the allowlist to include obvious PHI fields like `name`,
`birthdate`, `address` or the various ID fields.

## LIMS timeout and retries

The LIMS HTTP push has a default timeout of
`(connect=10s, read=60s)`. A hung Zope worker is recycled
within a minute rather than pinning an asyncio thread-pool
worker indefinitely.

Retry tuning:

- `-r, --retries 3` (default) — three push attempts on
  transient failures.
- `-d, --delay 5` (default) — seconds between retries.

A 401 / 403 response is **not** retried — the operator likely
needs to fix credentials.

## Shutdown behaviour

On SIGINT / SIGTERM the server stops accepting new connections
and waits up to `--shutdown-grace-seconds N` (default 30) for
in-flight pipeline tasks to finish before cancelling them. The
log records both the count and the grace period so the operator
can tune to the deployment's largest expected message size.

## Capture-only mode

```
senaite-astm-server -p 4010 -o ./hold --capture-only
```

Useful when:

- Commissioning a new instrument — confirm the wire shape
  before involving the LIMS.
- Wiring up a new consumer adapter — collect a few real
  captures, then replay them through `senaite-astm-send`.

`--url` is rejected in this mode so a misconfigured systemd
unit fails loudly rather than silently dropping every captured
message.
