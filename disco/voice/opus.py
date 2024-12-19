from array import array
from ctypes import POINTER, Structure as ctypes_Structure, c_int, c_int16, c_int32, c_float, c_char_p, cdll, \
    util as c_util, byref as c_byref, c_char, cast as c_cast
from platform import system as platform_system

from disco.util.logging import LoggingClass


c_int_ptr = POINTER(c_int)
c_int16_ptr = POINTER(c_int16)
c_float_ptr = POINTER(c_float)


class EncoderStruct(ctypes_Structure):
    pass


class DecoderStruct(ctypes_Structure):
    pass


EncoderStructPtr = POINTER(EncoderStruct)
DecoderStructPtr = POINTER(DecoderStruct)


class BaseOpus(LoggingClass):
    BASE_EXPORTED = {
        'opus_strerror': ([c_int], c_char_p),
    }

    EXPORTED = {}

    def __init__(self, library_path=None):
        self.path = library_path or self.find_library()
        self.lib = cdll.LoadLibrary(self.path)

        methods = {}
        methods.update(self.BASE_EXPORTED)
        methods.update(self.EXPORTED)

        for name, item in methods.items():
            func = getattr(self.lib, name)

            if item[0]:
                func.argtypes = item[0]

            func.restype = item[1]

            setattr(self, name, func)

    @staticmethod
    def find_library():
        if platform_system() == 'Windows':
            raise Exception('Cannot auto-load opus on Windows, please specify full library path')

        return c_util.find_library('opus')


class Application:
    AUDIO = 2049
    VOIP = 2048
    LOWDELAY = 2051


class Control:
    SET_BITRATE = 4002
    SET_BANDWIDTH = 4008
    SET_FEC = 4012
    SET_PLP = 4014


class OpusEncoder(BaseOpus):
    EXPORTED = {
        'opus_encoder_get_size': ([c_int], c_int),
        'opus_encoder_create': ([c_int, c_int, c_int, c_int_ptr], EncoderStructPtr),
        'opus_encode': ([EncoderStructPtr, c_int16_ptr, c_int, c_char_p, c_int32], c_int32),
        'opus_encoder_ctl': (None, c_int32),
        'opus_encoder_destroy': ([EncoderStructPtr], None),
    }

    def __init__(self, sampling_rate, channels, application=Application.AUDIO, library_path=None):
        super(OpusEncoder, self).__init__(library_path)
        self.sampling_rate = sampling_rate
        self.channels = channels
        self.application = application

        self._inst = None

    @property
    def inst(self):
        if not self._inst:
            self._inst = self.create()
            self.set_bitrate(128)
            self.set_fec(True)
            self.set_expected_packet_loss_percent(0.15)
        return self._inst

    def set_bitrate(self, kbps):
        kbps = min(128, max(16, int(kbps)))
        ret = self.opus_encoder_ctl(self.inst, int(Control.SET_BITRATE), kbps * 1024)

        if ret < 0:
            raise Exception('Failed to set bitrate to {}: {}'.format(kbps, ret))

    def set_fec(self, value):
        ret = self.opus_encoder_ctl(self.inst, int(Control.SET_FEC), int(value))

        if ret < 0:
            raise Exception('Failed to set FEC to {}: {}'.format(value, ret))

    def set_expected_packet_loss_percent(self, perc):
        ret = self.opus_encoder_ctl(self.inst, int(Control.SET_PLP), min(100, max(0, int(perc * 100))))

        if ret < 0:
            raise Exception('Failed to set PLP to {}: {}'.format(perc, ret))

    def create(self):
        ret = c_int()
        result = self.opus_encoder_create(self.sampling_rate, self.channels, self.application, c_byref(ret))

        if ret.value != 0:
            raise Exception('Failed to create opus encoder: {}'.format(ret.value))

        return result

    def __del__(self):
        if hasattr(self, '_inst') and self._inst:
            self.opus_encoder_destroy(self._inst)
            self._inst = None

    def encode(self, pcm, frame_size):
        max_data_bytes = len(pcm)
        pcm = c_cast(pcm, c_int16_ptr)
        data = (c_char * max_data_bytes)()

        ret = self.opus_encode(self.inst, pcm, frame_size, data, max_data_bytes)
        if ret < 0:
            raise Exception('Failed to encode: {}'.format(ret))

        return array('b', data[:ret]).tobytes()


class OpusDecoder(BaseOpus):
    pass
