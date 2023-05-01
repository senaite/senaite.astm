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

**Note ☝️:**
The push consuer endpoint `senaite.lis2a.import` does currently not support the
full messages (including control characters) sent by `senaite.astm`.
Therefore, it requires to register a custom endpoint for doing the results import.


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
