from collections import namedtuple
from struct import pack_into as struct_pack_into, unpack_from as struct_unpack_from, unpack as struct_unpack
from socket import socket, gethostbyname as socket_gethostbyname, AF_INET as SOCKET_AF_INET, SOCK_DGRAM as SOCKET_SOCK_DGRAM
from gevent import spawn as gevent_spawn, Timeout as GeventTimeout

from disco.util.crypto import AEScrypt
from disco.util.enum import Enum
from disco.util.logging import LoggingClass
from disco.voice.opus import OpusDecoder

AudioCodecs = ('opus',)
VideoCodecs = ('AV1X', 'H265', 'H264', 'VP8', 'VP9',)

RTPPayloadTypes = Enum(
    OPUS=0x78,       # 120
    AV1X=0x63,       # 99
    AV1X_RTX=0x64,   # 100
    H265=0x65,       # 101
    H265_RTX=0x66,   # 102
    H264=0x67,       # 103
    H264_RTX=0x68,   # 104
    VP8=0x69,        # 105
    VP8_RTX=0x6A,    # 106
    VP9=0x6B,        # 107
    VP9_RTX=0x6C,    # 108
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
OPUS_FRAME_SAMPLES = 960
OPUS_SAMPLING_RATE = 48000
OPUS_CHANNELS = 2
OPUS_SAMPLE_WIDTH = 2
OPUS_SILENCE_FRAME = b'\xf8\xff\xfe'

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
    'pcm',
    'timestamp',
    'duration',
    'silence',
])
VoiceData.__new__.__defaults__ = (None, None, 0, 0)

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
        self._nonce_data = bytearray(24)
        self._nonce_padding = bytearray(4)
        self._run_task = None
        self._secret_box = None
        self._opus_decoders = {}
        self._audio_state = {}

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

        if self._secret_box._disabled:
            raise Exception('libnacl is not installed, voice support is unavailable')

    def send_frame(self, frame, sequence=None, timestamp=None, incr_timestamp=None):
        if sequence is None:
            sequence = self.sequence
        if timestamp is None:
            timestamp = self.timestamp
        # Pack the RTP header into our buffer (a list of numbers)
        struct_pack_into('>H', self._rtp_audio_header, 2, sequence)  # BE, unsigned short
        struct_pack_into('>I', self._rtp_audio_header, 4, timestamp)  # BE, unsigned int
        struct_pack_into('>I', self._rtp_audio_header, 8, self.vc.ssrc_audio)  # BE, unsigned int

        if self.vc.mode == 'aead_aes256_gcm_rtpsize':
            nonce_size = 12  # 96-bits
        elif self.vc.mode == 'aead_xchacha20_poly1305_rtpsize':
            nonce_size = 24  # 192-bits
        else:
            raise Exception(f'Voice mode `{self.vc.mode}` is not supported.')

        # Use an incrementing number as a nonce. Only the first four bytes
        # contain the counter; the remaining bytes remain zero.
        self._nonce += 1
        if self._nonce > MAX_UINT32:
            self._nonce = 0
        struct_pack_into('>I', self._nonce_data, 0, self._nonce)  # BE, unsigned int
        struct_pack_into('>I', self._nonce_padding, 0, self._nonce)  # BE, unsigned int

        # Encrypt the payload with the nonce
        payload = self._secret_box.encrypt(plaintext=frame, nonce=bytes(self._nonce_data[:nonce_size]), aad=bytes(self._rtp_audio_header))

        # Pad the payload with the nonce
        payload += self._nonce_padding
        self.send(self._rtp_audio_header + payload)

        # Increment our sequence counter
        self.sequence += 1
        if self.sequence > MAX_SEQUENCE:
            self.sequence = 0

        # Increment our timestamp (if applicable)
        if incr_timestamp is not None:
            self.increment_timestamp(incr_timestamp)

    def send_silence(self, frames=5):
        for _ in range(frames):
            self.send_frame(OPUS_SILENCE_FRAME, incr_timestamp=OPUS_FRAME_SAMPLES)

    def decode_audio(self, user_id, rtp, data):
        if not self.vc.client.events.has_listeners('VoiceData'):
            return None

        try:
            data = self.vc.decrypt_voice_frame(user_id, data)
        except Exception as e:
            self.log.debug('[{}] [VoiceData] Failed to decrypt DAVE data from ssrc {}: {} - {}'.format(
                self.vc.channel_id, rtp.ssrc, e.__class__.__name__, e,
            ))
            return None

        decoder = self._opus_decoders.get(rtp.ssrc)
        if not decoder:
            decoder = OpusDecoder(OPUS_SAMPLING_RATE, OPUS_CHANNELS)
            self._opus_decoders[rtp.ssrc] = decoder

        try:
            pcm, duration = decoder.decode(data)
        except Exception as e:
            self.log.debug('[{}] [VoiceData] Failed to decode Opus data from ssrc {}: {} - {}'.format(
                self.vc.channel_id, rtp.ssrc, e.__class__.__name__, e,
            ))
            return None

        state_key = user_id if user_id is not None else rtp.ssrc
        state = self._audio_state.get(state_key)
        if state is None or state['ssrc'] != rtp.ssrc:
            if state:
                self._opus_decoders.pop(state['ssrc'], None)
            state = {
                'ssrc': rtp.ssrc,
                'rtp_timestamp': rtp.timestamp,
                'timestamp': state['timestamp'] if state else 0,
                'duration': duration,
            }
            self._audio_state[state_key] = state
            silence = duration if data == OPUS_SILENCE_FRAME else 0
            return pcm, state['timestamp'], duration, silence

        delta = (rtp.timestamp - state['rtp_timestamp']) & MAX_UINT32
        if delta > (MAX_UINT32 // 2):
            delta -= MAX_UINT32 + 1

        if delta <= 0:
            return None

        if delta > state['duration']:
            silence = delta - state['duration']
        else:
            silence = 0

        state['timestamp'] += delta
        state['rtp_timestamp'] = rtp.timestamp
        state['duration'] = duration

        if data == OPUS_SILENCE_FRAME:
            silence += duration

        return pcm, state['timestamp'], duration, silence

    def remove_audio_ssrc(self, ssrc, user_id=None):
        self._opus_decoders.pop(ssrc, None)
        if user_id is not None:
            state = self._audio_state.get(user_id)
            if state and state['ssrc'] == ssrc:
                self._audio_state.pop(user_id, None)
        else:
            self._audio_state.pop(ssrc, None)

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
                    nonce = bytearray(24)  # 192-bits

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
                    user_id = self.vc.audio_ssrcs.get(rtp.ssrc)
                    decoded = self.decode_audio(user_id, rtp, data)
                    if decoded is None:
                        continue

                    pcm, audio_timestamp, duration, silence = decoded
                    payload = VoiceData(
                        client=self.vc,
                        user_id=user_id,
                        payload_type=payload_type.name,
                        rtp=rtp,
                        nonce=nonce,
                        data=data,
                        pcm=pcm,
                        timestamp=audio_timestamp,
                        duration=duration,
                        silence=silence,
                    )

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
            self._run_task = None
        self._opus_decoders.clear()
        self._audio_state.clear()
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
            ip = str(data[8:].split(b'\x00', 1)[0], "utf-8")
            port = struct_unpack('<H', data[-2:])[0]  # little endian, unsigned short

        # Spawn read thread so we don't max buffers
        self.connected = True
        self._run_task = gevent_spawn(self.run)

        return ip, port
