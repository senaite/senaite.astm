# senaite.astm documentation

ASTM and HL7-over-MLLP transport for laboratory instruments,
wired to a SENAITE LIMS via the SENAITE push consumer interface.

senaite.astm ships three CLIs:

- **`senaite-astm-server`** — long-running TCP listener that
  accepts ASTM (or HL7) sessions from instruments and forwards
  them to the LIMS.
- **`senaite-astm-send`** — one-shot CLI that replays a captured
  ASTM file into a LIMS without bringing up a listener. Also
  used for offline conversion, validation and PHI scrubbing.
- **`senaite-astm-inspect`** — read-only introspection of
  captured ASTM files (instrument resolution, summary,
  structural diff).

## Contents

- [Quickstart](quickstart.md) — install, boot, replay, validate.
- [CLI reference](cli.md) — every flag on every command.
- [Deployment](deployment.md) — systemd / supervisord units,
  admin endpoint, PHI scrubbing, recovery workflows.
- [Changelog](../CHANGES.rst) — release notes (at the repo root).
