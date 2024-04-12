try:
    from regex import compile as re_compile
except ImportError:
    from re import compile as re_compile

from disco.types.base import SlottedModel, Field, snowflake, cached_property, enum, DictField, text
from disco.types.channel import Channel
from disco.types.user import User


WEBHOOK_URL_RE = re_compile(r'/api/webhooks/(\d+)/(.[^/]+)')


class WebhookTypes:
    INCOMING = 1
    CHANNEL_FOLLOWER = 2
    APPLICATION = 3


class Webhook(SlottedModel):
    id = Field(snowflake)
    type = Field(enum(WebhookTypes))
    guild_id = Field(snowflake)
    channel_id = Field(snowflake)
    user = Field(User)
    name = Field(text)
    avatar = Field(text)
    token = Field(text)
    application_id = Field(snowflake)
    source_guild = DictField(text, text)
    source_channel = Field(Channel)
    url = Field(text)

    @classmethod
    def execute_url(cls, url, **kwargs):
        from disco.api.client import APIClient

        results = WEBHOOK_URL_RE.findall(url)
        if len(results) != 1:
            return Exception('Invalid Webhook URL')

        return cls(id=results[0][0], token=results[0][1]).execute(
            client=APIClient(None),
            **kwargs
        )

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)

    @cached_property
    def channel(self):
        return self.client.state.channels.get(self.channel_id)

    def delete(self):
        if self.token:
            self.client.api.webhooks_token_delete(self.id, self.token)
        else:
            self.client.api.webhooks_delete(self.id)

    def modify(self, name, avatar):
        if self.token:
            return self.client.api.webhooks_token_modify(self.id, self.token, name, avatar)
        else:
            return self.client.api.webhooks_modify(self.id, name, avatar)

    def execute(
            self,
            content=None,
            username=None,
            avatar_url=None,
            tts=False,
            fobj=None,
            embeds=[],
            allowed_mentions=None,
            wait=False,
            thread_id=None,
            client=None):
        # TODO: support file stuff properly
        client = client or self.client.api

        return client.webhooks_token_execute(self.id, self.token, {
            'content': content,
            'username': username,
            'avatar_url': avatar_url,
            'tts': tts,
            'file': fobj,
            'embeds': [i.to_dict() for i in embeds],
            'allowed_mentions': allowed_mentions,
        }, wait, thread_id)
