from disco.types.base import SlottedModel, Field, snowflake, text, enum, ListField, cached_property, DictField
from disco.types.guild import GuildMember
from disco.types.message import MessageEmbed, AllowedMentions


class ApplicationCommandOptionType(object):
    SUB_COMMAND = 1
    SUB_COMMAND_GROUP = 2
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8


class ApplicationCommandOptionChoice(SlottedModel):
    name = Field(text)
    value = Field(text or int)


class ApplicationCommandOption(SlottedModel):
    type = Field(int)
    name = Field(text)
    description = Field(text)
    default = Field(bool)
    required = Field(bool)
    choices = ListField(ApplicationCommandOptionChoice)


class ApplicationCommandInteractionDataOption(SlottedModel):
    name = Field(text)
    value = Field(enum(ApplicationCommandOptionType))


class ApplicationCommandInteractionData(SlottedModel):
    id = Field(snowflake)
    name = Field(text)
    options = ListField(ApplicationCommandInteractionDataOption)


class ApplicationCommand(SlottedModel):
    id = Field(snowflake)
    application_id = Field(snowflake)
    name = Field(text)
    description = Field(text)
    options = ListField(ApplicationCommandOption)


class InteractionType(object):
    PING = 1
    APPLICATION_COMMAND = 2


class Interaction(SlottedModel):
    id = Field(snowflake)
    type = Field(enum(InteractionType))
    data = Field(DictField)
    guild_id = Field(snowflake)
    channel_id = Field(snowflake)
    member = Field(GuildMember)
    token = Field(text)


class InteractionResponseType(object):
    PONG = 1
    ACKNOWLEDGE = 2
    CHANNEL_MESSAGE = 3
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    ACK_WITH_SOURCE = 5


class InteractionApplicationCommandCallbackData(SlottedModel):
    tts = Field(bool)
    content = Field(text)
    embeds = ListField(MessageEmbed)
    allowed_mentions = Field(AllowedMentions)
    flags = Field(int)


class InteractionResponse(SlottedModel):
    type = Field(InteractionResponseType)
    data = Field(InteractionApplicationCommandCallbackData)
