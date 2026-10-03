from time import time
from gevent import sleep as gevent_sleep, spawn as gevent_spawn
from gevent.event import Event as GeventEvent

from disco.types.channel import Channel
from disco.util.emitter import Emitter
from disco.util.logging import LoggingClass
from disco.voice.client import VoiceState
from disco.voice.queue import PlayableQueue


class Player(LoggingClass):
    class Events:
        START_PLAY = 'START_PLAY'
        STOP_PLAY = 'STOP_PLAY'
        PAUSE_PLAY = 'PAUSE_PLAY'
        RESUME_PLAY = 'RESUME_PLAY'
        DISCONNECT = 'DISCONNECT'

    def __init__(self, client, queue=None):
        super(Player, self).__init__()
        self.client = client  # VoiceClient
        self.client.media = self

        # Queue contains playable items
        self.queue = queue or PlayableQueue()

        # Whether we're playing music (true for lifetime)
        self.playing = True

        # Set to an event when playback is paused
        self.paused = None

        # Current playing item
        self.now_playing = None

        # Current play task
        self.play_task = None

        # Whether voice transmission is suppressed
        self.silenced = False
        self._silence_paused = False
        self._silence_started = None

        # Core task
        self.run_task = gevent_spawn(self.run)

        # Event triggered when playback is complete
        self.complete = GeventEvent()

        # Event emitter for metadata
        self.events = Emitter()

        self.client.update_media_silence()

    def client(self):
        return self.client()

    def disconnect(self):
        self.client.disconnect()
        self.events.emit(self.Events.DISCONNECT)

    def skip(self):
        self.play_task.kill()

    def pause(self):
        if self.paused:
            return

        if self.client.state == VoiceState.CONNECTED and not getattr(self.client, '_initial_silence', False):
            self.client.send_silence()
            self._silence_started = time()

        self.paused = GeventEvent()
        self.client.set_speaking(False)
        self.events.emit(self.Events.PAUSE_PLAY)

    def resume(self):
        if self.paused and not self._silence_paused:
            self._advance_silence_timestamp()
            self.paused.set()
            self.paused = None
            if not self.silenced:
                self.client.set_speaking(True)
            self.events.emit(self.Events.RESUME_PLAY)

    def set_silenced(self, silenced):
        if self.silenced == silenced:
            return

        self.silenced = silenced

        if self.now_playing and hasattr(self.now_playing, 'set_transmitting'):
            self.now_playing.set_transmitting(not silenced)

        if silenced:
            if self.now_playing and not getattr(self.now_playing, 'streaming', False) and not self.paused:
                self._silence_paused = True
                self.pause()
            elif self.now_playing:
                if self.client.state == VoiceState.CONNECTED and not getattr(self.client, '_initial_silence', False):
                    self.client.send_silence()
                self._silence_started = time()
                self.client.set_speaking(False)
            else:
                self.client.set_speaking(False)
        elif self._silence_paused:
            self._silence_paused = False
            self._advance_silence_timestamp()
            self.resume()
        else:
            self._advance_silence_timestamp()
            self.client.set_speaking(True)

    def _advance_silence_timestamp(self):
        if self._silence_started is None:
            return

        if self.now_playing:
            samples_per_frame = getattr(self.now_playing, 'samples_per_frame', 960)
            silence_samples = int((time() - self._silence_started) * 48000)
            silence_samples -= silence_samples % samples_per_frame
            if silence_samples > 0:
                self.client.increment_timestamp(silence_samples)

        self._silence_started = None

    def play(self, item):
        streaming = getattr(item, 'streaming', False)

        if hasattr(item, 'set_transmitting'):
            item.set_transmitting(not self.silenced)

        if self.silenced and not streaming:
            self._silence_paused = True
            self.pause()

        if self.paused:
            self.client.set_speaking(False)
            self.paused.wait()
            if self.client.state == VoiceState.DISCONNECTED:
                return

        if self.client.state == VoiceState.DISCONNECTED:
            return

        if self.client.state != VoiceState.CONNECTED:
            self.client.state_emitter.once(VoiceState.CONNECTED, timeout=30)

        if self.client.state == VoiceState.DISCONNECTED:
            return

        if not self.silenced:
            self.client.set_speaking(True)

        frame = None
        start = time()
        loops = 0

        while True:
            if self.paused:
                self.client.set_speaking(False)
                self.paused.wait()
                if self.client.state == VoiceState.DISCONNECTED:
                    return
                frame = None
                start = time()
                loops = 0
                continue

            if self.client.state == VoiceState.DISCONNECTED:
                return

            if self.client.state != VoiceState.CONNECTED:
                self.client.state_emitter.once(VoiceState.CONNECTED, timeout=30)
                if self.client.state == VoiceState.DISCONNECTED:
                    return

            if self.silenced:
                frame = None
                start = time()
                loops = 0
                gevent_sleep(0.02)
                continue

            if frame is None:
                frame = item.next_frame()
                if frame is None:
                    return

            # Send the voice frame and increment our timestamp
            self.client.send_frame(frame)
            self.client.increment_timestamp(item.samples_per_frame)
            frame = None
            loops += 1

            next_time = start + 0.02 * loops
            gevent_sleep(max(0, next_time - time()))

    def run(self):
        self.client.set_speaking(False)

        while self.playing:
            self.now_playing = self.queue.get()

            self.events.emit(self.Events.START_PLAY, self)
            self.play_task = gevent_spawn(self.play, self.now_playing)
            self.play_task.join()
            self.events.emit(self.Events.STOP_PLAY, self)

            if self.client.state == VoiceState.DISCONNECTED:
                self.playing = False
                self.complete.set()
                return

        if self.client.state == VoiceState.CONNECTED:
            self.client.send_silence()

        self.client.set_speaking(False)
        self.disconnect()

    def set_channel(self, channel_or_id):
        if channel_or_id and isinstance(channel_or_id, Channel):
            channel_or_id = channel_or_id.id

        self.client.set_voice_state(channel_or_id)
