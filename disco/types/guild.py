import warnings

from disco.api.http import APIException
from disco.types.oauth import Application
from disco.types.webhook import Webhook
from disco.util.paginator import Paginator
from disco.util.snowflake import to_snowflake
from disco.types.base import (
    SlottedModel, Field, ListField, AutoDictField, DictField, snowflake, text, enum, datetime,
    cached_property,
)
from disco.types.user import User
from disco.types.voice import VoiceState
from disco.types.channel import Channel, ChannelType
from disco.types.message import Emoji
from disco.types.permissions import PermissionValue, Permissions, Permissible


class MFALevel(object):
    NONE = 0
    ELEVATED = 1


class VerificationLevel(object):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    EXTREME = 4


class ExplicitContentFilterLevel(object):
    NONE = 0
    WITHOUT_ROLES = 1
    ALL = 2


class DefaultMessageNotificationsLevel(object):
    ALL_MESSAGES = 0
    ONLY_MENTIONS = 1


class PremiumTier(object):
    NONE = 0
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class SystemChannelFlag(object):
    NONE = 0
    SUPPRESS_JOIN_NOTIFICATIONS = 1 << 0
    SUPPRESS_PREMIUM_SUBSCRIPTIONS = 1 << 1
    SUPPRESS_GUILD_REMINDER_NOTIFICATIONS = 1 << 2


class WelcomeScreenChannel(object):
    channel_id = Field(snowflake)
    description = Field(str)
    emoji_id = Field(snowflake)
    emoji_name = Field(str)


class WelcomeScreen(object):
    description = Field(str)
    welcome_channels = AutoDictField(WelcomeScreenChannel, 'channel_id')


class GuildEmoji(Emoji):
    """
    An emoji object.

    Attributes
    ----------
    id : snowflake
        The ID of this emoji.
    name : str
        The name of this emoji.
    user : User
        The User that created this emoji.
    require_colons : bool
        Whether this emoji requires colons to use.
    managed : bool
        Whether this emoji is managed by an integration.
    roles : list(snowflake)
        Roles this emoji is attached to.
    animated : bool
        Whether this emoji is animated.
    """
    id = Field(snowflake)
    name = Field(text)
    roles = ListField(snowflake)
    user = Field(User)
    require_colons = Field(bool)
    managed = Field(bool)
    animated = Field(bool)
    available = Field(bool)
    guild_id = Field(snowflake)

    def __str__(self):
        return '<{}:{}:{}>'.format('a' if self.animated else '', self.name, self.id)

    def update(self, **kwargs):
        return self.client.api.guilds_emojis_modify(self.guild_id, self.id, **kwargs)

    def delete(self, **kwargs):
        return self.client.api.guilds_emojis_delete(self.guild_id, self.id, **kwargs)

    @property
    def url(self):
        return 'https://cdn.discordapp.com/emojis/{}.{}'.format(self.id, 'gif' if self.animated else 'png')

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)


class PruneCount(SlottedModel):
    pruned = Field(int, default=None)


class Role(SlottedModel):
    """
    A role object.

    Attributes
    ----------
    id : snowflake
        The role ID.
    name : string
        The role name.
    hoist : bool
        Whether this role is hoisted (displayed separately in the sidebar).
    managed : bool
        Whether this role is managed by an integration.
    color : int
        The RGB color of this role.
    permissions : :class:`disco.types.permissions.PermissionsValue`
        The permissions this role grants.
    position : int
        The position of this role in the hierarchy.
    tags : dict(str, snowflake)
        The tags of this role.
    mentionable : bool
        Whether this role is taggable in chat.
    guild_id : snowflake
        The id of the server the role is in.
    """
    id = Field(snowflake)
    guild_id = Field(snowflake)
    name = Field(text)
    hoist = Field(bool)
    managed = Field(bool)
    color = Field(int)
    permissions = Field(PermissionValue, cast=int)
    position = Field(int)
    mentionable = Field(bool)
    tags = DictField(text, snowflake)

    def __str__(self):
        return self.name

    def delete(self, **kwargs):
        self.guild.delete_role(self, **kwargs)

    def update(self, *args, **kwargs):
        self.guild.update_role(self, *args, **kwargs)

    @property
    def mention(self):
        return '<@&{}>'.format(self.id)

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)


class GuildBan(SlottedModel):
    user = Field(User)
    reason = Field(text)


class GuildEmbed(SlottedModel):
    enabled = Field(bool)
    channel_id = Field(snowflake)


class GuildPreview(SlottedModel):
    id = Field(int)
    name = Field(str)
    icon = Field(str)
    splash = Field(str)
    discovery_splash = Field(str)
    emojis = AutoDictField(GuildEmoji, 'id')
    features = ListField(str)
    approximate_member_count = Field(int)
    approximate_presence_count = Field(int)
    description = Field(str)


class GuildMember(SlottedModel):
    """
    A GuildMember object.

    Attributes
    ----------
    user : :class:`disco.types.user.User`
        The user object of this member.
    guild_id : snowflake
        The guild this member is part of.
    nick : str
        The nickname of the member.
    mute : bool
        Whether this member is server voice-muted.
    deaf : bool
        Whether this member is server voice-deafened.
    joined_at : datetime
        When this user joined the guild.
    roles : list(snowflake)
        Roles this member is part of.
    premium_since : datetime
        When this user set their Nitro boost to this server.
    pending : bool
        Whether the user has passed Discord's role gate.
    """
    user = Field(User)
    nick = Field(text, default=None)
    roles = ListField(snowflake)
    joined_at = Field(datetime)
    premium_since = Field(datetime)
    deaf = Field(bool)
    mute = Field(bool)
    is_pending = Field(bool, default=False)
    pending = Field(bool, default=False)
    permissions = Field(text)
    guild_id = Field(snowflake)

    def __str__(self):
        return self.user.__str__()

    @property
    def name(self):
        """
        The nickname of this user if set, otherwise their username
        """
        return self.nick or self.user.username

    def get_voice_state(self):
        """
        Returns
        -------
        Optional[:class:`disco.types.voice.VoiceState`]
            Returns the voice state for the member if they are currently connected
            to the guild's voice server.
        """
        return self.guild.get_voice_state(self)

    def kick(self, **kwargs):
        """
        Kicks the member from the guild.
        """
        self.client.api.guilds_members_kick(self.guild.id, self.user.id, **kwargs)

    def ban(self, delete_message_days=0, **kwargs):
        """
        Bans the member from the guild.

        Parameters
        ----------
        delete_message_days : int
            The number of days to retroactively delete messages for.
        """
        self.guild.create_ban(self, delete_message_days, **kwargs)

    def unban(self, **kwargs):
        """
        Unbans the member from the guild.
        """
        self.guild.delete_ban(self, **kwargs)

    def set_nickname(self, nickname=None, **kwargs):
        """
        Sets the member's nickname (or clears it if None).

        Parameters
        ----------
        nickname : Optional[str]
            The nickname (or none to reset) to set.
        """
        if self.client.state.me.id == self.user.id:
            self.client.api.guilds_members_me_nick(self.guild.id, nick=nickname or '', **kwargs)
        else:
            self.client.api.guilds_members_modify(self.guild.id, self.user.id, nick=nickname or '', **kwargs)

    def disconnect(self):
        """
        Disconnects the member from voice (if they are connected).
        """
        self.modify(channel_id=None)

    def modify(self, **kwargs):
        self.client.api.guilds_members_modify(self.guild.id, self.user.id, **kwargs)

    def add_role(self, role, **kwargs):
        self.client.api.guilds_members_roles_add(self.guild.id, self.user.id, to_snowflake(role), **kwargs)

    def remove_role(self, role, **kwargs):
        self.client.api.guilds_members_roles_remove(self.guild.id, self.user.id, to_snowflake(role), **kwargs)

    @cached_property
    def owner(self):
        return self.guild.owner_id == self.id

    @cached_property
    def mention(self):
        if self.nick:
            return '<@!{}>'.format(self.id)
        return self.user.mention

    @property
    def id(self):
        """
        Alias to the guild members user id.
        """
        return self.user.id

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)

    @cached_property
    def permissions(self):
        return self.guild.get_permissions(self)


class Guild(SlottedModel, Permissible):
    """
    A guild object.

    Attributes
    ----------
    id : snowflake
        The id of this guild.
    name : str
        Guild's name.
    icon : str
        Guild's icon image hash
    splash : str
        Guild's splash image hash
    owner : bool
        Whether the user is the server owner.
    owner_id : snowflake
        The id of the owner.
    afk_channel_id : snowflake
        The id of the afk channel.
    system_channel_id : snowflake
        The id of the system channel.
    name : str
        Guild's name.
    icon : str
        Guild's icon image hash
    splash : str
        Guild's splash image hash
    widget_channel_id : snowflake
        The id of the server widget channel
    banner : str
        Guild's banner image hash
    region : str
        Voice region.
    afk_timeout : int
        Delay after which users are automatically moved to the afk channel.
    widget_enabled : bool
        Whether the guild's server widget is enabled.
    verification_level : int
        The verification level used by the guild.
    mfa_level : int
        The MFA level used by the guild.
    features : list(str)
        Extra features enabled for this guild.
    system_channel_flags : int
        The system messages that are disabled.
    vanity_url_code : str
        Guild's vanity url code
    description : str
        Guild's description
    max_presences : int
        [DEPRECATED] Guild's maximum amount of presences
    max_members : int
        Guild's maximum amount of members
    preferred_locale : str
        Guild's primary language
    members : dict(snowflake, :class:`GuildMember`)
        All of the guild's members.
    channels : dict(snowflake, :class:`disco.types.channel.Channel`)
        All of the guild's channels.
    roles : dict(snowflake, :class:`Role`)
        All of the guild's roles.
    emojis : dict(snowflake, :class:`GuildEmoji`)
        All of the guild's emojis.
    voice_states : dict(str, :class:`disco.types.voice.VoiceState`)
        All of the guild's voice states.
    premium_tier : int
        Guild's premium tier.
    premium_subscription_count : int
        The amount of users using their Nitro boost on this guild.
    """
    id = Field(snowflake)
    name = Field(text)
    icon = Field(text)
    splash = Field(text)
    discovery_splash = Field(text)
    owner = Field(bool)
    owner_id = Field(snowflake)
    permissions = Field(PermissionValue, cast=int)
    region = Field(text)
    afk_channel_id = Field(snowflake)
    afk_timeout = Field(int)
    verification_level = Field(enum(VerificationLevel))
    default_message_notifications = Field(enum(DefaultMessageNotificationsLevel))
    explicit_content_filter = Field(enum(ExplicitContentFilterLevel))
    roles = AutoDictField(Role, 'id')
    emojis = AutoDictField(GuildEmoji, 'id')
    features = ListField(str)
    mfa_level = Field(enum(MFALevel))
    application_id = Field(snowflake)
    widget_enabled = Field(bool)
    widget_channel_id = Field(snowflake)
    system_channel_id = Field(snowflake)
    system_channel_flags = Field(int)
    rules_channel_id = Field(snowflake)
    joined_at = Field(datetime)
    large = Field(bool)
    unavailable = Field(bool)
    member_count = Field(int)
    voice_states = AutoDictField(VoiceState, 'session_id')
    members = AutoDictField(GuildMember, 'id')
    channels = AutoDictField(Channel, 'id')
    threads = AutoDictField(Channel, 'id')
    # presences = AutoDictField(Presence)
    max_presences = Field(int, default=None)
    max_members = Field(int)
    vanity_url_code = Field(text, default=None)
    description = Field(text)
    banner = Field(text)
    premium_tier = Field(enum(PremiumTier))
    premium_subscription_count = Field(int, default=0)
    preferred_locale = Field(str)
    public_updates_channel_id = Field(snowflake)
    max_video_channel_users = Field(int)
    approximate_member_count = Field(int)
    approximate_presence_count = Field(int)
    # welcome_screen = Field(WelcomeScreen)
    nsfw = Field(bool)

    def __init__(self, *args, **kwargs):
        super(Guild, self).__init__(*args, **kwargs)

        self.attach(self.channels.values(), {'guild_id': self.id})
        self.attach(self.members.values(), {'guild_id': self.id})
        self.attach(self.roles.values(), {'guild_id': self.id})
        self.attach(self.emojis.values(), {'guild_id': self.id})
        self.attach(self.voice_states.values(), {'guild_id': self.id})

    @cached_property
    def owner(self):
        return self.members.get(self.owner_id)

    def get_commands(self):
        return self.client.api.applications_guild_commands_get(self.id)

    def register_command(self, name, description, options=None):
        data = {}
        data['name'] = name
        data['description'] = description
        data['options'] = options
        return self.client.api.applications_guild_commands_create(self.id, name, data)

    def update_command(self, command_id, name, description, options):
        data = {}
        data['name'] = name
        data['description'] = description
        data['options'] = options
        return self.client.api.applications_guild_commands_modify(self.id, command_id, data)

    def delete_command(self, command_id):
        return self.client.api.applications_guild_commands_delete(self.id, command_id)

    def get_permissions(self, member):
        """
        Get the permissions a user has in this guild.

        Returns
        -------
        :class:`disco.types.permissions.PermissionValue`
            Computed permission value for the user.
        """
        if not isinstance(member, GuildMember):
            member = self.get_member(member)

        # Owner has all permissions
        if self.owner_id == member.id:
            return PermissionValue(Permissions.ADMINISTRATOR)

        # Our value starts with the guilds default (@everyone) role permissions
        value = PermissionValue(self.roles.get(self.id).permissions)

        # Iterate over all roles the user has (plus the @everyone role)
        for role in map(self.roles.get, member.roles + [self.id]):
            value += role.permissions

        return value

    def get_voice_state(self, user):
        """
        Attempt to get a voice state for a given user (who should be a member of
        this guild).

        Returns
        -------
        :class:`disco.types.voice.VoiceState`
            The voice state for the user in this guild.
        """
        user = to_snowflake(user)

        for state in self.voice_states.values():
            if state.user_id == user:
                return state

    def get_member(self, user):
        """
        Attempt to get a member from a given user.

        Returns
        -------
        :class:`GuildMember`
            The guild member object for the given user.
        """
        user = to_snowflake(user)

        if user not in self.members:
            try:
                self.members[user] = self.client.api.guilds_members_get(self.id, user)
            except APIException:
                return

        return self.members.get(user)

    def get_prune_count(self, days=None):
        return self.client.api.guilds_prune_count_get(self.id, days=days)

    def prune(self, days=None, compute_prune_count=None):
        return self.client.api.guilds_prune_create(self.id, days=days, compute_prune_count=compute_prune_count)

    def create_role(self, **kwargs):
        """
        Create a new role.

        Returns
        -------
        :class:`Role`
            The newly created role.
        """
        return self.client.api.guilds_roles_create(self.id, **kwargs)

    def delete_role(self, role, **kwargs):
        """
        Delete a role.
        """
        self.client.api.guilds_roles_delete(self.id, to_snowflake(role), **kwargs)

    def update_role(self, role, **kwargs):
        if 'permissions' in kwargs and isinstance(kwargs['permissions'], PermissionValue):
            kwargs['permissions'] = kwargs['permissions'].value

        return self.client.api.guilds_roles_modify(self.id, to_snowflake(role), **kwargs)

    def request_guild_members(self, query=None, limit=0, presences=False):
        self.client.gw.request_guild_members(self.id, query, limit, presences)

    def request_guild_members_by_id(self, user_id_or_ids, limit=0, presences=False):
        self.client.gw.request_guild_members_by_id(self.id, user_id_or_ids, limit, presences)

    def sync(self):
        warnings.warn(
            'Guild.sync has been deprecated in place of Guild.request_guild_members',
            DeprecationWarning)

        self.request_guild_members()

    def get_bans(self):
        return self.client.api.guilds_bans_list(self.id)

    def get_ban(self, user):
        return self.client.api.guilds_bans_get(self.id, user)

    def delete_ban(self, user, **kwargs):
        self.client.api.guilds_bans_delete(self.id, to_snowflake(user), **kwargs)

    def create_ban(self, user, *args, **kwargs):
        self.client.api.guilds_bans_create(self.id, to_snowflake(user), *args, **kwargs)

    def create_channel(self, *args, **kwargs):
        warnings.warn(
            'Guild.create_channel will be deprecated soon, please use:'
            ' Guild.create_text_channel or Guild.create_category or Guild.create_voice_channel',
            DeprecationWarning)

        return self.client.api.guilds_channels_create(self.id, *args, **kwargs)

    def create_category(self, name, permission_overwrites=[], position=None, reason=None):
        """
        Creates a category within the guild.
        """
        return self.client.api.guilds_channels_create(
            self.id, ChannelType.GUILD_CATEGORY, name=name, permission_overwrites=permission_overwrites,
            position=position, reason=reason,
        )

    def create_text_channel(self, name, permission_overwrites=[], parent_id=None, nsfw=None, position=None, reason=None):
        """
        Creates a text channel within the guild.
        """
        return self.client.api.guilds_channels_create(
            self.id, ChannelType.GUILD_TEXT, name=name, permission_overwrites=permission_overwrites,
            parent_id=parent_id, nsfw=nsfw, position=position, reason=reason,
        )

    def create_voice_channel(
            self,
            name,
            permission_overwrites=[],
            parent_id=None,
            bitrate=None,
            user_limit=None,
            position=None,
            reason=None):
        """
        Creates a voice channel within the guild.
        """
        return self.client.api.guilds_channels_create(
            self.id, ChannelType.GUILD_VOICE, name=name, permission_overwrites=permission_overwrites,
            parent_id=parent_id, bitrate=bitrate, user_limit=user_limit, position=position, reason=reason)

    def leave(self):
        return self.client.api.users_me_guilds_delete(self.id)

    def get_invites(self):
        return self.client.api.guilds_invites_list(self.id)

    def get_emojis(self):
        return self.client.api.guilds_emojis_list(self.id)

    def get_emoji(self, emoji):
        return self.client.api.guilds_emojis_get(self.id, emoji)

    def get_preview(self):
        return self.client.api.guilds_preview_get(self.id)

    def get_voice_regions(self):
        return self.client.api.guilds_voice_regions_list(self.id)

    def get_icon_url(self, still_format='webp', animated_format='gif', size=1024):
        if not self.icon:
            return ''

        if self.icon.startswith('a_'):
            return 'https://cdn.discordapp.com/icons/{}/{}.{}?size={}'.format(
                self.id, self.icon, animated_format, size
            )
        else:
            return 'https://cdn.discordapp.com/icons/{}/{}.{}?size={}'.format(
                self.id, self.icon, still_format, size
            )

    def get_vanity_url(self):
        if not self.vanity_url_code:
            return ''

        return 'https://discord.gg/' + self.vanity_url_code

    def get_splash_url(self, fmt='webp', size=1024):
        if not self.splash:
            return ''

        return 'https://cdn.discordapp.com/splashes/{}/{}.{}?size={}'.format(self.id, self.splash, fmt, size)

    def get_banner_url(self, fmt='webp', size=1024):
        if not self.banner:
            return ''

        return 'https://cdn.discordapp.com/banners/{}/{}.{}?size={}'.format(self.id, self.banner, fmt, size)

    @property
    def icon_url(self):
        return self.get_icon_url()

    @property
    def vanity_url(self):
        return self.get_vanity_url()

    @property
    def splash_url(self):
        return self.get_splash_url()

    @property
    def banner_url(self):
        return self.get_banner_url()

    @property
    def system_channel(self):
        return self.channels.get(self.system_channel_id)

    @property
    def audit_log(self):
        return self.audit_log_iter()

    def audit_log_iter(self, **kwargs):
        return Paginator(
            self.client.api.guilds_auditlogs_list,
            'before',
            self.id,
            **kwargs
        )

    def get_audit_log_entries(self, *args, **kwargs):
        return self.client.api.guilds_auditlogs_list(self.id, *args, **kwargs)

    def get_discovery_requirements(self):
        return self.client.api.guilds_discovery_requirements(self.id)


class IntegrationAccount(SlottedModel):
    id = Field(text)
    name = Field(text)


class IntegrationExpireBehaviors(object):
    REMOVAL_ROLE = 0
    KICK = 1


class IntegrationApplication(SlottedModel):
    id = Field(snowflake)
    name = Field(text)
    icon = Field(text)
    description = Field(text)
    summary = Field(text)
    bot = Field(User)



class Integration(SlottedModel):
    id = Field(snowflake)
    name = Field(text)
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


class AuditLogActionTypes(object):
    GUILD_UPDATE = 1
    CHANNEL_CREATE = 10
    CHANNEL_UPDATE = 11
    CHANNEL_DELETE = 12
    CHANNEL_OVERWRITE_CREATE = 13
    CHANNEL_OVERWRITE_UPDATE = 14
    CHANNEL_OVERWRITE_DELETE = 15
    MEMBER_KICK = 20
    MEMBER_PRUNE = 21
    MEMBER_BAN_ADD = 22
    MEMBER_BAN_REMOVE = 23
    MEMBER_UPDATE = 24
    MEMBER_ROLE_UPDATE = 25
    MEMBER_MOVE = 26
    MEMBER_DISCONNECT = 27
    BOT_ADD = 28
    ROLE_CREATE = 30
    ROLE_UPDATE = 31
    ROLE_DELETE = 32
    INVITE_CREATE = 40
    INVITE_UPDATE = 41
    INVITE_DELETE = 42
    WEBHOOK_CREATE = 50
    WEBHOOK_UPDATE = 51
    WEBHOOK_DELETE = 52
    EMOJI_CREATE = 60
    EMOJI_UPDATE = 61
    EMOJI_DELETE = 62
    MESSAGE_DELETE = 72
    MESSAGE_BULK_DELETE = 73
    MESSAGE_PIN = 74
    MESSAGE_UNPIN = 75
    INTEGRATION_CREATE = 80
    INTEGRATION_UPDATE = 81
    INTEGRATION_DELETE = 82


GUILD_ACTIONS = (
    AuditLogActionTypes.GUILD_UPDATE,
    AuditLogActionTypes.BOT_ADD,
)

CHANNEL_ACTIONS = (
    AuditLogActionTypes.CHANNEL_CREATE,
    AuditLogActionTypes.CHANNEL_UPDATE,
    AuditLogActionTypes.CHANNEL_DELETE,
    AuditLogActionTypes.CHANNEL_OVERWRITE_CREATE,
    AuditLogActionTypes.CHANNEL_OVERWRITE_UPDATE,
    AuditLogActionTypes.CHANNEL_OVERWRITE_DELETE,
)

MEMBER_ACTIONS = (
    AuditLogActionTypes.MEMBER_KICK,
    AuditLogActionTypes.MEMBER_PRUNE,
    AuditLogActionTypes.MEMBER_BAN_ADD,
    AuditLogActionTypes.MEMBER_BAN_REMOVE,
    AuditLogActionTypes.MEMBER_UPDATE,
    AuditLogActionTypes.MEMBER_ROLE_UPDATE,
    AuditLogActionTypes.MEMBER_MOVE,
    AuditLogActionTypes.MEMBER_DISCONNECT,
)

ROLE_ACTIONS = (
    AuditLogActionTypes.ROLE_CREATE,
    AuditLogActionTypes.ROLE_UPDATE,
    AuditLogActionTypes.ROLE_DELETE,
)

INVITE_ACTIONS = (
    AuditLogActionTypes.INVITE_CREATE,
    AuditLogActionTypes.INVITE_UPDATE,
    AuditLogActionTypes.INVITE_DELETE,
)

WEBHOOK_ACTIONS = (
    AuditLogActionTypes.WEBHOOK_CREATE,
    AuditLogActionTypes.WEBHOOK_UPDATE,
    AuditLogActionTypes.WEBHOOK_DELETE,
)

EMOJI_ACTIONS = (
    AuditLogActionTypes.EMOJI_CREATE,
    AuditLogActionTypes.EMOJI_UPDATE,
    AuditLogActionTypes.EMOJI_DELETE,
)

MESSAGE_ACTIONS = (
    AuditLogActionTypes.MESSAGE_DELETE,
    AuditLogActionTypes.MESSAGE_BULK_DELETE,
    AuditLogActionTypes.MESSAGE_PIN,
    AuditLogActionTypes.MESSAGE_UNPIN,
)

INTEGRATIONS_ACTIONS = (
    AuditLogActionTypes.INTEGRATION_CREATE,
    AuditLogActionTypes.INTEGRATION_UPDATE,
    AuditLogActionTypes.INTEGRATION_DELETE,
)


class AuditLogObjectChange(SlottedModel):
    key = Field(text)
    new_value = Field(text)
    old_value = Field(text)


class AuditLogOptionalEntryInfo(SlottedModel):
    delete_member_days = Field(text)
    members_removed = Field(text)
    channel_id = Field(snowflake)
    message_id = Field(snowflake)
    count = Field(text)
    id = Field(snowflake)
    type = Field(text)
    role_name = Field(text)


class AuditLogEntry(SlottedModel):
    target_id = Field(snowflake)
    changes = ListField(AuditLogObjectChange)
    user_id = Field(snowflake)
    id = Field(snowflake)
    action_type = Field(enum(AuditLogActionTypes))
    # options = DictField(text, text)
    options = Field(AuditLogActionTypes)
    reason = Field(text)
    guild_id = Field(snowflake)

    _cached_target = Field(None)

    @classmethod
    def create(cls, client, users, webhooks, data, **kwargs):
        self = super(SlottedModel, cls).create(client, data, **kwargs)

        if self.action_type in MEMBER_ACTIONS:
            self._cached_target = users[self.target_id]
        elif self.action_type in WEBHOOK_ACTIONS:
            self._cached_target = webhooks[self.target_id]

        return self

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)

    @cached_property
    def user(self):
        return self.client.state.users.get(self.user_id)

    @cached_property
    def target(self):
        if self.action_type in GUILD_ACTIONS:
            return self.guild
        elif self.action_type in CHANNEL_ACTIONS:
            return self.guild.channels.get(self.target_id)
        elif self.action_type in MEMBER_ACTIONS:
            return self._cached_target or self.state.users.get(self.target_id)
        elif self.action_type in ROLE_ACTIONS:
            return self.guild.roles.get(self.target_id)
        elif self.action_type in WEBHOOK_ACTIONS:
            return self._cached_target
        elif self.action_type in EMOJI_ACTIONS:
            return self.guild.emojis.get(self.target_id)


class AuditLog(SlottedModel):
    webhooks = ListField(Webhook)
    users = ListField(User)
    audit_log_entries = ListField(AuditLogEntry)
    integrations = ListField(Integration)


class DiscoveryRequirementsHealthScore(SlottedModel):
    avg_nonnew_participators = Field(text, default=None)
    avg_nonnew_communicators = Field(text, default=None)
    num_intentful_joiners = Field(text, default=None)
    perc_ret_w1_intentful = Field(text, default=None)


class DiscoveryRequirements(SlottedModel):
    age = Field(bool)
    guild_id = Field(int)
    health_score = Field(DiscoveryRequirementsHealthScore)
    health_score_pending = Field(bool)
    healthy = Field(bool)
    minimum_age = Field(int)
    minimum_size = Field(int)
    nsfw_properties = Field(dict)
    protected = Field(bool)
    retention_healthy = Field(bool)
    engagement_healthy = Field(bool)
    safe_environment = Field(bool)
    size = Field(bool)
    sufficient = Field(bool)
    sufficient_without_grace_period = Field(bool)
    valid_rules_channel = Field(bool)


class DiscoveryCategoryName(SlottedModel):
    default = Field(str)
    # localizations = Field


class DiscoveryCategory(SlottedModel):
    id = Field(int)
    name = Field(DiscoveryCategoryName)
    is_primary = Field(bool)


class DiscoveryGuild(SlottedModel):
    guild_id = Field(snowflake)
    primary_category_id = Field(str)
    keywords = ListField(str)
    emoji_discoverability_enabled = Field(bool)
    category_ids = ListField(str)


class GuildTemplate(SlottedModel):
    code = Field(text)
    name = Field(text)
    description = Field(text)
    usage_count = Field(int)
    creator_id = Field(snowflake)
    creator = Field(User)
    created_at = Field(datetime)
    updated_at = Field(datetime)
    source_guild_id = Field(snowflake)
    serialized_source_guild = Field(Guild)
    is_dirty = Field(bool)
