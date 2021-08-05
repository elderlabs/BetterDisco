from disco.types.user import User
from disco.types.base import SlottedModel, text, Field, snowflake, enum, datetime, ListField
from disco.types.oauth import Application


class IntegrationAccount(SlottedModel):
    id = Field(text)
    name = Field(str)


class IntegrationExpireBehaviors(object):
    REMOVAL_ROLE = 0
    KICK = 1


class IntegrationApplication(SlottedModel):
    id = Field(snowflake)
    name = Field(str)
    icon = Field(str)
    description = Field(str)
    summary = Field(str)
    bot = Field(User)


class Integration(SlottedModel):
    id = Field(snowflake)
    name = Field(str)
    type = Field(text)
    enabled = Field(bool)
    syncing = Field(bool)
    role_id = Field(snowflake)
    enable_emoticons = Field(bool)
    expire_behavior = Field(enum(IntegrationExpireBehaviors))
    expire_grace_period = Field(int)
    user = Field(User)
    account = Field(IntegrationAccount)
    synced_at = Field(datetime)
    subscriber_count = Field(int)
    revoked = Field(bool)
    application = Field(Application)


class UserConnectionVisibilityType(object):
    NONE = 0
    EVERYONE = 1


class UserConnection(SlottedModel):
    id = Field(text)
    name = Field(str)
    type = Field(text)
    revoked = Field(bool)
    integrations = ListField(Integration)
    verified = Field(bool)
    friend_sync = Field(bool)
    show_activity = Field(bool)
    visibility = Field(enum(UserConnectionVisibilityType))
