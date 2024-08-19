from collections import namedtuple
from struct import pack_into as struct_pack_into, unpack_from as struct_unpack_from, unpack as struct_unpack
from socket import socket, gethostbyname as socket_gethostbyname, AF_INET as SOCKET_AF_INET, SOCK_DGRAM as SOCKET_SOCK_DGRAM
from gevent import spawn as gevent_spawn, Timeout as GeventTimeout

from disco.util.crypto import AEScrypt
from disco.util.enum import Enum
from disco.util.logging import LoggingClass

AudioCodecs = ('opus',)
VideoCodecs = ('AV1X', 'H265', 'H264', 'VP8', 'VP9')

RTPPayloadTypes = Enum(
    OPUS=0x78,  # 120
    # AV1X=0x,  # ?
    H265=0x65,  # 101
    H264=0x67,  # 103
    VP8=0x69,  # 105
    VP9=0x71,  # 107
)

RTCPPayloadTypes = Enum(
    SENDER_REPORT=200,
    RECEIVER_REPORT=201,
    SOURCE_DESCRIPTION=202,
    BYE=203,
    APP=204,
    RTPFB=205,
    PSFB=206,
)

MAX_UINT32 = 4294967295
MAX_SEQUENCE = 65535

RTP_HEADER_VERSION = 0x80  # Only RTP Version is set here (value of 2 << 6)
RTP_EXTENSION_ONE_BYTE = (0xBE, 0xDE)

RTPHeader = namedtuple('RTPHeader', [
    'version',
    'padding',
    'extension',
    'csrc_count',
    'marker',
    'payload_type',
    'sequence',
    'timestamp',
    'ssrc',
])

RTCPHeader = namedtuple('RTCPHeader', [
    'version',
    'padding',
    'reception_count',
    'packet_type',
    'length',
    'ssrc',
])

RTCPData = namedtuple('RTCPData', [
    'client',
    'user_id',
    'payload_type',
    'header',
    'data',
])

VoiceData = namedtuple('VoiceData', [
    'client',
    'user_id',
    'payload_type',
    'rtp',
    'nonce',
    'data',
])

VideoData = namedtuple('VideoData', [
    'client',
    'user_id',
    'payload_type',
    'rtp',
    'nonce',
    'data',
])


class UDPVoiceClient(LoggingClass):
    def __init__(self, vc):
        super(UDPVoiceClient, self).__init__()
        self.vc = vc

        # The underlying UDP socket
        self.conn = None

        # Connection information
        self.ip = None
        self.port = None
        self.connected = False

        # Voice information
        self.sequence = 0
        self.timestamp = 0

        self._nonce = 0
        self._run_task = None
        self._secret_box = None

        # RTP Header
        self._rtp_audio_header = bytearray(12)
        self._rtp_video_header = bytearray(12)
        self._rtp_audio_header[0] = RTP_HEADER_VERSION
        self._rtp_video_header[0] = RTP_HEADER_VERSION

    def set_audio_codec(self, codec):
        if codec not in AudioCodecs:
            raise Exception('Unsupported audio codec received, {}'.format(codec))

        ptype = RTPPayloadTypes.get(codec)
        self._rtp_audio_header[1] = ptype.value
        self.log.debug('[{}] Set UDP\'s Audio Codec to {}, RTP payload type {}'.format(self.vc.channel_id, ptype.name.upper(), ptype.value))

    def set_video_codec(self, codec):
        if codec not in VideoCodecs:
            raise Exception(f'Unsupported video codec received, {codec}')

        ptype = RTPPayloadTypes.get(codec.lower())
        self._rtp_video_header[1] = ptype.value
        self.log.debug('[{}] Set UDP\'s Video Codec to {}, RTP payload type {}'.format(self.vc.channel_id, ptype.name.upper(), ptype.value))

    def increment_timestamp(self, by):
        self.timestamp += by
        if self.timestamp > MAX_UINT32:
            self.timestamp = 0

    def setup_encryption(self, encryption_key):
        self._secret_box = AEScrypt(encryption_key, self.vc.mode)

    def send_frame(self, frame, sequence=None, timestamp=None, incr_timestamp=None):
        # Pack the RTC header into our buffer (a list of numbers)
        struct_pack_into('>H', self._rtp_audio_header, 2, sequence or self.sequence)  # BE, unsigned short
        struct_pack_into('>I', self._rtp_audio_header, 4, timestamp or self.timestamp)  # BE, unsigned int
        struct_pack_into('>i', self._rtp_audio_header, 8, self.vc.ssrc_audio)  # BE, int

        if self.vc.mode == 'aead_aes256_gcm_rtpsize':
            nonce = bytearray(12)  # 96-bits
        else:
            nonce = bytearray(24)  # 192-bits is 24 bytes

        # Use an incrementing number as a nonce, only first 4 bytes of the nonce is padded on
        self._nonce += 1
        if self._nonce > MAX_UINT32:
            self._nonce = 0
        struct_pack_into('>I', nonce, 0, self._nonce)  # BE, unsigned int
        nonce_padding = nonce[:4]

        if self.vc.mode not in ('aead_xchacha20_poly1305_rtpsize', 'aead_aes256_gcm_rtpsize'):
            raise Exception(f'Voice mode `{self.vc.mode}` is not supported.')

        # Encrypt the payload with the nonce
        payload = self._secret_box.encrypt(plaintext=frame, nonce=bytes(nonce), aad=bytes(self._rtp_audio_header))
        payload = payload.ciphertext

        # Pad the payload with the nonce, if applicable
        if nonce_padding:
            payload += nonce_padding

        # Send the header (sans nonce padding) plus the payload
        self.send(self._rtp_audio_header + payload)

        # Increment our sequence counter
        self.sequence += 1
        if self.sequence >= MAX_SEQUENCE:
            self.sequence = 0

        # Increment our timestamp (if applicable)
        if incr_timestamp:
            self.timestamp += incr_timestamp

    def run(self):
        while True:
            data, addr = self.conn.recvfrom(1500)  # Max RTP packet length

            # Data cannot be less than the bare minimum, just ignore
            if len(data) <= 12:
                self.log.debug('[{}] [VoiceData] Received voice data under 13 bytes'.format(self.vc.channel_id))
                continue

            first, second = struct_unpack_from('>BB', data)  # big-endian, 2x unsigned chars

            payload_type = RTCPPayloadTypes.get(second)
            if payload_type:
                length, ssrc = struct_unpack_from('>HI', data, 2)  # BE, unsigned short, unsigned int

                rtcp = RTCPHeader(
                    version=first >> 6,
                    padding=(first >> 5) & 1,
                    reception_count=first & 0x1F,
                    packet_type=second,
                    length=length,
                    ssrc=ssrc,
                )

                if rtcp.ssrc == self.vc.ssrc_rtcp:
                    user_id = self.vc.user_id
                else:
                    rtcp_ssrc = rtcp.ssrc
                    if rtcp_ssrc:
                        rtcp_ssrc -= 3
                    user_id = self.vc.audio_ssrcs.get(rtcp_ssrc, None)

                payload = RTCPData(
                    client=self.vc,
                    user_id=user_id,
                    payload_type=payload_type.name,
                    header=rtcp,
                    data=data[8:],
                )

                self.vc.client.events.emit('RTCPData', payload)
            else:
                sequence, timestamp, ssrc = struct_unpack_from('>HII', data, 2)  # BE, unsigned short, 2x unsigned int

                rtp = RTPHeader(
                    version=first >> 6,
                    padding=(first >> 5) & 1,
                    extension=(first >> 4) & 1,
                    csrc_count=first & 0x0F,
                    marker=second >> 7,
                    payload_type=second & 0x7F,
                    sequence=sequence,
                    timestamp=timestamp,
                    ssrc=ssrc,
                )

                # Check if rtp version is 2
                if rtp.version != 2:
                    self.log.debug('[{}] [VoiceData] Received an invalid RTP packet version, {}'.format(self.vc.channel_id, rtp.version))
                    continue

                payload_type = RTPPayloadTypes.get(rtp.payload_type)

                # Unsupported payload type received
                if not payload_type:
                    self.log.debug('[{}] [VoiceData] Received unsupported payload type, {}'.format(self.vc.channel_id, rtp.payload_type))
                    continue

                if self.vc.mode == 'aead_aes256_gcm_rtpsize':
                    nonce = bytearray(12)  # 96-bits
                else:
                    nonce = bytearray(24)  # 192-bits is 24 bytes

                nonce[:4] = data[-4:]
                data = data[:-4]

                if self.vc.mode not in ('aead_xchacha20_poly1305_rtpsize', 'aead_aes256_gcm_rtpsize'):
                    self.log.debug(f'[{self.vc.channel_id}] [VoiceData] Unsupported Encryption Mode, {self.vc.mode}')
                    continue

                header_size = 12
                header_size += (rtp.csrc_count * 4)
                if rtp.extension:
                    header_size += 4
                ctxt = data[header_size:]  # plus strip whatever additional bs is before the payload

                try:
                    data = self._secret_box.decrypt(ciphertext=bytes(ctxt), nonce=bytes(nonce), aad=bytes(data[:header_size]))
                except Exception as e:
                    self.log.debug('[{}] [VoiceData] Failed to decode data from ssrc {}: {} - {}'.format(self.vc.channel_id, rtp.ssrc, e.__class__.__name__, e))
                    continue

                # RFC3550 Section 5.1 (Padding)
                if rtp.padding:
                    padding_amount, = struct_unpack_from('>B', data[:-1])  # BE, unsigned char
                    data = data[-padding_amount:]

                if rtp.extension:
                    # RFC5285 Section 4.2: One-Byte Header
                    rtp_extension_header = struct_unpack_from('>BB', data)  # BE, 2x unsigned char
                    if rtp_extension_header == RTP_EXTENSION_ONE_BYTE:
                        data = data[2:]

                        fields_amount, = struct_unpack_from('>H', data)  # BE, unsigned short
                        fields = []

                        offset = 4
                        for i in range(fields_amount):
                            first_byte, = struct_unpack_from('>B', data[:offset])  # BE, unsigned char
                            offset += 1

                            rtp_extension_identifier = first_byte & 0xF
                            rtp_extension_len = ((first_byte >> 4) & 0xF) + 1

                            # Ignore data if identifier == 15, so skip if this is set as 0
                            if rtp_extension_identifier:
                                fields.append(data[offset:offset + rtp_extension_len])

                            offset += rtp_extension_len

                            # skip padding
                            while data[offset] == 0:
                                offset += 1

                        if len(fields):
                            fields.append(data[offset:])
                            data = b''.join(fields)
                        else:
                            data = data[offset:]

                # RFC3550 Section 5.3: Profile-Specific Modifications to the RTP Header
                # clients send it sometimes, definitely on fresh connects to a server, dunno what to do here
                # RFC6184: Marker bits are used to signify the last packet of a frame
                if rtp.marker and payload_type.name == 'opus':
                    self.log.debug('[{}] [VoiceData] Received RTP data with the marker set, skipping'.format(self.vc.channel_id))
                    continue

                if payload_type.name == 'opus':
                    payload = VoiceData(
                        client=self.vc,
                        user_id=self.vc.audio_ssrcs.get(rtp.ssrc),
                        payload_type=payload_type.name,
                        rtp=rtp,
                        nonce=nonce,
                        data=data,
                    )

                    # Raw RTP stream data, still needs conversion to be useful
                    self.vc.client.events.emit('VoiceData', payload)
                else:
                    payload = VideoData(
                        client=self.vc,
                        user_id=self.vc.video_ssrcs.get(rtp.ssrc),
                        payload_type=payload_type.name,
                        rtp=rtp,
                        nonce=nonce,
                        data=data,
                    )

                    # Raw RTP stream data, still needs conversion to be useful
                    self.vc.client.events.emit('VideoData', payload)

    def send(self, data):
        self.conn.sendto(data, (self.ip, self.port))

    def disconnect(self):
        if self._run_task:
            self._run_task.kill()
        return

    def connect(self, host, port, timeout=10, addrinfo=None):
        self.ip = socket_gethostbyname(host)
        self.port = port

        self.conn = socket(SOCKET_AF_INET, SOCKET_SOCK_DGRAM)

        if addrinfo:
            ip, port = addrinfo
        else:
            # Send discovery packet
            packet = bytearray(74)
            struct_pack_into('>H', packet, 0, 1)  # BE, unsigned short
            struct_pack_into('>H', packet, 2, 70)  # BE, unsigned short
            struct_pack_into('>I', packet, 4, self.vc.ssrc)  # BE, unsigned int
            self.send(packet)

            # Wait for a response
            try:
                data, addr = gevent_spawn(lambda: self.conn.recvfrom(74)).get(timeout=timeout)
            except GeventTimeout:
                return None, None

            # Read IP and port
            ip = str(data[8:]).split('\x00', 1)[0]
            port = struct_unpack('<H', data[-2:])[0]  # little endian, unsigned short

        # Spawn read thread so we don't max buffers
        self.connected = True
        self._run_task = gevent_spawn(self.run)

        return ip, port
