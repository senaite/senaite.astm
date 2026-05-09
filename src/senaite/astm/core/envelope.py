# -*- coding: utf-8 -*-
"""Typed envelope schema produced by :class:`senaite.astm.wrapper.Wrapper`.

The envelope is the JSON contract between `senaite.astm` and any
downstream LIMS consumer. Until the 2.x line, the shape was
implicit: a `defaultdict(list)` whose keys depended on which record
types happened to be present and whose per-record fields varied
silently between instruments. Consumers had to defensively probe
the structure (`obj.get("H", [{}])[0].get("sender", {})...`) and
every new instrument risked subtly changing the shape downstream
relied on.

This module pins that contract:

- :data:`ENVELOPE_VERSION` is bumped whenever the structure changes
  in a way consumers must adapt to.
- :class:`Metadata` declares the required keys (``envelope_version``,
  ``astm``, ``lis2a``) and accepts vendor extras (e.g. Roche c111's
  parsed sender component) via ``extra="allow"``.
- :class:`Envelope` declares the per-record-type buckets (H, P, O,
  R, C, M, L, Q) as lists of dicts. The per-record shape is left
  loose on purpose — that lives in the per-instrument record
  classes — but the *envelope* shape is now stable.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict

ENVELOPE_VERSION = "1.0"


class Metadata(BaseModel):
    """Metadata block of the envelope.

    Required keys are declared explicitly. Per-instrument extras
    (sender component, instrument type, etc.) are accepted via
    ``extra="allow"`` and surface unchanged in :meth:`model_dump`.
    """

    model_config = ConfigDict(extra="allow")

    envelope_version: str = ENVELOPE_VERSION
    astm: str
    lis2a: str


class Envelope(BaseModel):
    """Top-level envelope produced by ``Wrapper.to_dict()``.

    Per-record buckets default to empty lists so the shape is
    stable regardless of which record types a given instrument
    emits.
    """

    model_config = ConfigDict(extra="allow")

    metadata: Metadata
    H: List[Dict[str, Any]] = []
    P: List[Dict[str, Any]] = []
    O: List[Dict[str, Any]] = []  # noqa: E741
    R: List[Dict[str, Any]] = []
    C: List[Dict[str, Any]] = []
    M: List[Dict[str, Any]] = []
    L: List[Dict[str, Any]] = []
    Q: List[Dict[str, Any]] = []
