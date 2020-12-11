from datetime import datetime

from disco.types.base import (
    SlottedModel, Field, snowflake, text, with_equality, with_hash, enum, ListField,
    cached_property, DictField,
)

from disco.types.guild import GuildMember

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
    name = Field(str)
    value = Field(str) # Value can either be a string or an int.


class ApplicationCommandOption(SlottedModel):
    type = Field(int)
    name = Field(str)
    description = Field(str)
    default = Field(bool, default=False)
    required = Field(bool, default=False)
    choices = ListField(ApplicationCommandOptionChoice, default=[])
    options = ListField(ApplicationCommandOption, default=[])


class ApplicationCommand(SlottedModel):
    id = Field(snowflake)
    application_id = Field(snowflake)
    name = Field(str)
    description = Field(str)
    options = ListField(ApplicationCommandOption, default=[])


class InteractionType(object):
    PING = 1
    APPLICATION_COMMAND = 2


class Interaction(SlottedModel):
    id = Field(snowflake)
    type = Field(enum(InteractionType))
    data = Field(DictField)
    channel_id = Field(snowflake)
    member = Field(GuildMember)
    token = Field(str)

    @cached_property
    def channel(self):
        """
        Returns
        -------
        `Channel`
            The channel this interaction was created in.
        """
        return self.client.state.channels.get(self.channel_id)