from disco.types.base import SlottedModel, Field, ListField, snowflake, text, enum, DictField, BitsetMap, BitsetValue
from disco.types.permissions import PermissionValue
from disco.util.snowflake import to_snowflake
from disco.types.user import User


class TeamMembershipState:
    INVITED = 1
    ACCEPTED = 2


class TeamMember(SlottedModel):
    membership_state = Field(enum(TeamMembershipState))
    team_id = Field(snowflake)
    user = Field(User)
    role = Field(text)


class Team(SlottedModel):
    icon = Field(text)
    id = Field(snowflake)
    members = ListField(TeamMember)
    name = Field(text)
    owner_user_id = Field(snowflake)


class ApplicationInstallParams(SlottedModel):
    scopes = ListField(str)
    permissions = Field(PermissionValue)


class ApplicationFlags(BitsetMap):
    APPLICATION_AUTO_MODERATION_RULE_CREATE_BADGE = 1 << 6
    GATEWAY_PRESENCE = 1 << 12
    GATEWAY_PRESENCE_LIMITED = 1 << 13
    GATEWAY_GUILD_MEMBERS = 1 << 14
    GATEWAY_GUILD_MEMBERS_LIMITED = 1 << 15
    VERIFICATION_PENDING_GUILD_LIMIT = 1 << 16
    EMBEDDED = 1 << 17
    GATEWAY_MESSAGE_CONTENT = 1 << 18
    GATEWAY_MESSAGE_CONTENT_LIMITED = 1 << 19
    APPLICATION_COMMAND_BADGE = 1 << 23


class ApplicationFlagsValue(BitsetValue):
    map = ApplicationFlags


class Application(SlottedModel):
    id = Field(snowflake)
    name = Field(text)
    icon = Field(text)
    description = Field(text)
    rpc_origins = ListField(str)
    bot_public = Field(bool)
    bot_require_code_grant = Field(bool)
    bot = Field(User)
    terms_of_service_url = Field(text)
    privacy_policy_url = Field(text)
    owner = Field(User)
    verify_key = Field(text)
    team = Field(Team)
    guild_id = Field(snowflake)
    # guild = Field(Guild)  # cyclical import
    primary_sku_id = Field(snowflake)
    slug = Field(text)
    cover_image = Field(text)
    flags = Field(ApplicationFlagsValue)
    approximate_guild_count = Field(int)
    redirect_uris = ListField(str)
    interactions_endpoint_url = Field(str)
    role_connections_verification_url = Field(str)
    tags = ListField(str)
    install_params = Field(ApplicationInstallParams)
    custom_install_url = Field(str)

    def user_is_owner(self, user):
        user_id = to_snowflake(user)
        if user_id == self.owner.id:
            return True

        return any(user_id == member.user.id for member in self.team.members)

    def get_icon_url(self, fmt=None, size=1024):
        if not self.icon:
            return ''

        if not fmt:
            fmt = 'gif' if self.icon.startswith('a_') else 'webp'
        elif fmt == 'gif' and not self.icon.startswith('a_'):
            fmt = 'webp'

        return 'https://cdn.discordapp.com/icons/{}/{}.{}?size={}'.format(self.id, self.icon, fmt, size)

    def get_cover_image_url(self, fmt=None, size=1024):
        if not self.cover_image:
            return ''

        if not fmt:
            fmt = 'gif' if self.cover_image.startswith('a_') else 'webp'
        elif fmt == 'gif' and not self.cover_image.startswith('a_'):
            fmt = 'webp'

        return 'https://cdn.discordapp.com/app-icons/{}/{}.{}?size={}'.format(self.id, self.cover_image, fmt, size)

    @property
    def icon_url(self):
        return self.get_icon_url()

    @property
    def cover_image_url(self):
        return self.get_cover_image_url()


class ApplicationRoleConnectionMetadataType:
    INTEGER_LESS_THAN_OR_EQUAL = 1
    INTEGER_GREATER_THAN_OR_EQUAL = 2
    INTEGER_EQUAL = 3
    INTEGER_NOT_EQUAL = 4
    DATETIME_LESS_THAN_OR_EQUAL = 5
    DATETIME_GREATER_THAN_OR_EQUAL = 6
    BOOLEAN_EQUAL = 7
    BOOLEAN_NOT_EQUAL = 8


class ApplicationRoleConnectionMetadata(SlottedModel):
    type = Field(ApplicationRoleConnectionMetadataType)
    key = Field(str)
    name = Field(str)
    name_localizations = DictField(str, str)
    description = Field(str)
    description_localizations = DictField(str, str)


class ApplicationRoleConnection(SlottedModel):
    platform_name = Field(text)
    platform_username = Field(text)
    metadata = Field(ApplicationRoleConnectionMetadata)
