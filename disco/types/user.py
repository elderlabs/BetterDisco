from datetime import datetime

from disco.types.base import (
    SlottedModel, Field, snowflake, text, with_equality, with_hash, enum, ListField,
    cached_property,
)


class DefaultAvatars(object):
    BLURPLE = 0
    GREY = 1
    GREEN = 2
    ORANGE = 3
    RED = 4

    ALL = [BLURPLE, GREY, GREEN, ORANGE, RED]


class UserFlags(object):
    NONE = 0
    DISCORD_EMPLOYEE = 1 << 0
    DISCORD_PARTNER = 1 << 1
    HS_EVENTS = 1 << 2
    BUG_HUNTER_LVL1 = 1 << 3
    MFA_SMS = 1 << 4
    PREMIUM_PROMO_DISMISSED = 1 << 5
    HS_BRAVERY = 1 << 6
    HS_BRILLIANCE = 1 << 7
    HS_BALANCE = 1 << 8
    EARLY_SUPPORTER = 1 << 9
    TEAM_USER = 1 << 10
    SYSTEM = 1 << 12
    UNREAD_SYS_MSG = 1 << 13
    BUG_HUNTER_LVL2 = 1 << 14
    UNDERAGE_DELETED = 1 << 15
    VERIFIED_BOT = 1 << 16
    VERIFIED_DEV = 1 << 17
    CERTIFIED_MOD = 1 << 18


class PremiumType(object):
    CLASSIC = 1
    NITRO = 2


class UserConnection(object):
    id = Field(str)
    name = Field(str)
    type = Field(str)
    revoked = Field(bool)
    verified = Field(bool)
    friend_sync = Field(bool)
    show_activity = Field(bool)
    visibility = Field(int)


class VisibilityType(object):
    NONE = 0
    EVERYONE = 1


class User(SlottedModel, with_equality('id'), with_hash('id')):
    id = Field(snowflake)
    username = Field(text)
    discriminator = Field(text)
    avatar = Field(text)
    bot = Field(bool, default=False)
    system = Field(bool, default=False)
    mfa_enabled = Field(bool)
    locale = Field(text)
    verified = Field(bool)
    email = Field(text)
    flags = Field(int)
    public_flags = Field(int, default=0)
    premium_type = Field(enum(PremiumType))
    presence = Field(None)

    def get_avatar_url(self, still_format='webp', animated_format='gif', size=1024):
        if not self.avatar:
            return 'https://cdn.discordapp.com/embed/avatars/{}.png'.format(self.default_avatar)

        if self.avatar.startswith('a_'):
            return 'https://cdn.discordapp.com/avatars/{}/{}.{}?size={}'.format(
                self.id, self.avatar, animated_format, size
            )
        else:
            return 'https://cdn.discordapp.com/avatars/{}/{}.{}?size={}'.format(
                self.id, self.avatar, still_format, size
            )

    @property
    def default_avatar(self):
        return DefaultAvatars.ALL[int(self.discriminator) % len(DefaultAvatars.ALL)]

    @property
    def avatar_url(self):
        return self.get_avatar_url()

    @property
    def mention(self):
        return '<@{}>'.format(self.id)

    @property
    def mention_nickname(self):
        return '<@!{}>'.format(self.id)

    def open_dm(self):
        return self.client.api.users_me_dms_create(self.id)

    def __str__(self):
        return '{}#{}'.format(self.username, str(self.discriminator).zfill(4))

    def __repr__(self):
        return '<User {} ({})>'.format(self.id, self)


class ActivityTypes(object):
    DEFAULT = 0
    STREAMING = 1
    LISTENING = 2
    WATCHING = 3
    CUSTOM = 4
    COMPETING = 5


class Status(object):
    ONLINE = 'ONLINE'
    IDLE = 'IDLE'
    DND = 'DND'
    INVISIBLE = 'INVISIBLE'
    OFFLINE = 'OFFLINE'


class ClientStatus(SlottedModel):
    desktop = Field(str)
    mobile = Field(str)
    web = Field(str)


class ActivityParty(SlottedModel):
    id = Field(text)
    size = ListField(int)


class ActivityAssets(SlottedModel):
    large_image = Field(text)
    large_text = Field(text)
    small_image = Field(text)
    small_text = Field(text)


class ActivitySecrets(SlottedModel):
    join = Field(text)
    spectate = Field(text)
    match = Field(text)


class ActivityTimestamps(SlottedModel):
    start = Field(int)
    end = Field(int)

    @cached_property
    def start_time(self):
        return datetime.utcfromtimestamp(self.start / 1000)

    @cached_property
    def end_time(self):
        return datetime.utcfromtimestamp(self.end / 1000)


class ActivityFlags(object):
    INSTANCE = 1 << 0
    JOIN = 1 << 1
    SPECTATE = 1 << 2
    JOIN_REQUEST = 1 << 3
    SYNC = 1 << 4
    PLAY = 1 << 5


class Activity(SlottedModel):
    name = Field(text)
    type = Field(enum(ActivityTypes))
    url = Field(text)
    timestamps = Field(ActivityTimestamps)
    application_id = Field(text)
    details = Field(text)
    state = Field(text)
    party = Field(ActivityParty)
    assets = Field(ActivityAssets)
    secrets = Field(ActivitySecrets)
    instance = Field(bool)
    flags = Field(int)


class Presence(SlottedModel):
    user = Field(User, alias='user', ignore_dump=['presence'])
    activity = Field(Activity)
    guild_id = Field(snowflake)
    status = Field(enum(Status))
    activities = ListField(Activity)
    client_status = Field(ClientStatus)
