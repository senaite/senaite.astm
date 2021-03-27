# -*- coding: utf-8 -*-

import asyncio

clients = []


class SimpleChatClientProtocol(asyncio.Protocol):

    def connection_made(self, transport):
        self.transport = transport
        peername = transport.get_extra_info("peername")
        self.username = "{:s}:{:d}".format(*peername)
        print("connection_made: {}".format(self.username))

        for client in clients:
            client.send("{:s} connected".format(self.username))

        clients.append(self)

    def send(self, text):
        self.transport.write("{:s}\n".format(text).encode())

    def data_received(self, data):
        print("data_received: {}".format(data.decode()))

        incoming = data.decode()

        if len(incoming) == 0:
            return

        if incoming.find("/") == 0:
            parts = incoming.split()

            command = parts[0]

            print("found command block: {:s}".format(command))

            if command == "/username":
                if len(parts) != 2:
                    self.send("< command: invalid payload! Usage: /username <username>")
                    return

                print("{:s} changing username to {:s}".format(self.username, parts[1]))

                for client in clients:
                    if client != self:
                        client.send("{:s} changed username to {:s}".format(self.username, parts[1]))

                self.username = parts[1]
                self.send("< username changed")

                return

            elif command == "/whisper":
                if len(parts) < 3:
                    self.send("< command: invalid payload! Usage: /w <username> <message>")
                    return

                for client in clients:
                    if client.username == parts[1]:
                        client.send("{:s} whispered: {:s}".format(self.username, " ".join(parts[2:])))
                        return

                self.send("< command: whisper target username not found!")
                return

            elif command == "/exit":
                self.send("< command: disconnecting, bye!")
                print("client_disconnect: {:s}".format(self.username))
                self.transport.close()
                return

        for client in clients:
            if client is not self:
                client.send("{:s} wrote: {:s}".format(self.username, incoming))

    def connection_lost(self, ex):
        print("connection_lost: {}".format(self.username))
        clients.remove(self)

        for client in clients:
            client.send("{:s} disconnected".format(self.username))


async def send_from_stdin(loop):
    while True:
        message = yield loop.run_in_executor(None, input, ">")
        for client in clients:
            client.send(message)


if __name__ == '__main__':
    print("starting up..")

    loop = asyncio.get_event_loop()
    coro = loop.create_server(SimpleChatClientProtocol, '127.0.0.1', 8888)
    server = loop.run_until_complete(coro)

    # Start a task which reads from STDIN and pushes to clients.
    send_from_stdin(loop)

    for socket in server.sockets:
        print("serving on {}".format(socket.getsockname()))

    loop.run_forever()
