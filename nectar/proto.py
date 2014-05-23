from msgpack import packb, unpackb
from collections import namedtuple
from zlib import compress, decompress
from struct import pack, unpack
import asyncio

ChunkRequest = namedtuple('ChunkRequest', ('tree', 'checksum', 'chunk_from', 'chunk_to'))
ChunkReply = namedtuple('ChunkReply', ('data', 'seek', 'data_crc32'))
SetValuesRequest = namedtuple('SetValuesRequest', ('db', 'values',))
ValuesRequest = namedtuple('Values', ('values',))
ShareTreeRequest = namedtuple('ShareTreeRequest', ('tree', 'hashes'))
ShareTreeFileRequest = namedtuple('ShareTreeFileRequest', ('tree', 'hash_meta'))
IOReadChunkRequest = namedtuple('IOReadChunkRequest', ('filename', 'offset', 'nbytes'))
SetPermsRequest = namedtuple('SetPermsRequest', ('tree', 'keysum', 'perms'))
Ack = namedtuple('Ack', ('value',))
PubKeyReply = namedtuple('PubKeyReply', ('key',))

msg_dict = {'ChunkRequest':(0, ChunkRequest),
            'ChunkReply':(1, ChunkReply),
            'SetValuesRequest':(2, SetValuesRequest),
            'SetPermsRequest':(3, SetPermsRequest),
            'ValuesRequest':(4, ValuesRequest),
            'ShareTreeRequest':(5, ShareTreeRequest),
            'ShareTreeFileRequest':(6, ShareTreeFileRequest),
            'IOReadChunkRequest':(7, IOReadChunkRequest),
            'SetPermsRequest':(8, SetPermsRequest),
            'Ack':(9, Ack),
            'PubKeyReply':(10, PubKeyReply)
            }
msg_dict_rev = dict((v[0],v[1]) for k,v in msg_dict.items())


class PomaresHandler():
    def __init__(self, transport):
        self.transport = transport
        self.handshaked = False

    def send_data(self, payload):
        payload_size = len(payload)
        payload = pack('<I{:d}s'.format(payload_size), payload_size, payload)
        print('sending payload: {}'.format(payload))
        self.transport.write(payload)


class PomaresProtocol(asyncio.Protocol):
    def __init__(self, payload=None):
        self.payload = payload
        self.header_size = 4


    def connection_made(self, transport):
        self.handler = PomaresHandler(transport)
        self.data_buffer = bytearray()
        self.data_buffer_size = 0
        self.msg_size = 0

        print('connection made')
        if self.payload:
            self.handler.send_data(self.payload)
            self.payload = None


    def data_received(self, data):
        print('received data: {}'.format(data))

        # connection is made
        self.data_buffer.extend(data)
        self.data_buffer_size += len(data)

        if (not self.msg_size) and (self.data_buffer_size >= self.header_size):
            self.msg_size = self.encoded_size(self.data_buffer)

        print('data_buffer_size: {}'.format(self.data_buffer_size))
        print('msg_size: {}'.format(self.msg_size))

        if (self.data_buffer_size - self.header_size) >= self.msg_size:
            # got a complete msg, do stuff with it:
            self.route(self.handler, data[self.header_size:])
            
            # reset for next msg
            print('## RESET ##')
            self.msg_size = 0
            self.data_buffer = bytearray(data[self.data_buffer_size:])
            self.data_buffer_size = len(self.data_buffer)


    def connection_lost(self, exc):
        print('lost connection')


    def encoded_size(self, data):
        "return size based on header_size (in bytes)"
        return unpack('<I', data[:self.header_size])[0]

    def route(self, handler, msg):
        print('got message: {}'.format(msg))



def pack_proto(msg):
    msg_t = msg.__class__.__name__
    return tuple((msg_dict[msg_t][0],) + tuple((getattr(msg, f) for f in msg._fields)))

def unpack_proto(msg):
    msg_t = msg_dict_rev[msg[0]]
    return msg_t(*msg[1:])

def encode(msg):
    return packb(pack_proto(msg))

def decode(msg_buff):
    return unpack_proto(unpackb(msg_buff))


def compress_buff(buff):
    return compress(buff)

def decompress_buff(buff):
    return decompress(buff)

class EncodeError(Exception):
    pass

class DecodeError(Exception):
    pass

class SetValuesRequestError(Exception):
    pass


class BadHandshake(Exception):
    pass