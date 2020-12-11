from disco.types.base import SlottedModel, Field, snowflake, text, enum, ListField
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
    guild_id = Field(snowflake)
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
    data = Field(ApplicationCommandInteractionData)
    guild_id = Field(snowflake)
    channel_id = Field(snowflake)
    member = Field(GuildMember)
    token = Field(text)

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
