try:
    from regex import sub as re_sub
except ImportError:
    from re import sub as re_sub
from functools import partial as functools_partial
from unicodedata import normalize as unicodedata_normalize

from disco.types.base import (
    BitsetMap, BitsetValue, SlottedModel, Field, ListField, AutoDictField,
    snowflake, text, datetime, enum, cached_property,
)
from disco.types.channel import Channel, ChannelMention, ChannelType, Thread
from disco.types.guild import GuildMember
from disco.types.oauth import Application
from disco.types.reactions import Emoji, MessageReaction, StickerItem
from disco.types.user import User
from disco.util.paginator import Paginator
from disco.util.snowflake import to_snowflake


class MessageType:
    DEFAULT = 0
    RECIPIENT_ADD = 1
    RECIPIENT_REMOVE = 2
    CALL = 3
    CHANNEL_NAME_CHANGE = 4
    CHANNEL_ICON_CHANGE = 5
    PINS_ADD = 6
    GUILD_MEMBER_JOIN = 7
    USER_PREMIUM_GUILD_SUBSCRIPTION = 8
    USER_PREMIUM_GUILD_SUBSCRIPTION_TIER_1 = 9
    USER_PREMIUM_GUILD_SUBSCRIPTION_TIER_2 = 10
    USER_PREMIUM_GUILD_SUBSCRIPTION_TIER_3 = 11
    CHANNEL_FOLLOW_ADD = 12
    GUILD_STREAM = 13
    GUILD_DISCOVERY_DISQUALIFIED = 14
    GUILD_DISCOVERY_REQUALIFIED = 15
    GUILD_DISCOVERY_GRACE_PERIOD_INITIAL_WARNING = 16
    GUILD_DISCOVERY_GRACE_PERIOD_FINAL_WARNING = 17
    THREAD_CREATED = 18
    INLINE_REPLY = 19
    APPLICATION_COMMAND = 20
    THREAD_STARTER_MESSAGE = 21
    GUILD_INVITE_REMINDER = 22
    CONTEXT_MENU_COMMAND = 23
    AUTO_MODERATION_ACTION = 24
    ROLE_SUBSCRIPTION_PURCHASE = 25
    INTERACTION_PREMIUM_UPSELL = 26
    STAGE_START = 27
    STAGE_END = 28
    STAGE_SPEAKER = 29
    STAGE_RAISE_HAND = 30
    STAGE_TOPIC = 31
    GUILD_APPLICATION_PREMIUM_SUBSCRIPTION = 32
    GUILD_INCIDENT_ALERT_MODE_ENABLED = 36
    GUILD_INCIDENT_ALERT_MODE_DISABLED = 37
    GUILD_INCIDENT_REPORT_RAID = 38
    GUILD_INCIDENT_REPORT_FALSE_ALARM = 39


class MessageActivityType:
    JOIN = 1
    SPECTATE = 2
    LISTEN = 3
    JOIN_REQUEST = 5


class MessageActivity(SlottedModel):
    """
    The activity of a Rich Presence-related chat embed.

    Attributes
    ----------
    type : `MessageActivityType`
        The type of message activity.
    party_id : str
        The party id from a Rich Presence event.
    """
    type = Field(enum(MessageActivityType))
    party_id = Field(text)


class MessageFlags(BitsetMap):
    CROSSPOSTED = 1 << 0
    IS_CROSSPOST = 1 << 1
    SUPPRESS_EMBEDS = 1 << 2
    SOURCE_MESSAGE_DELETED = 1 << 3
    URGENT = 1 << 4
    HAS_THREAD = 1 << 5
    EPHEMERAL = 1 << 6
    LOADING = 1 << 7
    FAILED_TO_MENTION_SOME_ROLES_IN_THREAD = 1 << 8
    # UNKNOWN = 1 << 9
    SHOULD_SHOW_LINK_NOT_DISCORD_WARNING = 1 << 10


class MessageFlagValue(BitsetValue):
    map = MessageFlags


class MessageReference(SlottedModel):
    message_id = Field(snowflake)
    channel_id = Field(snowflake)
    guild_id = Field(snowflake)
    fail_if_not_exists = Field(bool)


class MessageEmbedType:
    rich = 'rich'
    image = 'image'
    video = 'video'
    gifv = 'gifv'
    article = 'article'
    link = 'link'


class MessageEmbedThumbnail(SlottedModel):
    """
    A thumbnail for the `MessageEmbed`.

    Attributes
    ----------
    url : str
        The thumbnail URL.
    proxy_url : str
        A proxy URL for the thumbnail, set by Discord.
    width : int
        The width of the thumbnail, set by Discord.
    height : int
        The height of the thumbnail, set by Discord.
    """
    url = Field(text)
    proxy_url = Field(text)
    width = Field(int)
    height = Field(int)


class MessageEmbedVideo(SlottedModel):
    """
    A video for the `MessageEmbed`.

    Attributes
    ----------
    url : str
        The URL for the video.
    width : int
        The width of the video, set by Discord.
    height : int
        The height of the video, set by Discord.
    """
    url = Field(text)
    proxy_url = Field(text)
    height = Field(int)
    width = Field(int)


class MessageEmbedImage(SlottedModel):
    """
    An image for the `MessageEmbed`.

    Attributes
    ----------
    url : str
        The URL for the image.
    proxy_url : str
        A proxy URL for the image, set by Discord.
    width : int
        The width of the image, set by Discord.
    height : int
        The height of the image, set by Discord.
    """
    url = Field(text)
    proxy_url = Field(text)
    width = Field(int)
    height = Field(int)


class MessageEmbedProvider(SlottedModel):
    name = Field(text)
    url = Field(text)


class MessageEmbedAuthor(SlottedModel):
    """
    An author for the `MessageEmbed`.

    Attributes
    ----------
    name : str
        The name of the author.
    url : str
        A URL for the author.
    icon_url : str
        A URL to an icon for the author.
    proxy_icon_url : str
        A proxy URL for the authors icon, set by Discord.
    """
    name = Field(text)
    url = Field(text)
    icon_url = Field(text)
    proxy_icon_url = Field(text)


class MessageEmbedFooter(SlottedModel):
    """
    A footer for the `MessageEmbed`.

    Attributes
    ----------
    text : str
        The contents of the footer.
    icon_url : str
        The URL for the footer icon.
    proxy_icon_url : str
        A proxy URL for the footer icon, set by Discord.
    """
    text = Field(text)
    icon_url = Field(text)
    proxy_icon_url = Field(text)


class MessageEmbedField(SlottedModel):
    """
    A field for the `MessageEmbed`.

    Attributes
    ----------
    name : str
        The name of the field.
    value : str
        The value of the field.
    inline : bool
        Whether the field renders inline or by itself.
    """
    name = Field(text)
    value = Field(text)
    inline = Field(bool)


class MessageEmbed(SlottedModel):
    """
    Message embed object.

    Attributes
    ----------
    title : str
        Title of the embed.
    type : str
        Type of the embed.
    description : str
        Description of the embed.
    url : str
        URL of the embed.
    timestamp : datetime
        The timestamp for the embed.
    color : int
        The color of the embed.
    footer : `MessageEmbedFooter`
        The footer of the embed.
    image : `MessageEmbedImage`
        The image of the embed.
    thumbnail : `MessageEmbedThumbnail`
        The thumbnail of the embed.
    video : `MessageEmbedVideo`
        The video of the embed.
    provider : `MessageEmbedProvider`
        The provider of the embed.
    author : `MessageEmbedAuthor`
        The author of the embed.
    fields : list[`MessageEmbedField`]
        The fields of the embed.
    """
    title = Field(text)
    type = Field(text)
    description = Field(text)
    url = Field(text)
    timestamp = Field(datetime)
    color = Field(int)
    footer = Field(MessageEmbedFooter)
    image = Field(MessageEmbedImage)
    thumbnail = Field(MessageEmbedThumbnail)
    video = Field(MessageEmbedVideo)
    provider = Field(MessageEmbedProvider)
    author = Field(MessageEmbedAuthor)
    fields = ListField(MessageEmbedField)

    def set_footer(self, *args, **kwargs):
        """
        Sets the footer of the embed, see `MessageEmbedFooter`.
        """
        self.footer = MessageEmbedFooter(*args, **kwargs)

    def set_image(self, *args, **kwargs):
        """
        Sets the image of the embed, see `MessageEmbedImage`.
        """
        self.image = MessageEmbedImage(*args, **kwargs)

    def set_thumbnail(self, *args, **kwargs):
        """
        Sets the thumbnail of the embed, see `MessageEmbedThumbnail`.
        """
        self.thumbnail = MessageEmbedThumbnail(*args, **kwargs)

    def set_video(self, *args, **kwargs):
        """
        Sets the video of the embed, see `MessageEmbedVideo`.
        """
        self.video = MessageEmbedVideo(*args, **kwargs)

    def set_author(self, *args, **kwargs):
        """
        Sets the author of the embed, see `MessageEmbedAuthor`.
        """
        self.author = MessageEmbedAuthor(*args, **kwargs)

    def add_field(self, *args, **kwargs):
        """
        Adds a new field to the embed, see `MessageEmbedField`.
        """
        self.fields.append(MessageEmbedField(*args, **kwargs))


class MessageAttachmentFlags(BitsetMap):
    IS_REMIX = 1 << 2


class MessageAttachmentFlagsValue(BitsetValue):
    map = MessageAttachmentFlags


class MessageAttachment(SlottedModel):
    """
    Message attachment object.

    Attributes
    ----------
    id : snowflake
        The id of this attachment.
    filename : str
        The filename of this attachment.
    url : str
        The URL of this attachment.
    proxy_url : str
        The URL to proxy through when downloading the attachment.
    size : int
        Size of the attachment.
    height : int
        Height of the attachment.
    width : int
        Width of the attachment.
    """
    id = Field(snowflake)
    filename = Field(text)
    description = Field(text)
    content_type = Field(text)
    size = Field(int)
    url = Field(text)
    proxy_url = Field(text)
    height = Field(int)
    width = Field(int)
    ephemeral = Field(bool)
    duration_sec = Field(float)
    waveform = Field(text)
    flags = Field(MessageAttachmentFlagsValue)


class AllowedMentionsTypes:
    ROLE = 'roles'
    USER = 'users'
    EVERYONE = 'everyone'


class AllowedMentions(SlottedModel):
    parse = ListField(AllowedMentionsTypes)
    roles = ListField(snowflake)
    users = ListField(snowflake)
    replied_user = Field(bool)


class ComponentTypes:
    ACTION_ROW = 1
    BUTTON = 2
    STRING_SELECT = 3
    TEXT_INPUT = 4
    USER_SELECT = 5
    ROLE_SELECT = 6
    MENTIONABLE_SELECT = 7
    CHANNEL_SELECT = 8


class ButtonStyles:
    PRIMARY = 1
    SECONDARY = 2
    SUCCESS = 3
    DANGER = 4
    LINK = 5


class TextInputStyles:
    SHORT = 1
    PARAGRAPH = 2


class SelectDefaultValue(SlottedModel):
    id = Field(snowflake)
    type = Field(text)


class SelectOption(SlottedModel):
    label = Field(text)
    value = Field(text)
    description = Field(text)
    emoji = Field(Emoji)
    default = Field(bool)


class _MessageComponent(SlottedModel):
    type = Field(enum(ComponentTypes))
    custom_id = Field(text)
    disabled = Field(bool)
    style = Field(int)
    label = Field(text)
    emoji = Field(Emoji, create=False)
    url = Field(text)
    options = ListField(SelectOption)
    placeholder = Field(text)
    min_values = Field(int)
    max_values = Field(int)
    min_length = Field(int)
    max_length = Field(int)
    required = Field(bool)
    value = Field(text)
    channel_types = ListField(enum(ChannelType))
    default_values = ListField(SelectDefaultValue)


class MessageComponent(_MessageComponent):
    components = ListField(_MessageComponent)


class ActionRow(SlottedModel):
    type = Field(int, default=1)
    components = ListField(MessageComponent)

    def add_component(self, *args, **kwargs):
        if len(args) == 1:
            return self.components.append(*args)
        else:
            return self.components.append(MessageComponent(*args, **kwargs))


class MessageModal(SlottedModel):
    title = Field(text)
    custom_id = Field(text)
    components = ListField(ActionRow)

    def add_component(self, *args, **kwargs):
        if len(args) == 1:
            return self.components.append(*args)
        else:
            return self.components.append(ActionRow(*args, **kwargs))


# TODO: remove after circular import fix
class _InteractionType:
    PING = 1
    APPLICATION_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4
    MODAL_SUBMIT = 5


class MessageInteraction(SlottedModel):
    id = Field(snowflake)
    type = Field(enum(_InteractionType))
    name = Field(text)
    user = Field(User)
    member = Field(GuildMember)


class MessagePollTypes:
    DEFAULT = 1


class MessagePollMedia(SlottedModel):
    text = Field(text)
    emoji = Field(Emoji)


class MessagePollAnswer(SlottedModel):
    answer_id = Field(int)
    poll_media = Field(MessagePollMedia)


class MessagePollResultCounts(SlottedModel):
    count = Field(int)
    id = Field(int)
    me_voted = Field(bool)


class MessagePollResults(SlottedModel):
    answer_counts = ListField(MessagePollResultCounts)
    is_finalized = Field(bool)


class MessagePoll(SlottedModel):
    allow_multiselect = Field(bool)
    answers = ListField(text)
    expiry = Field(datetime)
    layout_type = Field(enum(MessagePollTypes))
    question = Field(MessagePollMedia)
    results = Field(MessagePollResults)


class _Message(SlottedModel):
    """
    Represents a Message created within a Channel on Discord.

    Attributes
    ----------
    id : snowflake
        The ID of this message.
    channel_id : snowflake
        The channel ID this message was sent in.
    type : `MessageType`
        Type of the message.
    author : :class:`disco.types.user.User`
        The author of this message.
    content : str
        The unicode contents of this message.
    nonce : str
        The nonce of this message.
    timestamp : datetime
        When this message was created.
    edited_timestamp : datetime?
        When this message was last edited.
    tts : bool
        Whether this is a TTS (text-to-speech) message.
    mention_everyone : bool
        Whether this message has an @everyone which mentions everyone.
    pinned : bool
        Whether this message is pinned in the channel.
    mentions : dict[snowflake, `User`]
        Users mentioned within this message.
    mention_roles : list[snowflake]
        IDs for roles mentioned within this message.
    embeds : list[`MessageEmbed`]
        Embeds for this message.
    mention_channels : list[`ChannelMention`]
        The channels mentioned in this message if it is cross-posted.
    attachments : dict[`MessageAttachment`]
        Attachments for this message.
    reactions : list[`MessageReaction`]
        Reactions for this message.
    activity : `MessageActivity`
        The activity of a Rich Presence-related chat embed.
    application : `MessageApplication`
        The application of a Rich Presence-related chat embed.
    message_reference: `MessageReference`
        The reference of a cross-posted message.
    flags: `MessageFlagValue`
        The flags attached to a message.
    """
    id = Field(snowflake)
    channel_id = Field(snowflake)
    guild_id = Field(snowflake)
    author = Field(User)
    member = Field(GuildMember, create=False)
    content = Field(text)
    timestamp = Field(datetime)
    edited_timestamp = Field(datetime)
    tts = Field(bool)
    mention_everyone = Field(bool)
    mentions = AutoDictField(User, 'id', create=False)
    mention_roles = ListField(snowflake)
    mention_channels = ListField(ChannelMention)
    attachments = AutoDictField(MessageAttachment, 'id')
    embeds = ListField(MessageEmbed)
    reactions = ListField(MessageReaction)
    nonce = Field(text)
    pinned = Field(bool)
    webhook_id = Field(snowflake)
    type = Field(enum(MessageType))
    activity = Field(MessageActivity, create=False)
    application = Field(Application, create=False)
    application_id = Field(snowflake)
    message_reference = Field(MessageReference, create=False)
    flags = Field(MessageFlagValue)
    interaction = Field(MessageInteraction, create=False)
    # _thread = Field(Thread, alias='thread', create=False)  # fix this
    components = ListField(MessageComponent)
    sticker_items = ListField(StickerItem)
    poll = Field(MessagePoll, create=False)

    def __repr__(self):
        return '<Message id={} channel_id={}>'.format(self.id, self.channel_id)

    def __int__(self):
        return self.id

    @cached_property
    def channel(self):
        """
        Returns
        -------
        `Channel`
            The channel this message was created in.
        """
        if self.guild_id:
            if self.channel_id in self.client.state.threads:
                return self.client.state.threads.get(self.channel_id)
            elif self.channel_id in self.client.state.channels:
                return self.client.state.channels.get(self.channel_id)
        elif self.channel_id in self.client.state.dms:
            return self.client.state.dms[self.channel_id]
        return self.client.api.channels_get(self.channel_id)

    @cached_property
    def thread(self):
        """
        Returns
        -------
        `Thread`
            The thread this message was created in.
        """
        if self.channel_id in self.client.state.threads:
            return self.client.state.threads.get(self.channel_id)

    @cached_property
    def guild(self):
        """
        Returns
        -------
        `Guild`
            The guild (if applicable) this message was created in.
        """
        if self.channel.is_dm:
            return
        if self.guild_id:
            return self.client.state.guilds.get(self.guild_id)
        elif self.channel and self.channel.guild:
            return self.channel.guild

    def pin(self):
        """
        Pins the message to the channel it was created in.
        """
        self.channel.create_pin(self)

    def unpin(self):
        """
        Unpins the message from the channel it was created in.
        """
        self.channel.delete_pin(self)

    def reply(self, *args, **kwargs):
        """
        Reply to this message (see `Channel.send_message`).

        Returns
        -------
        `Message`
            The created message object.
        """
        return self.channel.send_message(*args, **kwargs)

    def edit(self, *args, **kwargs):
        """
        Edit this message.

        Parameters
        ----------
        content : str
            The new edited contents of the message.

        Returns
        -------
        `Message`
            The edited message object.
        """
        return self.client.api.channels_messages_modify(self.channel_id, self.id, *args, **kwargs)

    def delete(self):
        """
        Delete this message.

        Returns
        -------
        `Message`
            The deleted message object.
        """
        return self.client.api.channels_messages_delete(self.channel_id, self.id)

    def set_embeds_suppressed(self, state):
        """
        Toggle this message's embed suppression.

        Parameters
        ----------
        `state`
            Whether this message's embeds should be suppressed.
        """
        flags = int(self.flags or 0)

        if state:
            flags |= MessageFlags.SUPPRESS_EMBEDS
        else:
            flags &= ~MessageFlags.SUPPRESS_EMBEDS

        self.edit(flags=flags)

    def get_reactors(self, emoji, *args, **kwargs):
        """
        Returns an iterator which paginates the reactors for the given emoji.

        Returns
        -------
        `Paginator`(`User`)
            An iterator which handles pagination of reactors.
        """
        if isinstance(emoji, Emoji):
            emoji = emoji.to_string()

        return Paginator(
            self.client.api.channels_messages_reactions_get,
            'after',
            self.channel_id,
            self.id,
            emoji,
            *args,
            **kwargs)

    def add_reaction(self, emoji):
        """
        Adds a reaction to the message.

        Parameters
        ----------
        emoji : `Emoji`|str
            An emoji or string representing an emoji
        """
        if isinstance(emoji, Emoji):
            emoji = emoji.to_string()

        self.client.api.channels_messages_reactions_create(self.channel_id, self.id, emoji)

    def delete_reaction(self, emoji, user=None):
        """
        Deletes a reaction from the message.
        """
        if isinstance(emoji, Emoji):
            emoji = emoji.to_string()

        if user:
            user = to_snowflake(user)

        self.client.api.channels_messages_reactions_delete(self.channel_id, self.id, emoji, user)

    def delete_single_reaction(self, emoji):
        """
        Deletes all reactions of a single emoji from a message.
        Parameters
        ----------
        emoji : `Emoji`|str
            An emoji or string representing an emoji
        """
        if isinstance(emoji, Emoji):
            emoji = emoji.to_string()

        self.client.api.channels_messages_reactions_delete_emoji(self.channel_id, self.id, emoji)

    def delete_all_reactions(self):
        """
        Deletes all the reactions from a message.
        """
        self.client.api.channels_messages_reactions_delete_all(self.channel_id, self.id)

    def is_mentioned(self, entity):
        """
        Returns
        -------
        bool
            Whether the given entity was mentioned.
        """
        entity = to_snowflake(entity)
        return entity in self.mentions or entity in self.mention_roles

    @cached_property
    def without_mentions(self, valid_only=False):
        """
        Returns
        -------
        str
            the message contents with all mentions removed.
        """
        return self.replace_mentions(
            lambda u: '',
            lambda r: '',
            lambda c: '',
            nonexistant=not valid_only)

    @cached_property
    def with_proper_mentions(self):
        """
        Returns
        -------
        str
            The message with mentions replaced w/ their proper form.
        """
        def replace_user(u):
            return '@' + str(u)

        def replace_role(r):
            return '@' + str(r)

        def replace_channel(c):
            return str(c)

        return self.replace_mentions(replace_user, replace_role, replace_channel)

    def replace_mentions(self, user_replace=None, role_replace=None, channel_replace=None, nonexistant=False):
        """
        Replaces user and role mentions with the result of a given lambda/function.

        Parameters
        ----------
        user_replace : function
            A function taking a single argument, the user object mentioned, and
            returning a valid string.
        role_replace : function
            A function taking a single argument, the role ID mentioned, and
            returning a valid string.

        Returns
        -------
        str
            The message contents with all valid mentions replaced.
        """
        def replace(getter, func, match):
            oid = int(match.group(2))
            obj = getter(oid)

            if obj or nonexistant:
                return func(obj or oid) or match.group(0)

            return match.group(0)

        content = self.content

        if user_replace:
            replace_user = functools_partial(replace, self.mentions.get, user_replace)
            content = re_sub('(<@!?([0-9]+)>)', replace_user, content)

        if role_replace:
            replace_role = functools_partial(replace, lambda v: (self.guild and self.guild.roles.get(v)), role_replace)
            content = re_sub('(<@&([0-9]+)>)', replace_role, content)

        if channel_replace:
            replace_channel = functools_partial(replace, self.client.state.channels.get, channel_replace)
            content = re_sub('(<#([0-9]+)>)', replace_channel, content)

        return content


class Message(_Message):
    referenced_message = Field(_Message, create=False)


class MessageTable:
    def __init__(self, sep=' | ', codeblock=True, header_break=True, language=None):
        self.header = []
        self.entries = []
        self.size_index = {}
        self.sep = sep
        self.codeblock = codeblock
        self.header_break = header_break
        self.language = language

    def recalculate_size_index(self, cols):
        for idx, col in enumerate(cols):
            size = len(unicodedata_normalize('NFC', col))
            if idx not in self.size_index or size > self.size_index[idx]:
                self.size_index[idx] = size

    def set_header(self, *args):
        args = list(map(str, args))
        self.header = args
        self.recalculate_size_index(args)

    def add(self, *args):
        args = list(map(str, args))
        self.entries.append(args)
        self.recalculate_size_index(args)

    def compile_one(self, cols):
        data = self.sep.lstrip()

        for idx, col in enumerate(cols):
            padding = ' ' * (self.size_index[idx] - len(col))
            data += col + padding + self.sep

        return data.rstrip()

    def compile(self):
        data = []
        if self.header:
            data = [self.compile_one(self.header)]

        if self.header and self.header_break:
            data.append('-' * (sum(self.size_index.values()) + (len(self.header) * len(self.sep)) + 1))

        for row in self.entries:
            data.append(self.compile_one(row))

        if self.codeblock:
            return '```{}'.format(self.language if self.language else '') + '\n'.join(data) + '```'

        return '\n'.join(data)
