# -*- coding: utf-8 -*-

import re

from senaite.astm import logger
from senaite.astm import records
from senaite.astm.core.instrument import Instrument
from senaite.astm.core.instrument import register_instrument
from senaite.astm.encoded_streams import YumizenFloatleParseError
from senaite.astm.encoded_streams import parse_yumizen_floatle
from senaite.astm.fields import ComponentField
from senaite.astm.fields import ConstantField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import EncodedStreamField
from senaite.astm.fields import IntegerField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import PassthroughField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component
from senaite.astm.mapping import Record

# Per-kind names for the parallel lists inside the `Points`
# FLOATLE field (record field 14.7). The Yumizen spec section 3.5
# pins these positionally: HISTOGRAM carries (X, Y), MATRIX
# carries (X, Y, Qty, Pop). The instrument-side parser uses these
# tables to name the list-of-lists from
# :func:`parse_yumizen_floatle`. PopulationID legend (from the
# spec, table 3.5.3): 0=LYM, 1=MON, 2=NEU, 3=EOS, 4=LIC, 5=ALY,
# 6=LL, 7=RN, 8=RM, 11=BNL, 12=BNH, 13=LN, 14=BASO.
_POINTS_LIST_NAMES = {
    "HISTOGRAM": ("X", "Y"),
    "MATRIX": ("X", "Y", "Qty", "Pop"),
}

# Per-kind names for the parallel lists inside the `Thresholds`
# FLOATLE field (record field 14.6). HISTOGRAM thresholds (PltL,
# Pec, PltRbc on PLT — none on RBC / WBC) carry (X, ThrsID).
# MATRIX thresholds are documented but the spec notes they "must
# not be sent" (ListLength = 0), so the BoxID list is here for
# completeness only.
_THRESHOLDS_LIST_NAMES = {
    "HISTOGRAM": ("X", "ThrsID"),
    "MATRIX": ("X", "Y", "BoxID"),
}

VERSION = "1.0.0"
# Supports H500 and H550
HEADER_RX = re.compile(rb".*H5[0,5]0\^")


class HeaderRecord(records.HeaderRecord):
    """Message Header Record (H)
    """
    sender = ComponentField(
        Component.build(
            TextField(name="name"),
            TextField(name="serial"),
            TextField(name="version"),
        ))

    processing_id = SetField(
        field=TextField(),
        # P: Patient message, Q: Quality control message, D: Technician
        values=("P", "Q", "D"))

    version = TextField()


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)
    """
    unknown_1 = NotUsedField()
    unknown_2 = NotUsedField()


class OrderRecord(records.OrderRecord):
    """Order Record (O)
    """
    sample_id = TextField()
    instrument = TextField()
    test = ComponentField(
        Component.build(
            NotUsedField(name='_'),
            NotUsedField(name='__'),
            NotUsedField(name='___'),
            SetField(
                name='testname',
                field=TextField(),
                values=('CBC', 'DIF')),
        ))
    priority = ComponentField(
        Component.build(
            SetField(
                name='value',
                field=TextField(),
                values=('R', 'S')),
        ))
    requested_at = DateTimeField()
    received_at = DateTimeField()
    sampled_at = DateTimeField()
    reported_at = DateTimeField()


class CommentRecord(records.CommentRecord):
    """Comment Record (C)
    """


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.
    """
    test = ComponentField(
        Component.build(
            NotUsedField(name='_'),
            NotUsedField(name='__'),
            NotUsedField(name='___'),
            TextField(name='result_name'),
            TextField(name='assay_code'),
            TextField(name='dilution'),
        ))
    value = TextField()
    units = TextField()
    references = ComponentField(
        Component.build(
            TextField(name='result_range'),
            TextField(name='range_name'),
        ))
    abnormal_flag = SetField(
        field=TextField(),
        length=4,
        values=("HH", "H", "N", "L", "LL"))
    status = SetField(
        field=TextField(),
        length=1,
        values=("W", "X", "F"))
    operator = ComponentField(
        Component.build(
            TextField(name='login'),
            NotUsedField(name='_'),
            TextField(name='profile'),
        ))
    started_at = DateTimeField()
    completed_at = DateTimeField()


class RequestInformationRecord(records.RequestInformationRecord):
    """Request information Record (Q)
    """


# The Yumizen overloads the M record across several row types
# (HISTOGRAM, MATRIX, REAGENT, ...). Each row looks like:
#
#   1M|1|HISTOGRAM|RBC/PLT|RbcAlongRes|FLOATLE-stream/...|FLOATLE-stream/...
#
# The slot semantics depend on the `kind` tag in M-3:
#
#   M-3 kind     M-4         M-5            M-6              M-7
#   ---------    --------    -----------    --------------   --------------
#   HISTOGRAM    domain      stream         axis_x (stream)  axis_y (stream)
#   MATRIX       domain      stream         axis_x (stream)  axis_y (stream)
#   REAGENT      list        repeated cmps  (unused)         (unused)
#
# `kind` is always a string tag. `domain` and `stream` may be plain
# strings, backslash-separated lists, or repeated components — so
# they use PassthroughField, which preserves the original shape.
# axis_x / axis_y are encoded streams for HISTOGRAM / MATRIX and
# something else for REAGENT; EncodedStreamField decodes only when
# the prefix matches and passes other values through.
#
# Rebuild rather than subclass: the base ManufacturerInfoRecord is
# all NotUsedField, which would discard everything we care about.
_ManufacturerInfoRecord = Record.build(
    ConstantField(name="type", default="M"),
    IntegerField(name="seq", default=1, required=True),
    TextField(name="kind"),
    PassthroughField(name="domain"),
    PassthroughField(name="stream"),
    EncodedStreamField(name="axis_x"),
    EncodedStreamField(name="axis_y"),
)


class ManufacturerInfoRecord(_ManufacturerInfoRecord):
    """Yumizen M record with decoded Thresholds + Points.

    The Yumizen spec (section 3.5,
    `instruments/specs/horiba/Yumizen-H500-Comm-Spec.pdf`) frames
    the HISTOGRAM / MATRIX axis_x (Thresholds) and axis_y (Points)
    FLOATLE streams as a header block followed by parallel
    coordinate lists — not the flat numeric array a generic
    consumer would assume. Plotting the raw `axis_y` therefore
    reads display bounds and scale ticks as the first few "bin
    values" and disagrees visibly with the Yumizen's own printer.

    This `to_dict` override parses both streams into structured
    `thresholds` and `points` dicts so downstream renderers can
    plot the right thing without having to know the wire format:

    HISTOGRAM:
        `points = {"X": [...], "Y": [...]}` — explicit curve
        coordinates. Plot X vs Y directly; that is what the
        vendor printer does.
        `thresholds = {"X": [...], "ThrsID": [...]}` — vertical
        marker positions and their numeric IDs (PLT has
        Pec / PltL / PltRbc; RBC and WBC have none).

    MATRIX:
        `points = {"X": [...], "Y": [...], "Qty": [...],
                   "Pop": [...]}` — one entry per LMNE event
        with its resistance / absorbance coordinate, the number
        of events that landed on that coordinate, and a
        population ID (0=LYM, 1=MON, 2=NEU, 3=EOS, 4=LIC, 5=ALY,
        6=LL, 7=RN, 8=RM, 11=BNL, 12=BNH, 13=LN, 14=BASO).
        Color by Pop to reproduce the Yumizen's coloured scatter.
        `thresholds` is normally None — the spec says matrix
        thresholds "must not be sent" (ListLength = 0).

    Plus the shared display bounds (`x_min`, `x_max`, `y_min`,
    `y_max`) and tick lists (`x_ticks`, `y_ticks`) so a renderer
    can label axes in real device units.

    `axis_x` and `axis_y` are kept on the row unchanged so older
    consumers that did not know about the structure still work.
    Parse failures fall back to legacy behaviour and log a
    warning — the row still ships, just without the structured
    fields, and operations sees the format mismatch in the log.
    """

    def to_dict(self, obj=None):
        data = super().to_dict(obj)
        # Recursive calls inside `to_dict` pass `obj` explicitly;
        # only enrich when we're on the top-level record.
        if obj is not None and obj is not self:
            return data
        kind = data.get("kind")
        if kind not in _POINTS_LIST_NAMES:
            return data

        points_stream = data.get("axis_y")
        thresholds_stream = data.get("axis_x")
        # Points (field 14.7) carries X / Y scale ticks; Thresholds
        # (field 14.6) does not. See parse_yumizen_floatle.
        points = self._parse_section(
            points_stream, kind, "points", with_scale_ticks=True)
        thresholds = self._parse_section(
            thresholds_stream, kind, "thresholds",
            with_scale_ticks=False)

        # Display bounds + tick lists come from `points` when
        # available because that is the section the printer
        # plots; fall back to `thresholds` if for some reason
        # only that side parsed.
        bounds_source = points or thresholds
        if bounds_source is not None:
            for key in ("x_min", "x_max", "y_min", "y_max"):
                data[key] = bounds_source[key]
            data["x_ticks"] = bounds_source["x_ticks"]
            data["y_ticks"] = bounds_source["y_ticks"]

        data["points"] = self._format_section(
            points, _POINTS_LIST_NAMES, kind)
        data["thresholds"] = self._format_section(
            thresholds, _THRESHOLDS_LIST_NAMES, kind)
        return data

    @staticmethod
    def _parse_section(stream, kind, label, with_scale_ticks):
        """Run the Yumizen FLOATLE parser on `stream`, with one
        log line on a format mismatch so the row still ships."""
        try:
            return parse_yumizen_floatle(
                stream, with_scale_ticks=with_scale_ticks)
        except YumizenFloatleParseError as exc:
            logger.warning(
                "Yumizen %s %s: FLOATLE parse failed: %s",
                kind, label, exc)
            return None

    @staticmethod
    def _format_section(parsed, name_table, kind):
        """Convert the positional `lists` from the parser into a
        named dict using the per-kind label table, or None when
        the parser refused the stream or it carried no lists."""
        if parsed is None:
            return None
        if parsed["list_length"] == 0:
            # Spec-legal empty payload (matrix thresholds).
            return None
        names = name_table.get(kind, ())
        if len(parsed["lists"]) != len(names):
            logger.warning(
                "Yumizen %s: expected %d parallel lists, got %d",
                kind, len(names), len(parsed["lists"]))
            return None
        return dict(zip(names, parsed["lists"]))


class TerminatorRecord(records.TerminatorRecord):
    """Message Termination Record (L)
    """


@register_instrument
class HoribaYumizenH5xx(Instrument):
    name = "horiba_yumizen_h5xx"
    header_regex = HEADER_RX
    version = VERSION
    record_map = {
        "H": HeaderRecord,
        "P": PatientRecord,
        "O": OrderRecord,
        "R": ResultRecord,
        "C": CommentRecord,
        "Q": RequestInformationRecord,
        "M": ManufacturerInfoRecord,
        "L": TerminatorRecord,
    }


INSTRUMENT = HoribaYumizenH5xx()
