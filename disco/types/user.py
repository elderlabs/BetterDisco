from datetime import datetime

from disco.types.base import (
    SlottedModel, Field, snowflake, text, with_equality, with_hash, enum, ListField, cached_property, str_or_int
)


class DefaultAvatars:
    BLURPLE = 0
    GREY = 1
    GREEN = 2
    ORANGE = 3
    RED = 4

    ALL = ['BLURPLE', 'GREY', 'GREEN', 'ORANGE', 'RED']


class UserFlags:
    NONE = 0
    DISCORD_EMPLOYEE = 1 << 0
    DISCORD_PARTNER = 1 << 1
    HYPESQUAD_EVENTS = 1 << 2
    BUG_HUNTER_LEVEL_1 = 1 << 3
    MFA_SMS = 1 << 4
    PREMIUM_PROMO_DISMISSED = 1 << 5
    HYPESQUAD_ONLINE_HOUSE_1 = 1 << 6
    HYPESQUAD_ONLINE_HOUSE_2 = 1 << 7
    HYPESQUAD_ONLINE_HOUSE_3 = 1 << 8
    PREMIUM_EARLY_SUPPORTER = 1 << 9
    TEAM_PSEUDO_USER = 1 << 10
    # UNDOCUMENTED = 1 << 11
    SYSTEM = 1 << 12
    UNREAD_SYS_MSG = 1 << 13
    BUG_HUNTER_LEVEL_2 = 1 << 14
    UNDERAGE_DELETED = 1 << 15
    VERIFIED_BOT = 1 << 16
    VERIFIED_DEVELOPER = 1 << 17
    CERTIFIED_MODERATOR = 1 << 18
    BOT_HTTP_INTERACTIONS = 1 << 19
    ACTIVE_DEVELOPER = 1 << 20


class PremiumType:
    NONE = 0
    CLASSIC = 1
    NITRO = 2


class User(SlottedModel, with_equality('id'), with_hash('id')):
    id = Field(snowflake)
    username = Field(text)
    discriminator = Field(int)
    avatar = Field(text)
    bot = Field(bool, default=False)
    system = Field(bool, default=False)
    mfa_enabled = Field(bool)
    banner = Field(text)
    accent_color = Field(str_or_int)
    locale = Field(text)
    verified = Field(bool)
    email = Field(text)
    flags = Field(int)
    public_flags = Field(int, default=0)
    premium_type = Field(enum(PremiumType))
    # member = Field(GuildMember)

    def get_avatar_url(self, fmt=None, size=1024):
        if not self.avatar:
            return 'https://cdn.discordapp.com/embed/avatars/{}.png'.format(self.default_avatar)

        if not fmt:
            fmt = 'gif' if self.avatar.startswith('a_') else 'webp'
        elif fmt == 'gif' and not self.avatar.startswith('a_'):
            fmt = 'webp'

        return 'https://cdn.discordapp.com/avatars/{}/{}.{}?size={}'.format(self.id, self.avatar, fmt, size)

    def get_banner_url(self, fmt=None, size=1024):
        if not self.banner:
            return ''

        if not fmt:
            fmt = 'gif' if self.banner.startswith('a_') else 'webp'
        elif fmt == 'gif' and not self.banner.startswith('a_'):
            fmt = 'webp'

        return 'https://cdn.discordapp.com/banners/{}/{}.{}?size={}'.format(self.id, self.avatar, fmt, size)

    @property
    def default_avatar(self):
        return DefaultAvatars.ALL[self.discriminator % len(DefaultAvatars.ALL)]

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

    def __int__(self):
        return self.id

    def __repr__(self):
        return '<User id={} user={}>'.format(self.id, self)


class ActivityTypes:
    DEFAULT = 0
    STREAMING = 1
    LISTENING = 2
    WATCHING = 3
    CUSTOM = 4
    COMPETING = 5


class Status:
    ONLINE = 'ONLINE'
    IDLE = 'IDLE'
    DND = 'DND'
    INVISIBLE = 'INVISIBLE'
    OFFLINE = 'OFFLINE'


class ClientStatus(SlottedModel):
    desktop = Field(text)
    mobile = Field(text)
    web = Field(text)


class ActivityParty(SlottedModel):
    id = Field(text)
    # size = ListField(int)


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


class ActivityFlags:
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
