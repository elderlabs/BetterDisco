import abc
import audioop
import gevent
import struct
import types

from gevent.lock import Semaphore
from gevent.queue import Queue
from io import BytesIO
from six import add_metaclass

from disco.voice.opus import OpusEncoder

try:
    import yt_dlp
    ytdl = yt_dlp.YoutubeDL({'format': 'webm[abr>0]/bestaudio/best', 'default_search': 'ytsearch'})
except ImportError:
    ytdl = None

OPUS_HEADER_SIZE = struct.calcsize('<h')


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


@add_metaclass(abc.ABCMeta)
class BasePlayable(BaseUtil):
    @abc.abstractmethod
    def next_frame(self):
        raise NotImplementedError


@add_metaclass(abc.ABCMeta)
class BaseInput(BaseUtil):
    @abc.abstractmethod
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
            # allows time for a buffer to form, otherwise there is nothing to send
            gevent.sleep(1)
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
                'stdbuf', '-oL',
                self.command,
                '-user_agent', '"Mozilla/5.0 (Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"',
                '-i', str(self.source),
                '-f', 's16le',
                '-ar', str(self.sampling_rate),
                '-ac', str(self.channels),
                '-ab', '192k',
                '-bufsize', str(self.sampling_rate),
                '-loglevel', 'fatal',
                '-hls_time', '10',
                '-hls_playlist_type', 'event',
                'pipe:1',
            ]
            self._proc = gevent.subprocess.Popen(args, stdout=gevent.subprocess.PIPE)
        return self._proc


class YoutubeDLInput(FFmpegInput):
    def __init__(self, url=None, ie_info=None, *args, **kwargs):
        super(YoutubeDLInput, self).__init__(None, *args, **kwargs)
        self._url = url
        self._ie_info = ie_info
        self._info = None
        self._info_lock = Semaphore()

    @property
    def info(self):
        with self._info_lock:
            if not self._info:
                assert ytdl is not None, 'yt_dlp isn\'t installed'
                if self._url:
                    results = ytdl.extract_info(self._url, download=False)

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
        info = ytdl.extract_info(url, download=False)

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
        self.source = source
        self.frames = Queue()
        self.frame_buffer = frame_buffer
        self.volume = volume

        # Call the AbstractOpus constructor, as we need properties it sets
        AbstractOpus.__init__(self, *args, **kwargs)

        # Then call the OpusEncoder constructor, which requires some properties
        #  that AbstractOpus sets up
        OpusEncoder.__init__(self, self.sampling_rate, self.channels)

        # Spawn the encoder loop
        gevent.spawn(self._encoder_loop)

    def _encoder_loop(self):
        while self.source:
            if len(self.frames.queue) < self.frame_buffer:
                if self._volume != 1.0:
                    raw = audioop.mul(self.source.read(self.frame_size), 2, min(self._volume, 2.0))
                else:
                    raw = self.source.read(self.frame_size)
                if len(raw) < self.frame_size:
                    break

                self.frames.put(self.encode(raw, self.samples_per_frame))
            gevent.sleep(0.002)
        self.source = None
        self.frames.put(None)

    def next_frame(self):
        return self.frames.get()

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        if 0.0 > value:
            raise Exception('Volume accepts float values between 0.0 and 2.0 only')
        self._volume = min(value, 2.0)


class PlaylistPlayable(BasePlayable, AbstractOpus):
    def __init__(self, items, *args, **kwargs):
        super(PlaylistPlayable, self).__init__(*args, **kwargs)
        self.items = items
        self.now_playing = None

    def _get_next(self):
        if isinstance(self.items, types.GeneratorType):
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
        from gevent.queue import Queue

        super(MemoryBufferedPlayable, self).__init__(*args, **kwargs)
        self.frames = Queue()
        self.other = other
        gevent.spawn(self._buffer)

    def _buffer(self):
        while True:
            frame = self.other.next_frame()
            if not frame:
                break
            self.frames.put(frame)
        self.frames.put(None)

    def next_frame(self):
        return self.frames.get()
