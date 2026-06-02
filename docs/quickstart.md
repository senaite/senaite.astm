# Quickstart

This walkthrough takes you from a fresh checkout to a running
`senaite-astm-server` that captures live ASTM traffic and
forwards it to a SENAITE LIMS, plus a one-shot replay of a
captured fixture via `senaite-astm-send`.

## Install

```
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Three console scripts are registered:

- `senaite-astm-server` (long-running listener)
- `senaite-astm-send` (one-shot replay / convert / validate)
- `senaite-astm-inspect` (read-only introspection)

## Boot the server against a SENAITE LIMS

```
senaite-astm-server \
    -p 4010 \
    -o ./captures \
    -u http://admin:secret@localhost:8080/senaite \
    --logfile ./var/log/senaite-astm-server.log
```

What this does:

- Listens for ASTM TCP sessions on port `4010`.
- Persists every captured session to `./captures/` as a
  timestamped file.
- Forwards every parsed envelope to the SENAITE consumer
  `senaite.core.lis2a.import`.
- Writes a rotating log file to `./var/log/`.

## Boot the server in capture-only mode

When commissioning a new instrument or wiring up a new
consumer adapter, run the server in hold-and-review mode:

```
senaite-astm-server -p 4010 -o ./hold --capture-only
```

`--capture-only` accepts connections, persists captures, and
skips the LIMS push step. `--url` is rejected in this mode —
the operator picks one mode or the other.

## Replay a captured file

The simplest replay form sends the captured bytes as a typed
JSON envelope through the SENAITE push endpoint:

```
senaite-astm-send \
    -i ./captures/2026-06-02_14_23_01.456.txt \
    -m json \
    -u http://admin:secret@localhost:8080/senaite
```

## Re-target the sample id without editing the file

When the captured file references a sample id that no longer
exists in the LIMS, swap it on the fly. The substitution
invalidates the affected frame's 2-byte checksum, so combine
with `--rebuild-checksums`:

```
senaite-astm-send \
    -i ./captures/original.txt \
    --substitute-sample-id OLD_ID=NEW_ID \
    --rebuild-checksums \
    -u http://admin:secret@localhost:8080/senaite
```

## Inspect a captured file

```
senaite-astm-inspect instrument captures/*.txt
senaite-astm-inspect summary    captures/*.txt
senaite-astm-inspect diff       a.txt b.txt
```

No LIMS contact, no writes — safe to run against production
captures.

## Validate captures in CI

`--validate-only` parses each input into the typed envelope
and reports per-file pass / fail. Exit code is `1` when any
file fails, `0` otherwise — drop-in for a CI step:

```
senaite-astm-send --validate-only -i tests/fixtures/*.txt
```

## Where to go next

- [CLI reference](cli.md) — full reference for every flag on
  every command.
- [Deployment](deployment.md) — production deployment notes
  (supervisord / systemd, the `--admin-port` HTTP stats
  endpoint, log rotation, PHI scrubbing).
