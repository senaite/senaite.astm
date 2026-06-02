# CLI reference

senaite.astm ships three console scripts. Every flag is
documented inline with `--help`; this page collects the same
information in a single browsable reference.

## senaite-astm-server

Long-running TCP listener that accepts ASTM sessions, persists
captures, and forwards parsed envelopes to a SENAITE LIMS.

### Listener

- `-l, --listen IP` — bind address. Defaults to `0.0.0.0`.
- `-p, --port PORT` — TCP port. Defaults to `4010`.
- `-o, --output DIR` — directory where every captured session
  is written as a timestamped file. Required for
  `--capture-only`; otherwise optional but strongly recommended
  in production so that replay / audit is possible after a LIMS
  outage.
- `--shutdown-grace-seconds N` — seconds to wait for in-flight
  pipeline tasks to finish before cancelling them on SIGTERM.
  Defaults to `30`.

### Operating modes

- `--capture-only` — accept connections and persist captures,
  but skip the LIMS push step. Useful for a hold-and-review
  workflow when commissioning a new instrument. Requires
  `--output`; mutually exclusive with `--url`.

### Admin endpoint

- `--admin-port PORT` — open a read-only HTTP admin endpoint.
  `GET /stats` returns JSON: `uptime_seconds`,
  `active_sessions`, `frames_dispatched`, `last_dispatch_at`.
  Off by default.
- `--admin-listen IP` — bind address for `--admin-port`.
  Defaults to `127.0.0.1` because the endpoint is
  unauthenticated.

### LIMS push

- `-u, --url URL` — SENAITE URL with credentials:
  `http(s)://user:password@host[:port]/path`.
- `-c, --consumer NAME` — SENAITE push consumer interface.
  Defaults to `senaite.core.lis2a.import`.
- `-m, --message-format {json,astm,lis2a}` — format of the
  message body POSTed to SENAITE. `json` is the parsed typed
  envelope (what current SENAITE consumers expect). `astm` and
  `lis2a` are raw / flat-text variants for legacy consumers.
- `-r, --retries N` — push attempts on transient failures.
  Defaults to `3`.
- `-d, --delay SEC` — seconds between push retries. Defaults
  to `5`.

### Diagnostics

- `-v, --verbose` — DEBUG-level logging.
- `--logfile PATH` — rotating log file. Defaults to
  `senaite-astm-server.log` in the working directory.

## senaite-astm-send

One-shot CLI that replays a captured ASTM file. Composes
substitution, validation, scrubbing, filtering and dry-run
into a single processing pipeline.

### Inputs

- `-i, --infile FILE [FILE ...]` — one or more captured ASTM
  files. Read in order, each producing one message.

### Pre-parse transformations

- `--substitute-sample-id OLD=NEW` — replace every occurrence
  of OLD with NEW in the raw capture before parsing.
  Repeatable. Primary use: retarget a captured file to a
  different sample id without editing it. The substitution
  invalidates the affected frame's 2-byte checksum, so combine
  with `--rebuild-checksums`.
- `--rebuild-checksums` — recompute the trailing checksum of
  every ASTM frame before parsing. Use after any byte-level
  edit (substitution, scrub). Off by default so genuine wire
  corruption is not silently masked.

### Envelope transformations

- `--scrub-phi` — redact every P-record field that is not in
  the non-PHI allowlist (`type`, `seq`, `sex`, `race`,
  `height`, `weight`, `diet`, `reserved`) with `<REDACTED>`.
  Also clears `metadata.astm` and `metadata.lis2a` so the
  verbatim flat-text payloads do not leak through. Requires
  `--message-format json` (raw and flat outputs cannot be
  rewritten safely).
- `--scrub-phi-keep-field KEY` — extend the non-PHI allowlist
  with a vendor-specific non-identifying field. Repeatable.
- `--filter-records TYPES` — keep only the listed record-type
  buckets in the parsed envelope (`H,P,O,R,C,M,L,Q`). Mutually
  exclusive with `--drop-records`. Requires
  `--message-format json`.
- `--drop-records TYPES` — drop the listed record-type buckets
  from the parsed envelope.

### Output modes

- `-o, --output PATH` — write the converted message(s) instead
  of pushing to a LIMS.
  - `-` — write to stdout. Single input only.
  - existing directory — write one file per input as
    `<input-stem>.<ext>`.
  - regular file path — single input only.

  When set, `--url` is not required.
- `--dry-run` — log the URL, consumer, message count and
  per-message format + byte size that would be pushed to the
  LIMS, then exit without opening a connection. The URL
  password is masked.
- `--validate-only` — parse each input file into the typed
  envelope and report success or failure per file. No LIMS
  push, no output. Exit code is `1` on any failure, `0`
  otherwise.

### Format / LIMS

- `-m, --message-format {json,astm,lis2a}` — see
  `senaite-astm-server` above. Defaults to `json`.
- `-u, --url URL` — SENAITE URL with credentials. Required
  unless `--output`, `--dry-run` or `--validate-only` is set.
- `-c, --consumer NAME` — push consumer interface.
- `-r, --retries N` / `-d, --delay SEC` — push retry tuning.

## senaite-astm-inspect

Read-only introspection of captured ASTM files. No LIMS push,
no writes — safe to run against production captures.

### instrument

```
senaite-astm-inspect instrument FILE [FILE ...]
```

Prints the canonical instrument name resolved from each file's
first frame, one line per file. `unknown` when no registered
instrument matches the header.

### summary

```
senaite-astm-inspect summary FILE [FILE ...]
```

One-line summary per file:

```
capture.txt: instrument=H500 sample_id=CLVB262207 H=1 P=1 O=1 R=20 C=2 M=4 L=1 Q=0
```

### diff

```
senaite-astm-inspect diff FILE_A FILE_B
```

Unified diff of the two parsed envelopes' JSON serialisation.
Exit code is `1` when files differ, `0` when identical.
