from disco.types.base import SlottedModel, Field, snowflake, text, enum, ListField, cached_property, DictField, str_or_int, BitsetMap, BitsetValue
from disco.types.channel import Channel, ChannelType
from disco.types.guild import GuildMember, Role
from disco.types.message import MessageEmbed, AllowedMentions, Message, MessageComponent, SelectOption, MessageAttachment
from disco.types.user import User


class ApplicationCommandOptionType:
    SUB_COMMAND = 1
    SUB_COMMAND_GROUP = 2
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8
    MENTIONABLE = 9
    NUMBER = 10
    ATTACHMENT = 11


class ApplicationCommandTypes:
    CHAT_INPUT = 1
    USER = 2
    MESSAGE = 3


class ApplicationCommandOptionChoice(SlottedModel):
    name = Field(text)
    name_localizations = DictField(str, str)
    value = Field(str_or_int)


class _ApplicationCommandOption(SlottedModel):
    type = Field(enum(ApplicationCommandOptionType))
    name = Field(text)
    name_localizations = DictField(str, str)
    description = Field(text)
    description_localizations = DictField(str, str)
    required = Field(bool)
    choices = ListField(ApplicationCommandOptionChoice)
    channel_types = ListField(ChannelType)
    min_value = Field(int)
    max_value = Field(int)
    min_length = Field(int)
    max_length = Field(int)
    autocomplete = Field(bool)


class ApplicationCommandOption(_ApplicationCommandOption):
    options = ListField(_ApplicationCommandOption)


class InteractionDataResolved(SlottedModel):
    users = DictField(snowflake, User)
    members = DictField(snowflake, GuildMember)
    roles = DictField(snowflake, Role)
    channels = DictField(snowflake, Channel)
    messages = DictField(snowflake, Message)
    attachments = DictField(snowflake, MessageAttachment)


class _InteractionDataOption(SlottedModel):
    name = Field(text)
    type = Field(int)
    value = Field(str_or_int)
    focused = Field(bool)


class InteractionDataOption(_InteractionDataOption):
    options = ListField(_InteractionDataOption)


class InteractionData(SlottedModel):
    id = Field(snowflake)
    name = Field(text)
    type = Field(enum(ApplicationCommandTypes))
    resolved = Field(InteractionDataResolved, create=False)
    options = ListField(InteractionDataOption, create=False)
    custom_id = Field(text)
    component_type = Field(int)
    values = ListField(SelectOption, create=False)
    target_id = Field(snowflake)
    guild_id = Field(snowflake)
    components = ListField(MessageComponent)


class ApplicationCommand(SlottedModel):
    id = Field(snowflake)
    type = Field(enum(ApplicationCommandTypes))
    application_id = Field(snowflake)
    guild_id = Field(snowflake)
    name = Field(text)
    name_localizations = DictField(str, str)
    description = Field(text)
    description_localizations = DictField(str, str)
    options = ListField(ApplicationCommandOption)
    default_member_permissions = Field(int)
    dm_permissions = Field(bool)
    nsfw = Field(bool)
    version = Field(snowflake)


class ApplicationCommandPermissionType:
    ROLE = 1
    USER = 2
    CHANNEL = 3


class ApplicationCommandPermissions(SlottedModel):
    id = Field(snowflake)
    type = Field(enum(ApplicationCommandPermissionType))
    permission = Field(bool)


class GuildApplicationCommandPermissions(SlottedModel):
    id = Field(snowflake)
    application_id = Field(snowflake)
    guild_id = Field(snowflake)
    permissions = ListField(ApplicationCommandPermissions)


class InteractionType:
    PING = 1
    APPLICATION_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4
    MODAL_SUBMIT = 5


class Interaction(SlottedModel):
    id = Field(snowflake)
    application_id = Field(snowflake)
    type = Field(enum(InteractionType))
    data = Field(InteractionData)
    guild_id = Field(snowflake)
    channel_id = Field(snowflake)
    member = Field(GuildMember, create=False)
    user = Field(User, create=False)
    token = Field(text)
    version = Field(int)
    message = Field(Message, create=False)
    locale = Field(str)
    guild_locale = Field(str)

    def __repr__(self):
        return '<Interaction id={} channel_id={}>'.format(self.id, self.channel_id)

    def __int__(self):
        return self.id

    @cached_property
    def channel(self):
        if self.guild_id:
            if self.channel_id in self.client.state.threads:
                return self.client.state.threads.get(self.channel_id)
            return self.client.state.channels.get(self.channel_id)
        else:
            if self.channel_id in self.client.state.dms:
                return self.client.state.dms[self.channel_id]
            return self.client.api.channels_get(self.channel_id)

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)

    def pin(self):
        return self.channel.create_pin(self)

    def unpin(self):
        return self.channel.delete_pin(self)

    def reply(self, *args, **kwargs):
        return self.client.api.interactions_create_reply(self.id, self.token, *args, **kwargs)

    def edit(self, *args, **kwargs):
        return self.client.api.interactions_edit_reply(self.client.state.me.id, self.token, *args, **kwargs)

    def delete(self):
        return self.client.api.interactions_delete_reply(self.client.state.me.id, self.token)


class InteractionCallbackType:
    PONG = 1
    # ACKNOWLEDGE = 2  # DEPRECATED
    # CHANNEL_MESSAGE = 3  # DEPRECATED
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6
    UPDATE_MESSAGE = 7
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8
    MODAL = 9
    PREMIUM_REQUIRED = 10


class InteractionResponseFlags(BitsetMap):
    EPHEMERAL = 1 << 6


class InteractionResponseFlagsValue(BitsetValue):
    map = InteractionResponseFlags


class InteractionCallbackData(SlottedModel):
    tts = Field(bool)
    content = Field(text)
    embeds = ListField(MessageEmbed)
    allowed_mentions = Field(AllowedMentions)
    flags = Field(InteractionResponseFlagsValue)
    components = ListField(MessageComponent)


class InteractionResponse(Interaction):
    type = Field(enum(InteractionCallbackType))
    data = Field(InteractionCallbackData)

    def __repr__(self):
        return '<InteractionResponse id={} channel_id={}>'.format(self.id, self.channel_id)

    def __int__(self):
        return self.id
