from disco.api.http import APIException
from disco.types.integration import Integration
from disco.types.webhook import Webhook
from disco.util.paginator import Paginator
from disco.util.snowflake import to_snowflake
from disco.types.base import (
    SlottedModel, Field, ListField, AutoDictField, snowflake, text, enum, datetime,
    cached_property, BitsetMap, BitsetValue,
)
from disco.types.user import User
from disco.types.voice import VoiceState
from disco.types.channel import Channel, ChannelType, StageInstance, PermissionOverwrite, StageInstancePrivacyLevel, \
    Thread
from disco.types.reactions import Emoji, Sticker, StickerFormatTypes
from disco.types.permissions import PermissionValue, Permissions, Permissible


class MFALevel:
    NONE = 0
    ELEVATED = 1


class VerificationLevel:
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERY_HIGH = 4


class GuildNSFWLevel:
    DEFAULT = 0
    EXPLICIT = 1
    SAFE = 2
    AGE_RESTRICTED = 3


class ExplicitContentFilterLevel:
    DISABLED = 0
    MEMBERS_WITHOUT_ROLES = 1
    ALL_MEMBERS = 2


class DefaultMessageNotificationsLevel:
    ALL_MESSAGES = 0
    ONLY_MENTIONS = 1


class PremiumTier:
    NONE = 0
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class SystemChannelFlag(BitsetMap):
    SUPPRESS_JOIN_NOTIFICATIONS = 1 << 0
    SUPPRESS_PREMIUM_SUBSCRIPTIONS = 1 << 1
    SUPPRESS_GUILD_REMINDER_NOTIFICATIONS = 1 << 2
    SUPPRESS_JOIN_NOTIFICATION_REPLIES = 1 << 3
    SUPPRESS_ROLE_SUBSCRIPTION_PURCHASE_NOTIFICATIONS = 1 << 4
    SUPPRESS_ROLE_SUBSCRIPTION_PURCHASE_NOTIFICATION_REPLIES = 1 << 5


class SystemChannelFlagValue(BitsetValue):
    map = SystemChannelFlag


class GuildFeatures:
    ANIMATED_ICON = 'ANIMATED_ICON'
    BANNER = 'BANNER'
    COMMERCE = 'COMMERCE'
    COMMUNITY = 'COMMUNITY'
    DISCOVERABLE = 'DISCOVERABLE'
    DISCOVERABLE_DISABLED = 'DISCOVERABLE_DISABLED'
    FEATURABLE = 'FEATURABLE'
    INVITE_SPLASH = 'INVITE_SPLASH'
    MEMBER_VERIFICATION_GATE_ENABLED = 'MEMBER_VERIFICATION_GATE_ENABLED'
    NEWS = 'NEWS'
    PARTNERED = 'PARTNERED'
    PREVIEW_ENABLED = 'PREVIEW_ENABLED'
    VANITY_URL = 'VANITY_URL'
    VERIFIED = 'VERIFIED'
    VIP_REGIONS = 'VIP_REGIONS'
    WELCOME_SCREEN_ENABLED = 'WELCOME_SCREEN_ENABLED'
    TICKETED_EVENTS_ENABLED = 'TICKETED_EVENTS_ENABLED'
    MONETIZATION_ENABLED = 'MONETIZATION_ENABLED'
    MORE_STICKERS = 'MORE_STICKERS'
    THREE_DAY_THREAD_ARCHIVE = 'THREE_DAY_THREAD_ARCHIVE'
    SEVEN_DAY_THREAD_ARCHIVE = 'SEVEN_DAY_THREAD_ARCHIVE'
    PRIVATE_THREADS = 'PRIVATE_THREADS'


class PruneCount(SlottedModel):
    pruned = Field(int)


class RoleFlags(BitsetMap):
    IN_PROMPT = 1 << 0


class RoleFlagsValue(BitsetValue):
    map = RoleFlags


class RoleTags(SlottedModel):
    bot_id = Field(snowflake)
    integration_id = Field(snowflake)
    premium_subscriber = Field(bool)  # null = True
    subscription_listing_id = Field(snowflake)
    available_for_purchase = Field(bool)  # null = True
    guild_connections = Field(bool)  # null = True


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
    permissions = Field(PermissionValue)
    position = Field(int)
    mentionable = Field(bool)
    tags = Field(RoleTags)
    version = Field(int)
    unicode_emoji = Field(text)
    icon = Field(text)
    flags = Field(RoleFlagsValue)

    def __repr__(self):
        return f'<Role id={self.id} name={self.name}>'

    def __str__(self):
        return self.name

    def __int__(self):
        return self.id

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


class GuildEmoji(Emoji):
    """
    An emoji object.
    """
    roles = ListField(snowflake)

    def update(self, **kwargs):
        return self.client.api.guilds_emojis_modify(self.guild_id, self.id, **kwargs)

    def delete(self, **kwargs):
        return self.client.api.guilds_emojis_delete(self.guild_id, self.id, **kwargs)

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)


class GuildBan(SlottedModel):
    user = Field(User)
    reason = Field(text)


class GuildPreview(SlottedModel):
    id = Field(int)
    name = Field(text)
    icon = Field(text)
    splash = Field(text)
    discovery_splash = Field(text)
    emojis = AutoDictField(GuildEmoji, 'id')
    features = ListField(str)
    approximate_member_count = Field(int)
    approximate_presence_count = Field(int)
    description = Field(text)
    stickers = ListField(Sticker)


class GuildWidgetSettings(SlottedModel):
    enabled = Field(bool)
    channel_id = Field(snowflake)


class GuildWidget(SlottedModel):
    id = Field(snowflake)
    name = Field(text)
    instant_invite = Field(text)
    channels = ListField(Channel)
    members = ListField(User)
    presence_count = Field(int)


class GuildMemberFlags(BitsetMap):
    DID_REJOIN = 1 << 0
    COMPLETED_ONBOARDING = 1 << 1
    BYPASSES_VERIFICATION = 1 << 2
    STARTED_ONBOARDING = 1 << 3


class GuildMemberFlagValue(BitsetValue):
    map = GuildMemberFlags


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
    user = Field(User, create=False)
    nick = Field(text)
    avatar = Field(text)
    roles = ListField(snowflake)
    joined_at = Field(datetime)
    premium_since = Field(datetime)
    deaf = Field(bool)
    mute = Field(bool)
    flags = Field(GuildMemberFlagValue)
    pending = Field(bool, default=False)
    permissions = Field(PermissionValue)
    communication_disabled_until = Field(datetime)
    guild_id = Field(snowflake)
    hoisted_role = Field(snowflake)
    unusual_dm_activity_until = Field(datetime)

    def __repr__(self):
        return f'<GuildMember id={int(self.user)} name={str(self.user)}>' if self.user else f'<GuildMember partial guild={self.guild_id}>'

    def __str__(self):
        return str(self.user)

    def __int__(self):
        return int(self.user)

    @property
    def name(self):
        """
        The nickname of this user if set, otherwise their username
        """
        return self.nick or self.user.username

    def get_avatar_url(self, fmt=None, size=1024):
        if not self.avatar:
            return self.user.get_avatar_url(fmt, size)

        if not fmt:
            fmt = 'gif' if self.avatar.startswith('a_') else 'webp'
        elif fmt == 'gif' and not self.avatar.startswith('a_'):
            fmt = 'webp'

        return 'https://cdn.discordapp.com/guilds/{}/users/{}/avatars/{}.{}?size={}'.format(self.guild_id, self.id, self.avatar, fmt, size)

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
        self.client.api.guilds_members_remove(self.guild.id, self.user.id, **kwargs)

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

    def timeout(self, duration=None, **kwargs):
        """
        Times out the user for the specified duration (or clears it if None)

        Parameters
        ----------
        duration : Optional[str]
            The ISO8601 timestamp when the mute should expire. Max 28 days.
        """
        return self.client.api.guilds_members_modify(self.guild.id, self.user.id,
                                                     communication_disabled_until=duration, **kwargs)

    def set_nickname(self, nickname=None, **kwargs):
        """
        Sets the member's nickname (or clears it if None).

        Parameters
        ----------
        nickname : Optional[str]
            The nickname (or none to reset) to set.
        """
        if self.client.state.me.id == self.user.id:
            return self.client.api.guilds_members_me_modify(self.guild.id, nick=nickname or '', **kwargs)
        return self.client.api.guilds_members_modify(self.guild.id, self.user.id, nick=nickname or '', **kwargs)

    def disconnect(self):
        """
        Disconnects the member from voice (if they are connected).
        """
        if self.client.state.me.id == self.user.id:
            return self.client.state.voice_clients.get(self.guild.id).disconnect()
        return self.modify(channel_id=None)

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
            return '<@{}>'.format(self.id)
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
    def get_permissions(self):
        return self.guild.get_permissions(self)


class WelcomeScreenChannel:
    channel_id = Field(snowflake)
    description = Field(text)
    emoji_id = Field(snowflake)
    emoji_name = Field(text)

class WelcomeScreen:

    description = Field(text)
    welcome_channels = AutoDictField(WelcomeScreenChannel, 'channel_id')


class OnboardingPromptTypes:
    MULTIPLE_CHOICE = 0
    DROPDOWN = 1

class OnboardingMode:
    ONBOARDING_DEFAULT = 0

    ONBOARDING_ADVANCED = 1


class GuildOnboarding(SlottedModel):
    guild_id = Field(snowflake)
    prompts = ListField(enum(OnboardingPromptTypes))
    default_channel_ids = ListField(snowflake)
    enabled = Field(bool)
    mode = Field(enum(OnboardingMode))


class GuildScheduledEventPrivacyLevel:

    GUILD_ONLY = 2

    STAGE_INSTANCE = 1
class GuildScheduledEventEntityTypes:
    VOICE = 2
    EXTERNAL = 3


class GuildScheduledEventStatus:
    SCHEDULED = 1
    COMPLETED = 3
    ACTIVE = 2
    CANCELED = 4


class GuildScheduledEventEntityMetadata(SlottedModel):
    location = Field(text)


class GuildScheduledEventUser(SlottedModel):
    guild_scheduled_event_id = Field(snowflake)
    user = Field(User)
    member = Field(GuildMember)


class GuildScheduledEvent(SlottedModel):
    id = Field(snowflake)
    guild_id = Field(snowflake)
    channel_id = Field(snowflake)
    creator_id = Field(snowflake)
    name = Field(text)
    description = Field(text)
    scheduled_start_time = Field(datetime)
    scheduled_end_time = Field(datetime)
    privacy_level = Field(enum(GuildScheduledEventPrivacyLevel))
    status = Field(enum(GuildScheduledEventStatus))
    entity_type = Field(enum(GuildScheduledEventEntityTypes))
    entity_id = Field(snowflake)
    entity_metadata = Field(GuildScheduledEventEntityMetadata)
    creator = Field(User)
    user_count = Field(int)
    image = Field(text)

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)

    def image_url(self, format="webp"):
        if self.image:
            return f"https://cdn.discordapp.com/guild-events/{self.id}/{self.image}.{format}"
        else:
            return None


class GuildVoiceState(VoiceState):
    member = Field(GuildMember)


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
        All guild members.
    channels : dict(snowflake, :class:`disco.types.channel.Channel`)
        All guild channels.
    roles : dict(snowflake, :class:`Role`)
        All guild roles.
    emojis : dict(snowflake, :class:`GuildEmoji`)
        All guild emojis.
    voice_states : dict(str, :class:`disco.types.voice.VoiceState`)
        All guild voice states.
    premium_tier : int
        Guild's premium tier.
    premium_subscription_count : int
        The amount of users using their Nitro boosts on this guild.
    """
    id = Field(snowflake)
    name = Field(text)
    icon = Field(text)
    icon_hash = Field(text)
    splash = Field(text)
    discovery_splash = Field(text)
    owner = Field(bool)
    owner_id = Field(snowflake)
    permissions = Field(PermissionValue)
    afk_channel_id = Field(snowflake)
    afk_timeout = Field(int)
    widget_enabled = Field(bool)
    widget_channel_id = Field(snowflake)
    verification_level = Field(enum(VerificationLevel))
    default_message_notifications = Field(enum(DefaultMessageNotificationsLevel))
    explicit_content_filter = Field(enum(ExplicitContentFilterLevel))
    roles = AutoDictField(Role, 'id')
    emojis = AutoDictField(GuildEmoji, 'id')
    features = ListField(str)
    mfa_level = Field(enum(MFALevel))
    application_id = Field(snowflake)
    system_channel_id = Field(snowflake)
    system_channel_flags = Field(SystemChannelFlagValue)
    rules_channel_id = Field(snowflake)
    max_presences = Field(int)  # deprecated
    max_members = Field(int)
    vanity_url_code = Field(text)
    description = Field(text)
    banner = Field(text)
    premium_tier = Field(enum(PremiumTier))
    premium_subscription_count = Field(int, default=0)
    preferred_locale = Field(text)
    public_updates_channel_id = Field(snowflake)
    max_video_channel_users = Field(int)
    max_stage_video_channel_users = Field(int)
    approximate_member_count = Field(int)
    approximate_presence_count = Field(int)
    welcome_screen = Field(WelcomeScreen)
    nsfw_level = Field(enum(GuildNSFWLevel))
    stickers = AutoDictField(Sticker, 'id')
    premium_progress_bar_enabled = Field(bool)
    safety_alerts_channel_id = Field(snowflake)
    joined_at = Field(datetime)
    large = Field(bool)
    unavailable = Field(bool, default=False)
    member_count = Field(int)
    voice_states = AutoDictField(GuildVoiceState, 'session_id')
    members = AutoDictField(GuildMember, 'id')
    channels = AutoDictField(Channel, 'id')
    threads = AutoDictField(Thread, 'id')
    # presences = AutoDictField(Presence, 'status')
    stage_instances = AutoDictField(StageInstance, 'id')
    latest_onboarding_question_id = Field(snowflake)
    lazy = Field(bool)
    guild_scheduled_events = AutoDictField(GuildScheduledEvent, 'id')
    # embedded_activities = ListField(None)
    home_header = Field(text)
    hub_type = Field(text)
    # application_command_counts = Field(None)
    soundboard_sounds = AutoDictField(GuildSoundboardSound, 'sound_id')
    inventory_settings = Field(text)
    incidents_data = Field(text)
    version = Field(int)

    def __init__(self, *args, **kwargs):
        super(Guild, self).__init__(*args, **kwargs)

        self.attach(self.channels.values(), {'guild_id': self.id})
        self.attach(self.threads.values(), {'guild_id': self.id})
        self.attach(self.members.values(), {'guild_id': self.id})
        self.attach(self.roles.values(), {'guild_id': self.id})
        self.attach(self.emojis.values(), {'guild_id': self.id})
        self.attach(self.stickers.values(), {'guild_id': self.id})
        self.attach(self.voice_states.values(), {'guild_id': self.id})

    def __repr__(self):
        return f'<Guild id={self.id}{" name={}".format(self.name) if self.name else ""}>'

    def __str__(self):
        return self.name if self.name else self.id

    def __int__(self):
        return self.id

    @cached_property
    def owner(self):
        return self.members.get(self.owner_id)

    def get_commands(self):
        return self.client.api.applications_guild_commands_get(self.id)

    def register_command(self, name, description, options=None, default_permission=None):
        data = {}
        data['name'] = name
        data['description'] = description
        data['options'] = options
        data['default_permission'] = default_permission
        return self.client.api.applications_guild_commands_create(self.id, name, data)

    def update_command(self, command_id, name, description, options=None, default_permission=None):
        data = {}
        data['name'] = name
        data['description'] = description
        data['options'] = options
        data['default_permission'] = default_permission
        return self.client.api.applications_guild_commands_modify(self.id, command_id, data)

    def delete_command(self, command_id):
        return self.client.api.applications_guild_commands_delete(self.id, command_id)

    def delete_commands_all(self):
        return self.client.api.applications_guild_commands_bulk_overwrite(self.id, [])

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
        ## account for Discord's API being a complete knob on role deletion
        for role in map(self.roles.get, member.roles + [self.id]):
            if role is not None and hasattr(role, 'permissions'):
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

    def request_guild_members(self, query=None, limit=0, presences=True):
        self.client.gw.request_guild_members(self.id, query, limit, presences)

    def request_guild_members_by_id(self, user_id, limit=0, presences=True):
        self.client.gw.request_guild_members_by_id(self.id, user_id, limit, presences)

    def get_bans(self):
        return self.client.api.guilds_bans_list(self.id)

    def get_ban(self, user):
        return self.client.api.guilds_bans_get(self.id, user)

    def delete_ban(self, user, **kwargs):
        self.client.api.guilds_bans_delete(self.id, to_snowflake(user), **kwargs)

    def create_ban(self, user, *args, **kwargs):
        self.client.api.guilds_bans_create(self.id, to_snowflake(user), *args, **kwargs)

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

    def get_icon_url(self, fmt=None, size=1024):
        if not self.icon:
            return ''

        if not fmt:
            fmt = 'gif' if self.icon.startswith('a_') else 'webp'
        elif fmt == 'gif' and not self.icon.startswith('a_'):
            fmt = 'webp'

        return 'https://cdn.discordapp.com/icons/{}/{}.{}?size={}'.format(self.id, self.icon, fmt, size)

    def get_vanity_url(self):
        if not self.vanity_url_code:
            return ''

        return 'https://discord.gg/' + self.vanity_url_code

    def get_splash_url(self, fmt=None, size=1024):
        if not self.splash:
            return ''

        if not fmt:
            fmt = 'gif' if self.splash.startswith('a_') else 'webp'
        elif fmt == 'gif' and not self.splash.startswith('a_'):
            fmt = 'webp'

        return 'https://cdn.discordapp.com/splashes/{}/{}.{}?size={}'.format(self.id, self.splash, fmt, size)

    def get_banner_url(self, fmt=None, size=1024):
        if not self.banner:
            return ''

        if not fmt:
            fmt = 'gif' if self.banner.startswith('a_') else 'webp'
        elif fmt == 'gif' and not self.banner.startswith('a_'):
            fmt = 'webp'

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


class AuditLogActionTypes:
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
    STAGE_INSTANCE_CREATE = 83
    STAGE_INSTANCE_UPDATE = 84
    STAGE_INSTANCE_DELETE = 85
    STICKER_CREATE = 90
    STICKER_UPDATE = 91
    STICKER_DELETE = 92
    GUILD_SCHEDULED_EVENT_CREATE = 100
    GUILD_SCHEDULED_EVENT_UPDATE = 101
    GUILD_SCHEDULED_EVENT_DELETE = 102
    THREAD_CREATE = 110
    THREAD_UPDATE = 111
    THREAD_DELETE = 112
    APPLICATION_COMMAND_PERMISSION_UPDATE = 121
    AUTO_MODERATION_RULE_CREATE = 140
    AUTO_MODERATION_RULE_UPDATE = 141
    AUTO_MODERATION_RULE_DELETE = 142
    AUTO_MODERATION_BLOCK_MESSAGE = 143
    AUTO_MODERATION_FLAG_TO_CHANNEL = 144
    AUTO_MODERATION_USER_COMMUNICATION_DISABLED = 145
    CREATOR_MONETIZATION_REQUEST_CREATED = 150
    CREATOR_MONETIZATION_TERMS_ACCEPTED = 151


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
    new_value = Field(text)
    old_value = Field(text)
    key = Field(text)


class AuditLogOptionalEntryInfo(SlottedModel):
    application_id = Field(snowflake)
    auto_moderation_rule_name = Field(text)
    auto_moderation_rule_trigger_type = Field(text)
    channel_id = Field(snowflake)
    count = Field(text)
    delete_member_days = Field(text)
    id = Field(snowflake)
    members_removed = Field(text)
    message_id = Field(snowflake)
    role_name = Field(text)
    type = Field(text)
    integration_type = Field(text)


class AuditLogEntry(SlottedModel):
    target_id = Field(snowflake)
    changes = ListField(AuditLogObjectChange)
    user_id = Field(snowflake)
    id = Field(snowflake)
    action_type = Field(enum(AuditLogActionTypes))
    options = Field(AuditLogOptionalEntryInfo)
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


class AuditLogChangeKey(SlottedModel):
    name = Field(text)  # any
    description = Field(text)  # Guild or Sticker
    icon_hash = Field(text)  # Guild
    splash_hash = Field(text)  # Guild
    discovery_splash_hash = Field(text)  # Guild
    banner_hash = Field(text)  # Guild
    owner_id = Field(snowflake)  # Guild
    region = Field(text)  # Guild
    preferred_locale = Field(text)  # Guild
    afk_channel_id = Field(snowflake)  # Guild
    afk_timeout = Field(int)  # Guild
    rules_channel_id = Field(snowflake)  # Guild
    public_updates_channel_id = Field(snowflake)  # Guild
    mfa_level = Field(int)  # Guild
    verification_level = Field(int)  # Guild
    explicit_content_filter = Field(int)  # Guild
    default_message_notifications = Field(int)  # Guild
    vanity_url_code = Field(text)  # Guild
    _add = ListField(Role)  # Guild
    _remove = ListField(Role)  # Guild
    prune_delete_days = Field(int)  # Guild
    widget_enabled = Field(bool)  # Guild
    widget_channel_id = Field(snowflake)  # Guild
    system_channel_id = Field(snowflake)  # Guild
    position = Field(int)  # Channel
    topic = Field(text)  # Channel or StageInstance
    bitrate = Field(int)  # Channel
    overwrites = AutoDictField(PermissionOverwrite, 'id', alias='permission_overwrites')  # Channel
    nsfw = Field(bool)  # Channel
    application_id = Field(snowflake)  # Channel
    rate_limit_per_user = Field(int)  # Channel
    permissions = Field(PermissionValue)  # Role
    color = Field(int)  # Role
    hoist = Field(bool)  # Role
    mentionable = Field(bool)  # Role
    allow = Field(text)  # Role
    deny = Field(text)  # Role
    code = Field(text)  # Invite
    channel_id = Field(snowflake)  # Invite
    inviter_id = Field(snowflake)  # Invite
    max_uses = Field(int)  # Invite
    uses = Field(int)  # Invite
    max_age = Field(int)  # Invite
    temporary = Field(bool)  # Invite
    deaf = Field(bool)  # User
    mute = Field(bool)  # User
    nick = Field(text)  # User
    avatar_hash = Field(text)  # User
    id = Field(snowflake)  # any
    type = Field(text)  # any
    enable_emoticons = Field(bool)  # Integration
    expire_behavior = Field(int)  # Integration
    expire_grace_period = Field(int)  # Integration
    user_limit = Field(int)  # Channel (Voice)
    privacy_level = Field(StageInstancePrivacyLevel)  # StageInstance
    tags = Field(text)  # Sticker
    format_type = Field(StickerFormatTypes)  # Sticker
    asset = Field(text)  # Sticker
    available = Field(bool)  # Sticker
    guild_id = Field(snowflake)  # Sticker
    archived = Field(bool)  # Channel (Thread)
    locked = Field(bool)  # Channel (Thread)
    auto_archive_duration = Field(int)  # Channel (Thread)
    default_auto_archive_duration = Field(int)  # Channel


class AuditLog(SlottedModel):
    webhooks = ListField(Webhook)
    users = ListField(User)
    audit_log_entries = ListField(AuditLogEntry)
    integrations = ListField(Integration)
    threads = ListField(Thread)


class DiscoveryRequirementsHealthScore(SlottedModel):
    avg_nonnew_communicators = Field(int)
    avg_nonnew_participators = Field(int)
    num_intentful_joiners = Field(int)
    perc_ret_w1_intentful = Field(float)


class DiscoveryRequirements(SlottedModel):
    age = Field(bool)
    engagement_healthy = Field(bool, default=False)
    grace_period_end_date = Field(datetime)
    guild_id = Field(snowflake)
    health_score = Field(DiscoveryRequirementsHealthScore)
    health_score_pending = Field(bool)
    healthy = Field(bool, default=False)
    minimum_age = Field(int)
    minimum_size = Field(int)
    nsfw_properties = Field(dict)
    protected = Field(bool)
    retention_healthy = Field(bool)
    safe_environment = Field(bool)
    size = Field(bool)
    sufficient = Field(bool)
    sufficient_without_grace_period = Field(bool)
    valid_rules_channel = Field(bool)


class DiscoveryCategoryName(SlottedModel):
    default = Field(text)
    # localizations = Field


class DiscoveryCategory(SlottedModel):
    id = Field(int)
    name = Field(DiscoveryCategoryName)
    is_primary = Field(bool)


class DiscoveryGuild(SlottedModel):
    guild_id = Field(snowflake)
    primary_category_id = Field(text)
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


class AutoModerationEventTypes:
    MESSAGE_SEND = 1


class AutoModerationActionTypes:
    BLOCK_MESSAGE = 1
    SEND_ALERT_MESSAGE = 2
    TIMEOUT = 3


class AutoModerationActionMetadata(SlottedModel):
    channel_id = Field(snowflake)
    duration_seconds = Field(int)
    custom_message = Field(text)


class AutoModerationAction(SlottedModel):
    type = Field(enum(AutoModerationActionTypes))
    metadata = Field(AutoModerationActionMetadata)


class AutoModerationKeywordPresetTypes:
    PROFANITY = 1
    SEXUAL_CONTENT = 2
    SLURS = 3


class AutoModerationTriggerTypes:
    KEYWORD = 1
    SPAM = 2
    KEYWORD_PRESET = 3
    MENTION_SPAM = 4


class AutoModerationTriggerMetadata(SlottedModel):
    keyword_filter = ListField(text)
    regex_patterns = ListField(text)
    presets = ListField(enum(AutoModerationKeywordPresetTypes))
    allow_list = ListField(text)
    mention_total_limit = Field(int)
    mention_raid_protection_enabled = Field(bool)


class AutoModerationRule(SlottedModel):
    id = Field(snowflake)
    guild_id = Field(snowflake)
    name = Field(text)
    creator_id = Field(snowflake)
    event_type = Field(enum(AutoModerationEventTypes))
    trigger_type = Field(enum(AutoModerationTriggerTypes))
    trigger_metadata = Field(AutoModerationTriggerMetadata)
    actions = ListField(AutoModerationAction)
    enabled = Field(bool)
    exempt_roles = ListField(snowflake)
    exempt_channels = ListField(snowflake)


class AutoModerationActionExecute(SlottedModel):
    guild_id = Field(snowflake)
    action = Field(AutoModerationAction)
    rule_id = Field(snowflake)
    rule_trigger_type = Field(enum(AutoModerationTriggerTypes))
    user_id = Field(snowflake)
    channel_id = Field(snowflake)
    message_id = Field(snowflake)
    alert_system_message_id = Field(snowflake)
    content = Field(text)
    matched_keyword = Field(text)
    matched_content = Field(text)


class GuildEntitlementTypes:
    APPLICATION_SUBSCRIPTION = 8


class GuildEntitlement(SlottedModel):
    id = Field(snowflake)
    sku_id = Field(snowflake)
    application_id = Field(snowflake)
    user_id = Field(snowflake)
    type = Field(enum(GuildEntitlementTypes))
    deleted = Field(bool)
    starts_at = Field(datetime)
    ends_at = Field(datetime)
    guild_id = Field(snowflake)
