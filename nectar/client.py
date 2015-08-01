from nectar.config import key_path
from nectar.crypto import CryptoBox, SecretBox, load_key
from nectar.proto import Ack, PomaresProtocol, PubKeyReply
from nectar.proto import decompress_buff, compress_buff, encode, decode
import asyncio
import logging

ROUTES = {}


class PomaresClient:
    def __init__(self, address, key_path, server_pub_key, command):
        self.keyobj = load_key(key_path)
        logging.debug("client init_box pk: {}".format(self.keyobj.pk))
        logging.debug("client init_box sk: {}".format(self.keyobj.sk))
        self.command = command
        PomaresProtocol.route = self.route
        self.host, self.port = address

        self.do_handshake_init()

    def do_handshake_init(self):
        logging.debug('(route) do_handshake_init()')
        # send my pubkey to server
        handshk_payload = compress_buff(encode(PubKeyReply(self.keyobj.pk)))
        self.client_prot = PomaresProtocol(handshk_payload)

    def do_handshake(self, handler, msg):
        logging.debug('(route) do_handshake()')
        # expect server to send secret key to init_box
        handler.init_box = CryptoBox(self.keyobj)
        handler.init_box.box_with(server_pub_key)

        # receive server secretkey
        msg = handler.init_box.decrypt(msg)
        msg = decode(msg)
        handler.box = SecretBox(key=msg.key)
        handler.handshaked = True
        logging.debug('HANDSHAKED2')

        # XXX send first command msg
        logging.debug('(route) sending command msg')
        self.send_command(handler)

    def send_command(self, handler):
        new_msg = encode(Ack(self.command))  # XXX Ack for now...
        new_msg = handler.box.encrypt(new_msg)
        handler.send_data(compress_buff(new_msg))

    def route(self, handler, msg):
        logging.debug('(route) I am routing this msg: {}'.format(msg))
        try:
            msg = decompress_buff(msg)
            logging.debug('(route) decompressed msg: {}'.format(msg))
            if not handler.handshaked:
                logging.debug('(route) decoded msg: {}'.format(msg))
                # at this point we can only expect PubKeyReply
                self.do_handshake(handler, msg)
            else:
                # receive messages:
                msg = handler.box.decrypt(msg)
                request = decode(msg)
                logging.debug('(route) got request: {}'.format(request))

                # TODO treat server replies here

        except Exception as err:
            logging.debug('!!!! ignoring request [bad key] {}'.format(err))
            raise

    def run(self):
        loop = asyncio.get_event_loop()
        coro = loop.create_connection(lambda: self.client_prot,
                                      self.host, self.port)
        loop.run_until_complete(coro)
        loop.run_forever()
        loop.close()


class PomaresAdminClient:
    def __init__(self, admin_sock, commands):
        """opens a client in admin_sock and iterates over commands
        using talk()"""
        self.admin_sock = admin_sock
        self.commands = commands
        self.reader = None
        self.writer = None

    @asyncio.coroutine
    def talk(self):
        self.reader, self.writer = yield from \
                asyncio.open_unix_connection(self.admin_sock)
        for cmd in iter(self.commands):
            logging.debug('(PomaresAdminClient.talk) sending cmd: {}'.format(cmd))
            yield from self.send(cmd)
            yield from self.read()

    @asyncio.coroutine
    def send(self, payload):
        self.writer.write(bytes('{}\n'.format(payload).encode()))
        yield from self.writer.drain()

    @asyncio.coroutine
    def read(self):
        answer = yield from self.reader.readline()
        logging.debug('(PomaresAdminClient.talk) got data: {}'.format(answer))
        return answer

    def run(self):
        "runs event loop"
        loop = asyncio.get_event_loop()
        tasks = asyncio.async(self.talk())
        loop.run_until_complete(tasks)
        loop.close()


if __name__ == '__main__':
    import sys
    server_pub_key = load_key(key_path+'/local.key').pk
    my_key = key_path+'/my.key'
    if len(sys.argv) > 1:
        command = sys.argv[1]
    else:
        command = "default first command message"
    c = PomaresClient(('127.0.0.1', 8080), my_key, server_pub_key, command)
    c.run()
