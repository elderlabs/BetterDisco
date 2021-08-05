from disco.types.base import SlottedModel, Field, ListField, snowflake, text, enum
from disco.types.user import User
from disco.util.snowflake import to_snowflake


class TeamMembershipState(object):
    INVITED = 1
    ACCEPTED = 2


class TeamMember(SlottedModel):
    membership_state = Field(enum(TeamMembershipState))
    permissions = Field(text)
    team_id = Field(snowflake)
    user = Field(User)


class Team(SlottedModel):
    icon = Field(str)
    id = Field(snowflake)
    members = ListField(TeamMember)
    name = Field(str)
    owner_user_id = Field(snowflake)


class ApplicationFlags(object):
    NONE = 0
    GATEWAY_PRESENCE = 1 << 12
    GATEWAY_PRESENCE_LIMITED = 1 << 13
    GATEWAY_GUILD_MEMBERS = 1 << 14
    GATEWAY_GUILD_MEMBERS_LIMITED = 1 << 15
    VERIFICATION_PENDING_GUILD_LIMIT = 1 << 16
    EMBEDDED = 1 << 17


class Application(SlottedModel):
    id = Field(snowflake)
    name = Field(str)
    icon = Field(str)
    description = Field(str)
    rpc_origins = ListField(str)
    bot_public = Field(bool)
    bot_require_code_grant = Field(bool)
    terms_of_service_url = Field(str)
    privacy_policy_url = Field(str)
    owner = Field(User)
    summary = Field(str)
    verify_key = Field(str)
    team = Field(Team)
    guild_id = Field(snowflake)
    primary_sku_id = Field(snowflake)
    slug = Field(str)
    cover_image = Field(str)
    flags = Field(int)

    def user_is_owner(self, user):
        user_id = to_snowflake(user)
        if user_id == self.owner.id:
            return True

        return any(user_id == member.user.id for member in self.team.members)

    def get_icon_url(self, fmt='webp', size=1024):
        if not self.icon:
            return ''

        return 'https://cdn.discordapp.com/app-icons/{}/{}.{}?size={}'.format(self.id, self.icon, fmt, size)

    def get_cover_image_url(self, fmt='webp', size=1024):
        if not self.cover_image:
            return ''

        return 'https://cdn.discordapp.com/app-icons/{}/{}.{}?size={}'.format(self.id, self.cover_image, fmt, size)

    @property
    def icon_url(self):
        return self.get_icon_url()

    @property
    def cover_image_url(self):
        return self.get_cover_image_url()
