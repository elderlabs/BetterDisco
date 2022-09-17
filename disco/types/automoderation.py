from disco.types.base import SlottedModel, text, Field, snowflake, ListField, enum, cached_property


class KeywordPresetTypes(object):
    PROFANITY = 1
    SEXUAL_CONTENT = 2
    SLURS = 3


class EventType(object):
    MESSAGE_SEND = 1


class TriggerTypes(object):
    KEYWORD = 1
    SPAM = 3
    KEYWORD_PRESET = 4
    MENTION_SPAM = 5


class AutoModerationActionType(object):
    BLOCK_MESSAGE = 1
    SEND_ALERT_MESSAGE = 2
    TIMEOUT = 3


class TriggerMetaData(SlottedModel):
    keyword_filter = ListField(text)
    presets = ListField(enum(KeywordPresetTypes))
    allow_list = ListField(text)
    mention_total_limit = Field(int)


class AutoModerationActionMetaData(SlottedModel):
    channel_id = Field(snowflake)
    duration_seconds = Field(int)

    @property
    def channel(self):
        if self.channel_id:
            return self.client.state.channels.get(self.channel_id)
        else:
            return None


class AutoModerationAction(SlottedModel):
    type = Field(enum(AutoModerationActionType))
    metadata = Field(AutoModerationActionMetaData)


class AutoModerationRule(SlottedModel):
    id = Field(snowflake)
    guild_id = Field(snowflake)
    name = Field(text)
    creator_id = Field(snowflake)
    event_type = Field(enum(EventType))
    trigger_type = Field(enum(TriggerTypes))
    trigger_metadata = Field(TriggerMetaData)
    actions = ListField(AutoModerationAction)
    enabled = Field(bool)
    exempt_roles = ListField(snowflake)
    exempt_channels = ListField(snowflake)

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)

    @cached_property
    def creator(self):
        return self.client.state.users.get(self.creator_id)

    @property
    def creator_member(self):
        return self.guild.get_member(self.creator_id)
