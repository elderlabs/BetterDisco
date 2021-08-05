from disco.types.base import SlottedModel, Field, snowflake, text, enum, ListField, cached_property, DictField
from disco.types.channel import Channel
from disco.types.guild import GuildMember, Role
from disco.types.message import MessageEmbed, AllowedMentions, MessageFlagValue, Message, MessageComponent
from disco.types.user import User


class ApplicationCommandOptionType(object):
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


class ApplicationCommandOptionChoice(SlottedModel):
    name = Field(str)
    value = Field(text)


class _ApplicationCommandOption(SlottedModel):
    type = Field(enum(ApplicationCommandOptionType))
    name = Field(str)
    description = Field(str)
    # default = Field(bool)
    required = Field(bool)
    choices = ListField(ApplicationCommandOptionChoice)


class ApplicationCommandOption(_ApplicationCommandOption):
    options = ListField(_ApplicationCommandOption)


class ApplicationCommandInteractionDataResolved(SlottedModel):
    users = DictField(snowflake, User)
    members = DictField(snowflake, GuildMember)
    roles = DictField(snowflake, Role)
    channels = DictField(snowflake, Channel)


class _ApplicationCommandInteractionDataOption(SlottedModel):
    name = Field(str)
    type = Field(int)
    value = Field(enum(ApplicationCommandOptionType))


class ApplicationCommandInteractionDataOption(_ApplicationCommandInteractionDataOption):
    options = ListField(_ApplicationCommandInteractionDataOption)


class ComponentTypes(object):
    ACTION_ROW = 1
    BUTTON = 2


class ApplicationCommandInteractionData(SlottedModel):
    id = Field(snowflake)
    name = Field(str)
    resolved = Field(ApplicationCommandInteractionDataResolved)
    options = ListField(ApplicationCommandInteractionDataOption)
    custom_id = Field(text)
    component_type = Field(int)


class ApplicationCommand(SlottedModel):
    id = Field(snowflake)
    application_id = Field(snowflake)
    name = Field(str)
    description = Field(str)
    options = ListField(ApplicationCommandOption)
    default_permission = Field(bool, default=True)
    guild_id = Field(snowflake)
    version = Field(snowflake)


class ApplicationCommandPermissionType(object):
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


class InteractionType(object):
    PING = 1
    APPLICATION_COMMAND = 2
    MessageComponent = 3


class Interaction(SlottedModel):
    id = Field(snowflake)
    application_id = Field(snowflake)
    type = Field(enum(InteractionType))
    data = Field(ApplicationCommandInteractionData)
    guild_id = Field(snowflake)
    channel_id = Field(snowflake)
    member = Field(GuildMember)
    user = Field(User)
    token = Field(str)
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


class InteractionCallbackType(object):
    PONG = 1
    # ACKNOWLEDGE = 2
    # CHANNEL_MESSAGE = 3
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6
    UPDATE_MESSAGE = 7


class InteractionResponseFlags(object):
    EPHEMERAL = 1 << 6


class InteractionApplicationCommandCallbackData(SlottedModel):
    tts = Field(bool)
    content = Field(str)
    embeds = ListField(MessageEmbed)
    allowed_mentions = Field(AllowedMentions)
    flags = Field(MessageFlagValue)
    components = ListField(MessageComponent)


class InteractionResponse(SlottedModel):
    type = Field(InteractionCallbackType)
    data = Field(InteractionApplicationCommandCallbackData)
