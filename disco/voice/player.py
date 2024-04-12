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

        # Core task
        self.run_task = gevent_spawn(self.run)

        # Event triggered when playback is complete
        self.complete = GeventEvent()

        # Event emitter for metadata
        self.events = Emitter()

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
        self.paused = GeventEvent()
        self.events.emit(self.Events.PAUSE_PLAY)

    def resume(self):
        if self.paused:
            self.paused.set()
            self.paused = None
            self.events.emit(self.Events.RESUME_PLAY)

    def play(self, item):
        #  Grab the first frame before we start anything else, sometimes playables
        #  can do some lengthy async tasks here to set up the playable, and we
        #  don't want to lerp the first N frames of the playable into playing
        #  faster
        frame = item.next_frame()
        if frame is None:
            return

        start = time()
        loops = 0

        while True:
            loops += 1

            if self.paused:
                self.client.set_speaking(False)
                self.paused.wait()
                gevent_sleep(2)
                self.client.set_speaking(True)
                start = time()
                loops = 0

            if self.client.state == VoiceState.DISCONNECTED:
                return

            if self.client.state != VoiceState.CONNECTED:
                self.client.state_emitter.once(VoiceState.CONNECTED, timeout=30)

            # Send the voice frame and increment our timestamp
            self.client.send_frame(frame)
            self.client.increment_timestamp(item.samples_per_frame)

            frame = item.next_frame()
            if frame is None:
                return

            next_time = start + 0.02 * loops
            delay = max(0, 0.02 + (next_time - time()))
            gevent_sleep(delay)

    def run(self):
        self.client.set_speaking(True)

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

        self.client.set_speaking(False)
        self.disconnect()

    def set_channel(self, channel_or_id):
        if channel_or_id and isinstance(channel_or_id, Channel):
            channel_or_id = channel_or_id.id

        self.client.set_voice_state(channel_or_id)
