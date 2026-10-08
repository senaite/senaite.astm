# SENAITE ASTM

Middleware to communicate between SENAITE and clinical and laboratory
instruments using ASTM specifications.

This program uses Python `asyncio` to receive ASTM messages on a given IP and
Port. `asyncio` is a library to write concurrent code using the async/await
syntax and needs therefore requires Python 3.6.x or higher.


## Installation

This package can be installed with `pip` from the sources:

    $ git clone git@github.com:senaite/senaite.astm.git
    $ cd senaite.astm
    $ pip install -e .


## Usage

The script `senaite-astm-server` allows to start the server:

    $ senaite-astm-server --help

    usage: senaite-astm-server [-h] [-l LISTEN] [-p PORT] [-o OUTPUT] [-u URL] [-c CONSUMER] [-m MESSAGE_FORMAT] [-r RETRIES] [-d DELAY] [-v] [--logfile LOGFILE]

    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         Verbose logging (default: False)
      --logfile LOGFILE     Path to store log files (default: senaite-astm-server.log)

    ASTM SERVER:
      -l LISTEN, --listen LISTEN
                            Listen IP address (default: 0.0.0.0)
      -p PORT, --port PORT  Port to connect (default: 4010)
      -o OUTPUT, --output OUTPUT
                            Output directory to write full messages (default: None)

    SENAITE LIMS:
      -u URL, --url URL     SENAITE URL address including username and password in the format: http(s)://<user>:<password>@<senaite_url> (default: None)
      -c CONSUMER, --consumer CONSUMER
                            SENAITE push consumer interface (default: senaite.lis2a.import)
      -m MESSAGE_FORMAT, --message-format MESSAGE_FORMAT
                            Message format to send to SENAITE. Supports "astm" or "lis2a". (default: lis2a)
      -r RETRIES, --retries RETRIES
                            Number of attempts of reconnection when SENAITE instance is not reachable. Only has effect when argument --url is set (default: 3)
      -d DELAY, --delay DELAY
                            Time delay in seconds between retries when SENAITE instance is not reachable. Only has effect when argument --url is set (default: 5)


## Simulator

The script `senaite-astm-simulator` allows to simulate an insturment connection
by sending frame-by-frame of an ASTM message with a possible delay to the
server:

    $ senaite-astm-simulator --help
    usage: senaite-astm-simulator [-h] [-a ADDRESS] [-p PORT] [-i INFILE [INFILE ...]] [-d DELAY] [-v]

    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         Verbose logging (default: False)

    ASTM SERVER:
      -a ADDRESS, --address ADDRESS
                            ASTM Server IP (default: 127.0.0.1)
      -p PORT, --port PORT  ASTM Server Port (default: 4010)
      -i INFILE [INFILE ...], --infile INFILE [INFILE ...]
                            ASTM file(s) to send (default: None)
      -d DELAY, --delay DELAY
                            Delay in seconds between two frames. (default: 0.1)

### Example

Start the server:

    $ senaite-astm-server -v
    Starting server on 0.0.0.0:4010
    ASTM server ready to handle connections ...


Send data to the server:

    $ senaite-astm-simulator -i src/senaite/astm/tests/data/cobas_c111.txt
    -> Write ENQ
    <- Got response: b'\x06'
    -> Sending data: b'\x021H|\\^&|||c111ELREMC^Roche^c111^4.2.2.1730^1^13147|||||host|RSUPL^REAL|P|1|20230414105700\rP|1||\rO|1||BMM 371 CONTROLE^^3||S||||||N|||||||||||20230414105700|||F\rR|1|^^^687|28.6|U/L||N||F||LABO||20230414105626\rC|1|I|111^? QC|I\rM|1|RR^BM^c111^1|23|23\\23\\21\\24\\26\\23\\579\\573\\571\\568\\566\\564\\568\\567\\565\\564\\8272\\8165\\8118\\8092\x03D6'
    <- Got response: b'\x06'
    -> Write EOT
    <- Got response: b''
    Done


## HL7-over-MLLP transport

Some instruments (e.g. PixCell HemoScreen) speak HL7 v2 over MLLP
instead of ASTM. The `senaite-hl7-server` script listens on the
IANA-registered HL7 port and turns each received message into the
same envelope shape the ASTM transport produces, so a single
downstream consumer can handle both:

    $ senaite-hl7-server --help

    usage: senaite-hl7-server [-h] [-l LISTEN] [-p PORT] [-o OUTPUT] [-u URL]
                              [-c CONSUMER] [-m MESSAGE_FORMAT] [-r RETRIES]
                              [-d DELAY] [-v] [--logfile LOGFILE]

    HL7 SERVER:
      -l LISTEN             Listen IP address (default: 0.0.0.0)
      -p PORT               Port to listen on (default: 2575)
      -o OUTPUT             Output directory to write captured HL7 messages

    SENAITE LIMS:
      -u URL                SENAITE URL with credentials. Without --url the
                            server runs in capture-only mode.
      -c CONSUMER           SENAITE push consumer interface
                            (default: senaite.core.hl7.import)
      -m MESSAGE_FORMAT     Format sent to SENAITE: "json" or "hl7"
                            (default: json)

Without `--url` the server runs capture-only: every message is
ACKed at the MLLP level and written to `--output` if set, but
nothing is pushed to a LIMS.

### Envelope mapping

HL7 segments are routed into the same buckets the ASTM parser
produces, so consumers can ignore the transport:

| HL7 segment | Envelope bucket |
| ----------- | --------------- |
| MSH         | H               |
| PID         | P               |
| OBR         | O               |
| OBX         | R               |
| NTE         | C               |

Within each bucket, fields are keyed by their HL7 field number as a
string. For example, MSH-9 (message type) is available as
`envelope.H[0]["9"]`, OBX-3 (observation identifier) as
`envelope.R[i]["3"]`. The original HL7 text is preserved verbatim
in `envelope.metadata.hl7` so capture and "push the original bytes"
flows keep working.

Worked fixtures live under `src/senaite/astm/tests/data/hl7/` and
are exercised by `tests/test_hl7_parser.py`.


## CELL-DYN Emerald transport

The Abbott CELL-DYN Emerald hematology analyzers (Emerald 18, Emerald 22
and Emerald 22 AL) speak neither ASTM nor HL7, but a proprietary,
text-oriented protocol over TCP/IP, as described in the *CELL-DYN Emerald
22 AL Laboratory Information System Interface Specification* (Abbott part
no. 9159915). The instrument is the TCP client: it connects to the host IP
address and port configured in its COMMUNICATION / NET. PARAM. menu
(protocol must be set to TCP/IP, the default is UDP/IP).

The `senaite-emerald-server` script is the listener the instruments connect
to. It drives the handshake of the protocol, checks the control sum
(CRC-16) of each frame, and turns each result into the same envelope shape
the ASTM transport produces:

    $ senaite-emerald-server --help

    usage: senaite-emerald-server [-h] [-l LISTEN] [-p PORT] [-o OUTPUT]
                                  [--shutdown-grace-seconds SECONDS]
                                  [-u URL] [-c CONSUMER] [-m MESSAGE_FORMAT]
                                  [-r RETRIES] [-d DELAY] [-v]
                                  [--logfile LOGFILE]

    CELL-DYN EMERALD SERVER:
      -l LISTEN             Listen IP address (default: 0.0.0.0)
      -p PORT               Port to listen on. The default is the default
                            host port of the instrument (default: 1200)
      -o OUTPUT             Output directory to write captured frames

    SENAITE LIMS:
      -u URL                SENAITE URL with credentials. Without --url the
                            server runs in capture-only mode.
      -c CONSUMER           SENAITE push consumer interface
                            (default: senaite.core.lis2a.import)
      -m MESSAGE_FORMAT     Format sent to SENAITE: "json" or "emerald"
                            (default: json)

The handshake is:

| Instrument                            | Host                         |
| ------------------------------------- | ---------------------------- |
| `CONNECT;<serial>;<version>`          | `ACK_CONNECT;<version>`      |
| `[header] RESULT_READY;<size>`        | `ACK_RESULT_READY`           |
| `[header] RESULT ... END_RESULT;<crc>` | `ACK_RESULT;OK`            |
| `[header] CALIBRATION ... END_CALI`   | `ACK_CALI;<lot>;OK`          |
| `DISCONNECT;<serial>`                 |                              |

A frame is only acknowledged once it has been written to `--output`. In
handshake mode, the instrument does not tag as sent the results that were
not acknowledged, and proposes to send them again at next login. Frames
with a wrong control sum are acknowledged with `ACK_RESULT;CRC_ERROR`. The
push to the LIMS runs afterwards, in the background, and only for the
results of samples: QC, calibration, repeatability and start-up frames are
captured, but not pushed.

### Envelope mapping

| Frame                      | Envelope bucket                              |
| -------------------------- | -------------------------------------------- |
| frame header               | H (`sender`: machine name, number, serial)   |
| patient information        | P                                            |
| sample information         | O (`sample_id` from `SID`)                   |
| hematological parameters   | R (one per parameter)                        |
| alarms and messages        | C                                            |

Parameters are decoded by their token (`WBC`, `NEU%`, ...), since the order
of the lines differs among the instruments of the family. Each result
record holds the value (`+++++` if over range, `-----` if invalid), the
flags in `abnormal_flag` and the limits in `references`. The units are not
sent by the instrument per parameter, but the unit system of the frame is
available in `envelope.metadata.unit_system`.

The sender name of the header (e.g. `EMD22AL`) is the one the push consumer
of SENAITE uses to resolve the importer, the same way as for the ASTM
transport. The original frame is preserved verbatim in the `emerald` extra
of the envelope metadata.

The files exported by the instrument to a USB drive use the same format, so
they can be parsed the same way. A worked fixture lives under
`src/senaite/astm/tests/data/emerald/` and is exercised by
`tests/test_emerald.py`.


## Custom push consumer

A push consumer is registered as an adapter in `configure.zcml`:

    <!-- Adapter to handle instrument pushes -->
    <adapter
      name="custom.lis2a.import"
      factory=".lis2a.PushConsumer"
      provides="senaite.jsonapi.interfaces.IPushConsumer"
      for="*" />

The implementation in the `lis2a` module should look like this:

    from senaite.jsonapi.interfaces import IPushConsumer
    from zope.interface import implementer


    @implementer(IPushConsumer)
    class PushConsumer(object):
        """Adapter that handles push requests for name "custom.lis2a.import"
        """
        def __init__(self, data):
            self.data = data

        def process(self):
            """Processes the LIS2-A compliant message.
            """
            # Extract LIS2-A messages from the data
            messages = self.data.get("messages")
            
            # parse and import the messages ...

            return True
