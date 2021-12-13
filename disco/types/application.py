from disco.types.base import SlottedModel, Field, snowflake, text, enum, ListField, cached_property, DictField, str_or_int
from disco.types.channel import Channel, ChannelType
from disco.types.guild import GuildMember, Role
from disco.types.message import MessageEmbed, AllowedMentions, MessageFlagValue, Message, MessageComponent, SelectOption
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


class ApplicationCommandTypes:
    CHAT_INPUT = 1
    USER = 2
    MESSAGE = 3


class ApplicationCommandOptionChoice(SlottedModel):
    name = Field(text)
    value = Field(str_or_int)


class _ApplicationCommandOption(SlottedModel):
    type = Field(enum(ApplicationCommandOptionType))
    name = Field(text)
    description = Field(text)
    required = Field(bool)
    choices = ListField(ApplicationCommandOptionChoice)
    channel_types = ListField(ChannelType)
    min_value = Field(int)
    max_value = Field(int)
    autocomplete = Field(bool)


class ApplicationCommandOption(_ApplicationCommandOption):
    options = ListField(_ApplicationCommandOption)


class ApplicationCommandInteractionDataResolved(SlottedModel):
    users = DictField(snowflake, User)
    members = DictField(snowflake, GuildMember)
    roles = DictField(snowflake, Role)
    channels = DictField(snowflake, Channel)


class _ApplicationCommandInteractionDataOption(SlottedModel):
    name = Field(text)
    type = Field(int)
    # value = Field(enum(ApplicationCommandOptionType))
    value = Field(str_or_int)
    focused = Field(bool)


class ApplicationCommandInteractionDataOption(_ApplicationCommandInteractionDataOption):
    options = ListField(_ApplicationCommandInteractionDataOption)


class ComponentTypes:
    ACTION_ROW = 1
    BUTTON = 2


class ApplicationCommandInteractionData(SlottedModel):
    id = Field(snowflake)
    name = Field(text)
    type = Field(enum(ApplicationCommandTypes))
    resolved = Field(ApplicationCommandInteractionDataResolved)
    options = ListField(ApplicationCommandInteractionDataOption)
    custom_id = Field(text)
    component_type = Field(int)
    values = ListField(SelectOption)
    target_id = Field(snowflake)


class ApplicationCommand(SlottedModel):
    id = Field(snowflake)
    type = Field(enum(ApplicationCommandTypes))
    application_id = Field(snowflake)
    guild_id = Field(snowflake)
    name = Field(text)
    description = Field(text)
    options = ListField(ApplicationCommandOption)
    default_permission = Field(bool, default=True)
    version = Field(snowflake)


class ApplicationCommandPermissionType:
    ROLE = 1
    USER = 2


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


class Interaction(SlottedModel):
    id = Field(snowflake)
    application_id = Field(snowflake)
    type = Field(enum(InteractionType))
    data = Field(ApplicationCommandInteractionData)
    guild_id = Field(snowflake)
    channel_id = Field(snowflake)
    member = Field(GuildMember)
    user = Field(User)
    token = Field(text)
    version = Field(int)
    message = Field(Message)

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)

    @cached_property
    def channel(self):
        return self.client.state.channels.get(self.channel_id)

    def send_acknowledgement(self, type, data=None):
        return self.client.api.interactions_create(self.id, self.token, type, data)

    def edit_acknowledgement(self, data):
        return self.client.api.interactions_edit(self.id, self.token, data)

    def delete_acknowledgement(self):
        return self.client.api.interactions_delete(self.id, self.token)

    def reply(self, data):
        return self.client.api.interactions_followup_create(self.token, data)

    def edit(self, data):
        return self.client.api.interactions_followup_edit(self.token, data)

    def delete(self):
        return self.client.api.interactions_followup_delete(self.token)


class InteractionCallbackType:
    PONG = 1
    # ACKNOWLEDGE = 2
    # CHANNEL_MESSAGE = 3
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6
    UPDATE_MESSAGE = 7
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8
    # UNKNOWN = 9


class InteractionResponseFlags:
    EPHEMERAL = 1 << 6


class InteractionApplicationCommandCallbackData(SlottedModel):
    tts = Field(bool)
    content = Field(text)
    embeds = ListField(MessageEmbed)
    allowed_mentions = Field(AllowedMentions)
    flags = Field(MessageFlagValue)
    components = ListField(MessageComponent)


class InteractionResponse(SlottedModel):
    type = Field(InteractionCallbackType)
    data = Field(InteractionApplicationCommandCallbackData)
