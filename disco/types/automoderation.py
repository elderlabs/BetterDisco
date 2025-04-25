from disco.types.base import SlottedModel, text, Field, snowflake, ListField, enum, cached_property


class KeywordPresetTypes:
    PROFANITY = 1
    SEXUAL_CONTENT = 2
    SLURS = 3


class AutoModerationEventType:
    MESSAGE_SEND = 1
    MESSAGE_UPDATE = 2


class AutoModerationTriggerTypes:
    KEYWORD = 1
    SPAM = 3
    KEYWORD_PRESET = 4
    MENTION_SPAM = 5
    MEMBER_PROFILE = 6


class AutoModerationActionType:
    BLOCK_MESSAGE = 1
    SEND_ALERT_MESSAGE = 2
    TIMEOUT = 3
    BLOCK_MEMBER_INTERACTION = 4


class TriggerMetaData(SlottedModel):
    keyword_filter = ListField(text)
    regex_patterns = ListField(text)
    presets = ListField(enum(KeywordPresetTypes))
    allow_list = ListField(text)
    mention_total_limit = Field(int)
    mention_raid_protection_enabled = Field(bool)


class AutoModerationActionMetaData(SlottedModel):
    channel_id = Field(snowflake)
    duration_seconds = Field(int)
    custom_message = Field(text)

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
    event_type = Field(enum(AutoModerationEventType))
    trigger_type = Field(enum(AutoModerationTriggerTypes))
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
