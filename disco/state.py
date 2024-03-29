from collections import deque, namedtuple
from gevent.event import Event

from disco.util.config import Config
from disco.util.string import underscore
from disco.util.hashmap import HashMap, DefaultHashMap
from disco.util.emitter import Priority


class StackMessage(namedtuple('StackMessage', ['id', 'channel_id', 'author_id'])):
    """
    A message stored on a stack inside of the state object, used for tracking
    previously sent messages in channels.

    Attributes
    ---------
    id : snowflake
        The id of the message.
    channel_id : snowflake
        The id of the channel this message was sent in.
    author_id : snowflake
        The id of the author of this message.
    """


class StateConfig(Config):
    """
    A configuration object for determining how the State tracking behaves.

    Attributes
    ----------
    track_messages : bool
        Whether the state store should keep a buffer of previously sent messages.
        Message tracking allows for multiple higher-level shortcuts and can be
        highly useful when developing bots that need to delete their own messages.

        Message tracking is implemented using a deque and a namedtuple, meaning
        it should generally not have a high impact on memory, however users who
        find that they do not need and may be experiencing memory pressure can
        disable this feature entirely using this attribute.
    track_messages_size : int
        The size of the messages deque for each channel. This value can be used
        to calculate the total number of possible `StackMessage` objects kept in
        memory, simply: `total_messages_size * total_channels`. This value can
        be tweaked based on usage and to help prevent memory pressure.
    sync_guild_members : bool
        If true, guilds will be automatically synced when they are initially loaded
        or joined. Generally this setting is OK for smaller bots, however bots in over
        50 guilds will notice this operation can take a while to complete, and may want
        to batch requests using the underlying `GatewayClient.request_guild_members`
        interface.
    """
    track_messages = False
    track_messages_size = 100

    sync_guild_members = True


class State:
    """
    The State class is used to track global state based on events emitted from
    the `GatewayClient`. State tracking is a core component of the Disco client,
    providing the mechanism for most of the higher-level utility functions.

    Attributes
    ----------
    EVENTS : list(str)
        A list of all events the State object binds to.
    client : `disco.client.Client`
        The Client instance this state is attached to.
    config : `StateConfig`
        The configuration for this state instance.
    me : `User`
        The currently logged in user.
    guilds : dict(snowflake, `Guild`)
        Mapping of all known/loaded Guilds.
    channels : dict(snowflake, `Channel`)
        Weak mapping of all known/loaded Channels.
    users : dict(snowflake, `User`)
        Weak mapping of all known/loaded Users.
    voice_clients : dict(str, 'VoiceClient')
        Weak mapping of all known voice clients.
    voice_states : dict(str, `VoiceState`)
        Weak mapping of all known/active Voice States.
    messages : Optional[dict(snowflake, deque)]
        Mapping of channel ids to deques containing `StackMessage` objects.
    """
    EVENTS = [
        'Ready', 'GuildCreate', 'GuildUpdate', 'GuildDelete', 'GuildMemberAdd', 'GuildMemberUpdate',
        'GuildMemberRemove', 'GuildMembersChunk', 'GuildRoleCreate', 'GuildRoleUpdate', 'GuildRoleDelete',
        'GuildEmojisUpdate', 'GuildStickersUpdate', 'ChannelCreate', 'ChannelUpdate', 'ChannelDelete',
        'VoiceServerUpdate', 'VoiceStateUpdate', 'MessageCreate', 'PresenceUpdate', 'UserUpdate', 'ThreadCreate',
        'ThreadUpdate', 'ThreadDelete',
    ]

    def __init__(self, client, config):
        self.client = client
        self.config = config

        self.ready = Event()
        self.guilds_waiting_sync = 0

        self.me = None
        self.guilds = HashMap()
        self.channels = HashMap()
        self.commands = HashMap()
        self.dms = HashMap()
        self.emojis = HashMap()
        self.stickers = HashMap()
        self.threads = HashMap()
        self.users = HashMap()
        self.voice_clients = HashMap()
        self.voice_states = HashMap()

        # If message tracking is enabled, listen to those events
        if self.config.track_messages:
            self.messages = DefaultHashMap(lambda: deque(maxlen=self.config.track_messages_size))
            self.EVENTS += ['MessageDelete', 'MessageDeleteBulk']

        # The bound listener objects
        self.listeners = []
        self.bind()

    def unbind(self):
        """
        Unbinds all bound event listeners for this state object.
        """
        map(lambda k: k.unbind(), self.listeners)
        self.listeners = []

    def bind(self):
        """
        Binds all events for this state object, storing the listeners for later
        unbinding.
        """
        assert not len(self.listeners), 'Binding while already bound is dangerous'

        for event in self.EVENTS:
            func = 'on_' + underscore(event)
            self.listeners.append(self.client.events.on(event, getattr(self, func), priority=Priority.AFTER))

    def fill_messages(self, channel):
        for message in reversed(next(channel.messages_iter(bulk=True))):
            self.messages[channel.id].append(
                StackMessage(message.id, message.channel_id, message.author.id))

    def on_ready(self, event):
        self.me = event.user
        self.guilds_waiting_sync = len(event.guilds)

    def on_user_update(self, event):
        self.me.inplace_update(event.user)

    def on_message_create(self, event):
        if self.config.track_messages:
            self.messages[event.message.channel_id].append(
                StackMessage(event.message.id, event.message.channel_id, event.message.author.id))

        if event.message.channel_id in self.channels:
            self.channels[event.message.channel_id].last_message_id = event.message.id

        if event.message.channel_id in self.threads:
            self.threads[event.message.channel_id].last_message_id = event.message.id

        if not event.message.guild_id and event.message.channel_id not in self.dms:
            self.dms[event.message.channel_id] = event.message.channel

    def on_message_delete(self, event):
        if event.channel_id not in self.messages:
            return

        sm = next((i for i in self.messages[event.channel_id] if i.id == event.id), None)
        if not sm:
            return

        self.messages[event.channel_id].remove(sm)

    def on_message_delete_bulk(self, event):
        if event.channel_id not in self.messages:
            return

        # TODO: performance
        for sm in tuple(self.messages[event.channel_id]):
            if sm.id in event.ids:
                self.messages[event.channel_id].remove(sm)

    def on_guild_create(self, event):
        if not event.unavailable:
            self.guilds_waiting_sync -= 1
            if self.guilds_waiting_sync <= 0:
                self.ready.set()

        if event.guild.id in self.guilds:
            return

        self.guilds[event.guild.id] = event.guild
        self.channels.update(event.guild.channels)
        self.threads.update(event.guild.threads)
        self.emojis.update(event.guild.emojis)
        self.stickers.update(event.guild.stickers)

        for voice_state in event.guild.voice_states.values():
            self.voice_states[voice_state.session_id] = voice_state

        for member in event.guild.members.values():
            if member.user.id not in self.users:
                self.users[member.user.id] = member.user

        for presence in event.presences:
            if presence.user.id in self.users:
                self.users[presence.user.id].presence = presence

        # TODO: better performance on large guild sync
        if self.config.sync_guild_members:
            event.guild.request_guild_members()

    def on_guild_update(self, event):
        ignored = ['channels', 'emojis', 'members', 'stickers', 'threads', 'voice_states', 'presences']
        if not hasattr(event.guild, 'widget_enabled'):
            ignored.append('widget_enabled')
        self.guilds[event.guild.id].inplace_update(event.guild, ignored=ignored)

    # TODO: commands
    def on_guild_delete(self, event):
        if hasattr(event, 'guild'):
            if event.unavailable:
                return

        if event.id in self.guilds:
            del self.guilds[event.id]

        if event.id in self.voice_clients:
            self.voice_clients[event.id].disconnect()

        channels = tuple(self.channels.keys())
        for channel in channels:
            if self.channels[channel].guild_id == event.id:
                del self.channels[channel]

        threads = tuple(self.threads.keys())
        for thread in threads:
            if self.threads[thread].guild_id == event.id:
                del self.threads[thread]

        emojis = tuple(self.emojis.keys())
        for emoji in emojis:
            if self.emojis[emoji].guild_id == event.id:
                del self.emojis[emoji]

        stickers = tuple(self.stickers.keys())
        for sticker in stickers:
            if self.stickers[sticker].guild_id == event.id:
                del self.stickers[sticker]

        voice_states = tuple(self.voice_states.keys())
        for vstate in voice_states:
            if self.voice_states[vstate].guild_id == event.id:
                del self.voice_states[vstate]

    def on_channel_create(self, event):
        if event.channel.is_guild and event.channel.guild_id in self.guilds:
            self.guilds[event.channel.guild_id].channels[event.channel.id] = event.channel
            self.channels[event.channel.id] = event.channel

    def on_channel_update(self, event):
        if event.channel.id in self.channels:
            self.channels[event.channel.id].inplace_update(event.channel)

            if event.overwrites is not None:
                self.channels[event.channel.id].overwrites = event.overwrites
                self.channels[event.channel.id].after_load()

    def on_channel_delete(self, event):
        if event.channel.is_guild and event.channel.guild and event.channel.id in event.channel.guild.channels:
            del event.channel.guild.channels[event.channel.id]
            del self.channels[event.channel.id]

    def on_thread_create(self, event):
        if event.channel.guild_id in self.guilds:
            self.guilds[event.channel.guild_id].threads[event.channel.id] = event.channel
            self.threads[event.channel.id] = event.channel

    def on_thread_update(self, event):
        if event.channel.id in self.threads:
            self.threads[event.channel.id].inplace_update(event.channel)

            if event.overwrites is not None:
                self.threads[event.channel.id].overwrites = event.overwrites
                self.threads[event.channel.id].after_load()

    def on_thread_delete(self, event):
        if event.channel.id in self.threads:
            del event.channel.guild.threads[event.channel.id]
            del self.threads[event.channel.id]

    def on_voice_server_update(self, event):
        if event.guild_id not in self.voice_clients:
            return

        voice_client = self.voice_clients.get(event.guild_id)
        voice_client.set_endpoint(event.endpoint)
        voice_client.set_token(event.token)

    def on_voice_state_update(self, event):
        # Existing connection, we are either moving channels or disconnecting
        if event.state.session_id in self.voice_states:
            # Moving channels
            if event.state.channel_id:
                self.voice_states[event.state.session_id].inplace_update(event.state)
            # Disconnection
            else:
                if event.state.guild_id in self.guilds:
                    if event.state.session_id in self.guilds[event.state.guild_id].voice_states:
                        del self.guilds[event.state.guild_id].voice_states[event.state.session_id]
                del self.voice_states[event.state.session_id]
        # New connection
        elif event.state.channel_id:
            if event.state.guild_id in self.guilds:
                expired_voice_state = self.guilds[event.state.guild_id].voice_states.select_one(user_id=event.user_id)
                if expired_voice_state:
                    del self.guilds[event.state.guild_id].voice_states[expired_voice_state.session_id]
                self.guilds[event.state.guild_id].voice_states[event.state.session_id] = event.state
            expired_voice_state = self.voice_states.select_one(user_id=event.user_id)
            if expired_voice_state:
                del self.voice_states[expired_voice_state.session_id]
            self.voice_states[event.state.session_id] = event.state

    def on_guild_member_add(self, event):
        if event.member.user.id not in self.users:
            self.users[event.member.user.id] = event.member.user
        else:
            event.member.user = self.users[event.member.user.id]

        if event.guild_id not in self.guilds:
            return

        # Avoid adding duplicate events to member_count.
        if event.member.id not in self.guilds[event.guild_id].members:
            self.guilds[event.guild_id].member_count += 1

        self.guilds[event.guild_id].members[event.member.id] = event.member

    def on_guild_member_update(self, event):
        if event.guild_id not in self.guilds:
            return

        if event.member.id not in self.guilds[event.guild_id].members:
            return

        self.guilds[event.guild_id].members[event.member.id].inplace_update(event.member)

        if not event.user.id in self.users:
            self.users[event.user.id] = event.user

        if event.roles and event.guild_id in self.guilds:
            self.guilds[event.guild_id].members[event.user.id].roles = event.roles

        self.users[event.user.id].inplace_update(event.user)

    def on_guild_member_remove(self, event):
        if event.guild_id not in self.guilds:
            return

        if event.user.id not in self.guilds[event.guild_id].members:
            return

        self.guilds[event.guild_id].member_count -= 1
        del self.guilds[event.guild_id].members[event.user.id]

    def on_guild_members_chunk(self, event):
        if event.guild_id not in self.guilds:
            return

        guild = self.guilds[event.guild_id]
        for member in event.members:
            member.guild_id = guild.id
            guild.members[member.id] = member

            if member.id not in self.users:
                self.users[member.id] = member.user
            else:
                member.user = self.users[member.id]

        if not event.presences:
            return

        for presence in event.presences:
            # TODO: this matches the recursive, hackfix method found in on_presence_update
            user = presence.user
            user.presence = presence
            self.users[user.id].inplace_update(user)

    def on_guild_role_create(self, event):
        if event.guild_id not in self.guilds:
            return

        self.guilds[event.guild_id].roles[event.role.id] = event.role

    def on_guild_role_update(self, event):
        if event.guild_id not in self.guilds:
            return

        self.guilds[event.guild_id].roles[event.role.id].inplace_update(event.role)

    def on_guild_role_delete(self, event):
        if event.guild_id not in self.guilds:
            return

        if event.role_id not in self.guilds[event.guild_id].roles:
            return

        del self.guilds[event.guild_id].roles[event.role_id]

        # This _should_ update roles on each user when a role is removed
        for member in self.guilds[event.guild_id].members.values():
            if event.role_id in member.roles:
                member.roles.remove(event.role_id)

    def on_guild_emojis_update(self, event):
        if event.guild_id not in self.guilds:
            return

        for emoji in event.emojis:
            emoji.guild_id = event.guild_id

        self.guilds[event.guild_id].emojis = HashMap({i.id: i for i in event.emojis})

        self.emojis = {}
        for guild in self.guilds.values():
            self.emojis.update(guild.emojis)

    # TODO: default Discord stickers
    def on_guild_stickers_update(self, event):
        if event.guild_id not in self.guilds or not hasattr(event, 'stickers'):
            return

        for sticker in event.stickers:
            sticker.guild_id = event.guild_id

        self.guilds[event.guild_id].stickers = HashMap({i.id: i for i in event.stickers})

        self.stickers = {}
        for guild in self.guilds.values():
            self.stickers.update(guild.stickers)

    def on_presence_update(self, event):
        # TODO: this is recursive, we hackfix in Model
        user = event.presence.user
        user.presence = event.presence

        # if we have the user tracked locally, we can just use the presence
        #  update to update both their presence and the cached user object.
        if user.id in self.users:
            self.users[user.id].inplace_update(user)
        else:
            # Otherwise this user does not exist in our local cache, so we can
            #  use this opportunity to add them. They will quickly fall out of
            #  scope and be deleted if they aren't used below
            self.users[user.id] = user
