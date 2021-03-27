# -*- coding: utf-8 -*-

import asyncio

from senaite.astm.protocol import ASTMProtocol


def main():
    print("starting up ...")

    loop = asyncio.get_event_loop()
    coro = loop.create_server(ASTMProtocol, '0.0.0.0', 4010)
    server = loop.run_until_complete(coro)

    for socket in server.sockets:
        print("serving on {}".format(socket.getsockname()))
    loop.run_forever()


if __name__ == '__main__':
    main()
