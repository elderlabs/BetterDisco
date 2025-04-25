from disco.types.application import ApplicationCommand
from disco.types.automoderation import AutoModerationRule
from disco.types.base import SlottedModel, text, Field, snowflake, ListField, enum, cached_property, AutoDictField
from disco.types.channel import PermissionOverwrite, StageInstancePrivacyLevel, Thread
from disco.types.guild import Role, GuildScheduledEvent
from disco.types.integration import Integration
from disco.types.permissions import PermissionValue
from disco.types.reactions import StickerFormatTypes
from disco.types.user import User
from disco.types.webhook import Webhook


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
    SOUNDBOARD_SOUND_CREATE = 130
    SOUNDBOARD_SOUND_UPDATE = 131
    SOUNDBOARD_SOUND_DELETE = 132
    AUTO_MODERATION_RULE_CREATE = 140
    AUTO_MODERATION_RULE_UPDATE = 141
    AUTO_MODERATION_RULE_DELETE = 142
    AUTO_MODERATION_BLOCK_MESSAGE = 143
    AUTO_MODERATION_FLAG_TO_CHANNEL = 144
    AUTO_MODERATION_USER_COMMUNICATION_DISABLED = 145
    CREATOR_MONETIZATION_REQUEST_CREATED = 150
    CREATOR_MONETIZATION_TERMS_ACCEPTED = 151
    ONBOARDING_PROMPT_CREATE = 163
    ONBOARDING_PROMPT_UPDATE = 164
    ONBOARDING_PROMPT_DELETE = 165
    ONBOARDING_CREATE = 166
    ONBOARDING_UPDATE = 167
    HOME_SETTINGS_CREATE = 190
    HOME_SETTINGS_UPDATE = 191


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
    application_commands = ListField(ApplicationCommand)
    audit_log_entries = ListField(AuditLogEntry)
    auto_moderation_rules = ListField(AutoModerationRule)
    guild_scheduled_events = ListField(GuildScheduledEvent)
    integrations = ListField(Integration)
    threads = ListField(Thread)
    users = ListField(User)
    webhooks = ListField(Webhook)