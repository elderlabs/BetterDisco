import abc
import gevent
import struct
import subprocess
import types

from gevent.lock import Semaphore
from gevent.queue import Queue
from io import BytesIO as BufferedIO
from six import add_metaclass

from disco.voice.opus import OpusEncoder

try:
    import youtube_dl
    ytdl = youtube_dl.YoutubeDL({'format': 'webm[abr>0]/bestaudio/best'})
except ImportError:
    ytdl = None

OPUS_HEADER_SIZE = struct.calcsize('<h')


class AbstractOpus(object):
    def __init__(self, sampling_rate=48000, frame_length=20, channels=2):
        self.sampling_rate = sampling_rate
        self.frame_length = frame_length
        self.channels = 2
        self.sample_size = 2 * self.channels
        self.samples_per_frame = int(self.sampling_rate / 1000 * self.frame_length)
        self.frame_size = self.samples_per_frame * self.sample_size


class BaseUtil(object):
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

    @abc.abstractmethod
    def fileobj(self):
        raise NotImplementedError


class OpusFilePlayable(BasePlayable, AbstractOpus):
    """
    An input which reads opus data from a file or file-like object.
    """
    def __init__(self, fobj, *args, **kwargs):
        super(OpusFilePlayable, self).__init__(*args, **kwargs)
        self.fobj = fobj
        self.done = False

    def next_frame(self):
        if self.done:
            return None

        header = self.fobj.read(OPUS_HEADER_SIZE)
        if len(header) < OPUS_HEADER_SIZE:
            self.done = True
            return None

        data_size = struct.unpack('<h', header)[0]
        data = self.fobj.read(data_size)
        if len(data) < data_size:
            self.done = True
            return None

        return data


class FFmpegInput(BaseInput, AbstractOpus):
    def __init__(self, source='-', command='ffmpeg', streaming=False, **kwargs):
        super(FFmpegInput, self).__init__(**kwargs)
        if source:
            self.source = source
        self.streaming = streaming
        self.command = command

        self._buffer = None
        self._proc = None

    def read(self, sz):
        if self.streaming:
            raise TypeError('Cannot read from a streaming FFmpegInput')

        # First read blocks until the subprocess finishes
        if not self._buffer:
            data, _ = self.proc.communicate()
            self._buffer = BufferedIO(data)

        # Subsequent reads can just do dis thang
        return self._buffer.read(sz)

    def fileobj(self):
        if self.streaming:
            return self.proc.stdout
        else:
            return self

    @property
    def proc(self):
        if not self._proc:
            if callable(self.source):
                self.source = self.source(self)

            if isinstance(self.source, (tuple, list)):
                self.source, self.metadata = self.source

            args = [
                self.command,
                '-i', str(self.source),
                '-f', 's16le',
                '-bufsize', '4M',
                '-ar', str(self.sampling_rate),
                '-ac', str(self.channels),
                '-loglevel', 'warning',
                'pipe:1',
            ]
            self._proc = subprocess.Popen(args, stdin=None, stdout=subprocess.PIPE)
        return self._proc


class YoutubeDLInput(FFmpegInput):
    def __init__(self, url=None, ie_info=None, *args, **kwargs):
        super(YoutubeDLInput, self).__init__(None, *args, **kwargs)
        self._url = url
        self._ie_info = ie_info
        self._info = None
        self._info_lock = Semaphore()
        self._stream = False

    @property
    def info(self):
        with self._info_lock:
            if not self._info:
                assert ytdl is not None, 'YoutubeDL isn\'t installed'
                # ydl = youtube_dl.YoutubeDL({'format': 'webm[abr>0]/bestaudio/best'})
                if self._url:
                    # ytdl.extract_info(self._url, download=False, process=False)
                    results = ytdl.extract_info(self._url, download=False)
                    if 'entries' not in results:
                        self._ie_info = [results]
                    else:
                        self._ie_info = results['entries']

                    for result in self._ie_info:
                        if 'youtube' in result['extractor']:
                            audio_formats = [fmt for fmt in result['formats'] if
                                             fmt['vcodec'] == 'none' and fmt['acodec'] == 'opus']
                        elif result['extractor'] == 'twitch:stream':
                            audio_formats = [fmt for fmt in result['formats'] if fmt['format_id'] == 'audio_only']
                        else:
                            audio_formats = [fmt for fmt in result['formats'] if fmt['ext'] in ['opus', 'mp3']]
                        if not audio_formats:
                            raise Exception("Couldn't find valid audio format for {}".format(self._url))

                        if result['extractor'] == 'twitch:stream':
                            self._info = audio_formats[0]
                            self._stream = True
                        else:
                            self._info = sorted(audio_formats, key=lambda i: i['abr'], reverse=True)[0]
                            self._stream = False

            return self._info

    @property
    def _metadata(self):
        return self.info

    # TODO: :thinking:
    @classmethod
    def many(cls, url, *args, **kwargs):
        # ytdl = youtube_dl.YoutubeDL({'format': 'webm[abr>0]/bestaudio/best'})
        info = ytdl.extract_info(url, download=False, process=False)

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
        if self._stream:
            return True
        return False


class BufferedOpusEncoderPlayable(BasePlayable, OpusEncoder, AbstractOpus):
    def __init__(self, source, *args, **kwargs):
        self.source = source
        self.frames = Queue(kwargs.pop('queue_size', 4096))

        # Call the AbstractOpus constructor, as we need properties it sets
        AbstractOpus.__init__(self, *args, **kwargs)

        # Then call the OpusEncoder constructor, which requires some properties
        #  that AbstractOpus sets up
        OpusEncoder.__init__(self, self.sampling_rate, self.channels)

        # Spawn the encoder loop
        gevent.spawn(self._encoder_loop)

    def _encoder_loop(self):
        while self.source:
            raw = self.source.read(self.frame_size)
            if len(raw) < self.frame_size:
                break

            self.frames.put(self.encode(raw, self.samples_per_frame))
            gevent.idle()
        self.source = None
        self.frames.put(None)

    def next_frame(self):
        return self.frames.get()


class DCADOpusEncoderPlayable(BasePlayable, AbstractOpus, OpusEncoder):
    def __init__(self, source, *args, **kwargs):
        self.source = source
        self.command = kwargs.pop('command', 'dcad')
        self.on_complete = kwargs.pop('on_complete', None)
        super(DCADOpusEncoderPlayable, self).__init__(*args, **kwargs)

        self._done = False
        self._proc = None

# TODO: what is this?
    @property
    def proc(self):
        if not self._proc:
            source = obj = self.source.fileobj()
            if not hasattr(obj, 'fileno'):
                source = subprocess.PIPE

            self._proc = subprocess.Popen([
                self.command,
                '--channels', str(self.channels),
                '--rate', str(self.sampling_rate),
                '--size', str(self.samples_per_frame),
                '--bitrate', '128',
                '--fec',
                '--packet-loss-percent', '30',
                '--input', 'pipe:0',
                '--output', 'pipe:1',
            ], stdin=source, stdout=subprocess.PIPE)

            def writer():
                while True:
                    data = obj.read(2048)
                    if len(data) > 0:
                        self._proc.stdin.write(data)
                    if len(data) < 2048:
                        break

            if source == subprocess.PIPE:
                gevent.spawn(writer)
        return self._proc

    def next_frame(self):
        if self._done:
            return None

        header = self.proc.stdout.read(OPUS_HEADER_SIZE)
        if len(header) < OPUS_HEADER_SIZE:
            self._done = True
            self.on_complete()
            return

        size = struct.unpack('<h', header)[0]

        data = self.proc.stdout.read(size)
        if len(data) < size:
            self._done = True
            self.on_complete()
            return

        return data


class FileProxyPlayable(BasePlayable, AbstractOpus):
    def __init__(self, other, output, *args, **kwargs):
        self.flush = kwargs.pop('flush', False)
        self.on_complete = kwargs.pop('on_complete', None)
        super(FileProxyPlayable, self).__init__(*args, **kwargs)
        self.other = other
        self.output = output

    def next_frame(self):
        frame = self.other.next_frame()

        if frame:
            self.output.write(struct.pack('<h', len(frame)))
            self.output.write(frame)

            if self.flush:
                self.output.flush()
        else:
            self.output.flush()
            self.on_complete()
            self.output.close()
        return frame


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
