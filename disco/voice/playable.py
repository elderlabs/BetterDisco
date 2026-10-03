from abc import ABCMeta, abstractmethod as abc_abstractmethod
try:
    from audioop import mul as audioop_mul
except ImportError:
    audioop_mul = None
from gevent import sleep as gevent_sleep, spawn as gevent_spawn
from gevent.lock import Semaphore as GeventSemaphore
from gevent.subprocess import PIPE as GEVENT_PIPE, Popen as GeventPopen
from io import BytesIO
from sys import modules as sys_modules
from types import GeneratorType
try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError
    from yt_dlp.networking.exceptions import HTTPError
    from yt_dlp.networking.impersonate import ImpersonateTarget
    try:
        import curl_cffi
        from random import choice as random_choice
    except ImportError:
        curl_cffi = None
except ImportError:
    YoutubeDL = None

from disco.util.metaclass import add_metaclass
from disco.voice.opus import OpusEncoder


class AbstractOpus:
    def __init__(self, sampling_rate=48000, frame_length=20, channels=2):
        self.sampling_rate = sampling_rate
        self.frame_length = frame_length
        self.channels = channels
        self.sample_size = 2 * self.channels
        self.samples_per_frame = int(self.sampling_rate / 1000 * self.frame_length)
        self.frame_size = self.samples_per_frame * self.sample_size


class BaseUtil:
    def pipe(self, other, *args, **kwargs):
        child = other(self, *args, **kwargs)
        setattr(child, 'metadata', self.metadata)
        setattr(child, '_parent', self)
        return child

    @property
    def metadata(self):
        return getattr(self, '_metadata', None)

    @metadata.setter
    def metadata(self, value):
        self._metadata = value


@add_metaclass(ABCMeta)
class BasePlayable(BaseUtil):
    @abc_abstractmethod
    def next_frame(self):
        raise NotImplementedError


@add_metaclass(ABCMeta)
class BaseInput(BaseUtil):
    @abc_abstractmethod
    def read(self, size):
        raise NotImplementedError


class FFmpegInput(BaseInput, AbstractOpus):
    def __init__(self, source='-', command='ffmpeg', streaming=False, **kwargs):
        super(FFmpegInput, self).__init__(**kwargs)
        if source:
            self.source = source
        self.command = command
        if streaming:
            self.streaming = streaming

        self._buffer = None
        self._proc = None

    def read(self, sz):
        if not self._buffer:
            if self.streaming:
                self._buffer = self.proc.stdout
            else:
                self._buffer = BytesIO(self.proc.stdout.read())

        return self._buffer.read(sz)

    @property
    def proc(self):
        if not self._proc:
            if callable(self.source):
                self.source = self.source(self)

            if isinstance(self.source, (tuple, list)):
                self.source, self.metadata = self.source

            args = [
                self.command,
                '-nostdin',
                '-user_agent', '"Mozilla/5.0 (Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"',
                '-i', str(self.source),
                '-vn',
                '-f', 's16le',
                '-ar', str(self.sampling_rate),
                '-ac', str(self.channels),
                '-loglevel', 'fatal',
                '-hls_time', '10',
                '-hls_playlist_type', 'event',
                'pipe:1',
            ]
            self._proc = GeventPopen(args, stdout=GEVENT_PIPE)
        return self._proc


class YoutubeDLInput(FFmpegInput):
    def __init__(self, url=None, ie_info=None, *args, **kwargs):
        if YoutubeDL and curl_cffi:
            self.ytdl = YoutubeDL({'format': 'webm[abr>0]/bestaudio/best', 'default_search': 'ytsearch', 'impersonate': ImpersonateTarget.from_str(random_choice(('chrome', 'firefox', 'edge', 'safari')))})
        elif YoutubeDL:
            self.ytdl = YoutubeDL({'format': 'webm[abr>0]/bestaudio/best', 'default_search': 'ytsearch'})
        else:
            self.ytdl = None
        super(YoutubeDLInput, self).__init__(None, *args, **kwargs)
        self._url = url
        self._ie_info = ie_info
        self._info = None
        self._info_lock = GeventSemaphore()

    @property
    def info(self):
        with self._info_lock:
            if not self._info:
                assert self.ytdl is not None, 'yt_dlp isn\'t installed'
                if self._url:
                    try:
                        results = self.ytdl.extract_info(self._url, download=False)
                    except (DownloadError, HTTPError) as e:
                        return self.log.error(f'YTDL Error - {e.__class__.__name__}: {e}')
                    if 'entries' not in results:
                        self._ie_info = results
                    else:
                        # logic to ignore live versions of a song if we're not asking for them when searching
                        # rudimentary at the moment, but it's enough to get the job done
                        # disabled by default if not specifically asking for multiple results
                        if 'ytsearch' in self._url and len(self._url.split()) > 1 and len(results['entries']) > 1:
                            self._ie_info = None
                            ignored_terms = ('LIVE', 'VIDEO')
                            for entry in results['entries']:
                                for term in ignored_terms:
                                    if term in entry['title'].upper() and term not in self._url.upper():
                                        continue
                                    self._ie_info = entry
                                    break
                                if self._ie_info:
                                    break
                            if not self._ie_info:
                                self._ie_info = results['entries'][0]
                        else:
                            self._ie_info = results['entries'][0]

                    self._info = self._ie_info
                    if 'is_live' not in self._ie_info:
                        self._ie_info['is_live'] = False

                    if not self._info:
                        raise Exception("Couldn't find valid audio format for {}".format(self._url))

            return self._info

    @property
    def _metadata(self):
        return self.info

    # TODO: :thinking:
    @classmethod
    def many(cls, url, *args, **kwargs):
        info = cls.ytdl.extract_info(url, download=False)

        if 'entries' not in info:
            yield cls(ie_info=info, *args, **kwargs)
            return

        for item in info['entries']:
            yield cls(ie_info=item, *args, **kwargs)

    @property
    def source(self):
        return self.info['url']

    @property
    def streaming(self):
        return self.info['is_live']


class BufferedOpusEncoderPlayable(BasePlayable, OpusEncoder, AbstractOpus):
    def __init__(self, source, volume=1.0, frame_buffer=100, *args, **kwargs):
        from gevent.queue import Queue as GeventQueue
        self.source = source
        self.frames = GeventQueue()
        self.frame_buffer = frame_buffer
        self.volume = volume
        self.transmitting = True
        self._encoder_task = None
        self._streaming = None

        # Call the AbstractOpus constructor, as we need properties it sets
        AbstractOpus.__init__(self, *args, **kwargs)

    def _start_encoder(self):
        # The encoder and its source should not be started until this playable
        # becomes active. This is particularly meaningful for playlist queues.
        OpusEncoder.__init__(self, self.sampling_rate, self.channels)
        self._frame_buffer = self.frame_buffer if self.streaming else min(self.frame_buffer, 25)
        self._encoder_task = gevent_spawn(self._encoder_loop)

    def _encoder_loop(self):
        while self.source:
            if len(self.frames.queue) >= self._frame_buffer:
                gevent_sleep(0.02)
                continue

            raw = self.source.read(self.frame_size)
            if len(raw) < self.frame_size:
                break

            if self.streaming and not self.transmitting:
                gevent_sleep(0.02)
                continue

            if self._volume != 1.0:
                raw = audioop_mul(raw, 2, min(self._volume, 2.0))

            self.frames.put(self.encode(raw, self.samples_per_frame))
        self.source = None
        self.frames.put(None)

    def next_frame(self):
        if not self._encoder_task:
            self._start_encoder()
        return self.frames.get()

    def set_transmitting(self, transmitting):
        self.transmitting = transmitting
        if self.streaming and not transmitting:
            self.frames.queue.clear()

    @property
    def streaming(self):
        if self._streaming is None:
            self._streaming = self.source.streaming
        return self._streaming

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        if 'audioop' not in sys_modules.keys():
            self._volume = 1.0
            raise Exception('audioop-lts not installed. Volume support is unavailable.')
        if 0.0 > value:
            raise Exception('Volume accepts float values between 0.0 and 2.0 only.')
        self._volume = min(value, 2.0)


class PlaylistPlayable(BasePlayable, AbstractOpus):
    def __init__(self, items, *args, **kwargs):
        super(PlaylistPlayable, self).__init__(*args, **kwargs)
        self.items = items
        self.now_playing = None

    def _get_next(self):
        if isinstance(self.items, GeneratorType):
            return next(self.items, None)
        return self.items.pop()

    def next_frame(self):
        if not self.items:
            return

        if not self.now_playing:
            self.now_playing = self._get_next()
            if not self.now_playing:
                return

        frame = self.now_playing.next_frame()
        if not frame:
            return self.next_frame()

        return frame


class MemoryBufferedPlayable(BasePlayable, AbstractOpus):
    def __init__(self, other, *args, **kwargs):
        from gevent.queue import Queue as GeventQueue

        super(MemoryBufferedPlayable, self).__init__(*args, **kwargs)
        self.frames = GeventQueue()
        self.other = other
        gevent_spawn(self._buffer)

    def _buffer(self):
        while True:
            frame = self.other.next_frame()
            if not frame:
                break
            self.frames.put(frame)
        self.frames.put(None)

    def next_frame(self):
        return self.frames.get()
