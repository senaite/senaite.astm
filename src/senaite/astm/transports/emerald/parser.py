# -*- coding: utf-8 -*-
"""CELL-DYN Emerald frame → :class:`Envelope` parser.

Turns a raw frame (bytes, as captured by
:mod:`senaite.astm.transports.emerald.protocol` or as exported by the
instrument to a USB drive) into the same :class:`Envelope` shape the ASTM
transport produces, so downstream consumers depend on one schema
regardless of which transport the device speaks.

A result frame looks like::

    EMD22AL;1;310618-000034;OPERATOR     frame header
    RESULT                               frame ID
    DATE;19/02/2024                      sample information
    TIME;11:46:47
    MODE;NORMAL
    SID;2600009
    ...
    WBC;4.1;;;3.7;3.7;10.1;10.1          id;value;flag A;flag B;low panic;
    NEU%;55.0;;;39.3;39.3;73.7;73.7        low;high;high panic
    ...
    WBC CURVE;...                        histograms, alarms, matrices
    ALARMS;...
    END_RESULT;38650                     control sum

Mapping to the envelope buckets:

=========================== ============================================
Frame                       Envelope bucket
=========================== ============================================
frame header                :attr:`Envelope.H` (``sender``: machine name,
                            instrument number, serial)
patient information         :attr:`Envelope.P`
sample information          :attr:`Envelope.O` (``sample_id`` from SID)
hematological parameters    :attr:`Envelope.R` (one per parameter)
alarms and messages         :attr:`Envelope.C`
=========================== ============================================

The order of the parameter lines differs among the instruments of the
family (Emerald 18, 22 and 22 AL), so parameters are always decoded by
their token, never by their position. The machine name of the frame
header is taken as is, so the sender name to resolve the importer in the
LIMS is the one the instrument sends (e.g. ``EMD22AL``).

Patient, sample and analysis information (P, O) is only set for the
results of samples, not for QC, calibration or repeatability frames.

The raw frame text lands in the ``emerald`` extra of the
:class:`Metadata`, so the envelopes of the other transports keep their
shape.
"""

import re

from senaite.astm.core.envelope import Envelope
from senaite.astm.core.envelope import Metadata

DEFAULT_ENCODING = "utf-8"

# Modes of the result frames that are not about a sample
NON_SAMPLE_MODES = ("QC", "CALIBRATION", "REPEATABILITY")

# Tokens of the lines that start the section after the parameters
END_OF_PARAMETERS = ("ALARMS", "INTERPRETIVE_WBC", "INTERPRETIVE_RBC",
                     "INTERPRETIVE_PLT", "COMMENT")

# Tokens of the lines of alarms and messages, mapped to comment records
COMMENT_TOKENS = ("ALARMS", "INTERPRETIVE_WBC", "INTERPRETIVE_RBC",
                  "INTERPRETIVE_PLT", "COMMENT")

# Token of a hematological parameter, e.g. WBC, NEU%, MCHC
PARAMETER_TOKEN = re.compile(r"^[A-Z][A-Z0-9#%_-]*$")

# Value of a hematological parameter: a number, +++++ (over range) or
# ----- (invalid result)
PARAMETER_VALUE = re.compile(r"^([+-]?\d*\.?\d+|\+{5}|-{5})$")

# Sex codes of the instrument
SEX = {"0": "U", "1": "M", "2": "F"}


def _decode(raw):
    """Return ``raw`` as a string regardless of input type."""
    if isinstance(raw, bytes):
        return raw.decode(DEFAULT_ENCODING, errors="replace")
    return raw


def split_lines(text):
    """Returns the non-empty lines of the text, with CR, LF or CRLF as
    line terminators
    """
    text = text.replace("\r\n", "\r").replace("\n", "\r")
    return [line for line in text.split("\r") if line.strip()]


def split_fields(line):
    """Returns the fields of the line, stripped
    """
    return [field.strip() for field in line.split(";")]


def to_ansi(date, time=""):
    """Converts a date in ``DD/MM/YYYY`` format and a time in ``HH:MM:SS``
    format to ``YYYYMMDD[HHMMSS]``, as used by ASTM envelopes. Returns an
    empty string if the date is not valid
    """
    parts = (date or "").split("/")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return ""
    day, month, year = parts
    ansi = "{}{}{}".format(year.zfill(4), month.zfill(2), day.zfill(2))
    time = "".join((time or "").split(":"))
    if len(time) == 6 and time.isdigit():
        ansi += time
    return ansi


def is_parameter(fields):
    """Returns whether the fields are the ones of a hematological parameter
    line: ``id;value;flag A;flag B;...``
    """
    if len(fields) < 4:
        return False
    if not PARAMETER_TOKEN.match(fields[0]):
        return False
    return bool(PARAMETER_VALUE.match(fields[1]))


def parse_header(line):
    """Returns the header record from the frame header line:
    ``[MACHINE_NAME];W;X;Y``, where W is the instrument number, X the
    serial number and Y the user login
    """
    fields = split_fields(line) + [""] * 4
    return {
        "type": "H",
        "sender": {
            "name": fields[0],
            "number": fields[1],
            "serial": fields[2],
            "version": "",
        },
        "operator": fields[3],
    }


def parse_parameter(fields, seq, info):
    """Returns the result record for the hematological parameter
    """
    flags = [{"flag": flag} for flag in fields[2:4] if flag]
    # Patient results carry the panic and normal limits, while QC results
    # carry the target limits only
    limits = fields[4:8]
    if len(limits) == 4:
        keys = ("low_panic", "low", "high", "high_panic")
    else:
        keys = ("low", "high")
    references = dict(zip(keys, limits))
    return {
        "type": "R",
        "seq": str(seq),
        "test": {"name": fields[0]},
        "value": fields[1],
        "units": "",
        "abnormal_flag": flags,
        "references": references,
        "status": "F",
        "operator": info.get("OPERATOR", ""),
        "completed_at": to_ansi(info.get("DATE"), info.get("TIME")),
    }


def parse(raw):
    """Parse a raw CELL-DYN Emerald frame into an :class:`Envelope`.

    :param raw: frame bytes (or string), from the frame header until the
        control sum line (optional).
    :returns: A fully-populated :class:`Envelope`. The raw frame is stored
        verbatim in the ``emerald`` extra of the metadata.
    :raises ValueError: when the input has no frame header nor frame ID.
    """
    text = _decode(raw)
    lines = split_lines(text)
    if len(lines) < 2:
        raise ValueError("Not a CELL-DYN Emerald frame: {!r}".format(
            text[:80]))

    header = parse_header(lines[0])
    frame_id = split_fields(lines[1])[0].upper()

    info = {}
    results = []
    comments = []
    in_parameters = True
    for line in lines[2:]:
        fields = split_fields(line)
        token = fields[0].upper()
        if token in END_OF_PARAMETERS or token.endswith(" CURVE"):
            in_parameters = False
        if token in COMMENT_TOKENS:
            text_value = ";".join(filter(None, fields[1:]))
            if text_value:
                comments.append({
                    "type": "C",
                    "seq": str(len(comments) + 1),
                    "source": token,
                    "data": text_value,
                })
            continue
        if not in_parameters or token.startswith("END_"):
            continue
        if is_parameter(fields):
            results.append(parse_parameter(
                fields, len(results) + 1, info))
        elif len(fields) > 1:
            info.setdefault(token, fields[1])

    timestamp = to_ansi(info.get("DATE"), info.get("TIME"))
    header["timestamp"] = timestamp
    if info.get("OPERATOR"):
        header["operator"] = info["OPERATOR"]

    mode = info.get("MODE", "").upper()
    patients = []
    orders = []
    if frame_id == "RESULT" and mode not in NON_SAMPLE_MODES:
        patients.append({
            "type": "P",
            "seq": "1",
            "id": info.get("PID", ""),
            "name": info.get("ID", ""),
            "birthdate": to_ansi(info.get("BIRTH")),
            "sex": SEX.get(info.get("SEX", ""), "U"),
            "physician": info.get("PRESC", ""),
            "location": info.get("LOCAT", ""),
        })
        orders.append({
            "type": "O",
            "seq": "1",
            "sample_id": info.get("SID", ""),
            "test": {"name": info.get("TEST", "")},
            "instrument": {
                "rack": info.get("RACK", ""),
                "position": info.get("POS", ""),
            },
            "biomaterial": info.get("TYPE", ""),
            "report_type": "F",
        })

    metadata = Metadata(
        emerald=text,
        frame_id=frame_id,
        mode=mode,
        unit_system=info.get("UNIT", ""),
    )
    return Envelope(metadata=metadata, H=[header], P=patients, O=orders,
                    R=results, C=comments)
