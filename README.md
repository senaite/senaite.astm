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
