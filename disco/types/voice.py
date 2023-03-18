from disco.types.base import SlottedModel, text, Field, snowflake, cached_property, datetime


class VoiceState(SlottedModel):
    guild_id = Field(snowflake)
    channel_id = Field(snowflake)
    user_id = Field(snowflake)
    session_id = Field(text)
    deaf = Field(bool)
    mute = Field(bool)
    self_deaf = Field(bool)
    self_mute = Field(bool)
    self_stream = Field(bool)
    self_video = Field(bool)
    suppress = Field(bool)
    request_to_speak_timestamp = Field(datetime)

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)

    @property
    def channel(self):
        return self.client.state.channels.get(self.channel_id)

    @cached_property
    def user(self):
        return self.client.state.users.get(self.user_id)

    @property
    def member(self):
        return self.guild.get_member(self.user_id)


class VoiceRegion(SlottedModel):
    id = Field(text)
    name = Field(text)
    vip = Field(bool)
    optimal = Field(bool)
    deprecated = Field(bool)
    custom = Field(bool)

    def __str__(self):
        return self.id

    def __int__(self):
        return self.id

    def __repr__(self):
        return '<VoiceRegion name={}>'.format(self.name)
