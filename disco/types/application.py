from disco.types.base import SlottedModel, Field, snowflake, text, enum, ListField, cached_property, DictField, \
    str_or_int, BitsetMap, BitsetValue, datetime
from disco.types.channel import Channel, ChannelType
from disco.types.guild import GuildMember, Role, Guild
from disco.types.message import MessageEmbed, AllowedMentions, Message, MessageAttachment, component, MessageFlags, \
    MessagePoll, MessageFlagValue
from disco.types.permissions import PermissionValue
from disco.types.reactions import Emoji
from disco.types.user import User
from disco.util.paginator import Paginator
from disco.util.snowflake import to_snowflake


class ApplicationCommandOptionType:
    SUB_COMMAND = 1
    SUB_COMMAND_GROUP = 2
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8
    MENTIONABLE = 9
    NUMBER = 10
    ATTACHMENT = 11


class ApplicationCommandTypes:
    CHAT_INPUT = 1
    USER = 2
    MESSAGE = 3


class ApplicationCommandOptionChoice(SlottedModel):
    name = Field(text)
    name_localizations = DictField(str, str)
    value = Field(str_or_int)


class _ApplicationCommandOption(SlottedModel):
    type = Field(enum(ApplicationCommandOptionType))
    name = Field(text)
    name_localizations = DictField(str, str)
    description = Field(text)
    description_localizations = DictField(str, str)
    required = Field(bool)
    choices = ListField(ApplicationCommandOptionChoice)
    channel_types = ListField(enum(ChannelType))
    min_value = Field(int)
    max_value = Field(int)
    min_length = Field(int)
    max_length = Field(int)
    autocomplete = Field(bool)


class ApplicationCommandOption(_ApplicationCommandOption):
    options = ListField(_ApplicationCommandOption)


class InteractionDataResolved(SlottedModel):
    users = DictField(snowflake, User)
    members = DictField(snowflake, GuildMember)
    roles = DictField(snowflake, Role)
    channels = DictField(snowflake, Channel)
    messages = DictField(snowflake, Message)
    attachments = DictField(snowflake, MessageAttachment)


def interaction_option(data):
    return InteractionDataOption.create(data=data, client=None)


class InteractionDataOption(SlottedModel):
    options = ListField(interaction_option, create=False)
    name = Field(text)
    type = Field(int)
    value = Field(str_or_int)
    focused = Field(bool)


class InteractionData(SlottedModel):
    id = Field(snowflake)
    name = Field(text)
    type = Field(enum(ApplicationCommandTypes))
    resolved = Field(InteractionDataResolved, create=False)
    options = ListField(interaction_option, create=False)
    custom_id = Field(text)
    component_type = Field(int)
    values = ListField(text, create=False)
    target_id = Field(snowflake)
    guild_id = Field(snowflake)
    components = ListField(component, create=False)


class ApplicationCommand(SlottedModel):
    id = Field(snowflake)
    type = Field(enum(ApplicationCommandTypes))
    application_id = Field(snowflake)
    guild_id = Field(snowflake)
    name = Field(text)
    name_localizations = DictField(str, str)
    description = Field(text)
    description_localizations = DictField(str, str)
    options = ListField(ApplicationCommandOption)
    default_member_permissions = Field(int)
    dm_permissions = Field(bool)
    nsfw = Field(bool)
    version = Field(snowflake)


class ApplicationCommandPermissionType:
    ROLE = 1
    USER = 2
    CHANNEL = 3


class ApplicationCommandPermissions(SlottedModel):
    id = Field(snowflake)
    type = Field(enum(ApplicationCommandPermissionType))
    permission = Field(bool)


class EntitlementType:
    PURCHASE = 1
    PREMIUM_SUBSCRIPTION = 2
    DEVELOPER_GIFT = 3
    TEST_MODE_PURCHASE = 4
    FREE_PURCHASE = 5
    USER_GIFT = 6
    PREMIUM_PURCHASE = 7
    APPLICATION_SUBSCRIPTION = 8


class Entitlement(SlottedModel):
    id = Field(snowflake)
    sku_id = Field(snowflake)
    application_id = Field(snowflake)
    user_id = Field(snowflake)
    type = Field(enum(EntitlementType))
    deleted = Field(bool)
    starts_at = Field(datetime)
    ends_at = Field(datetime)
    guild_id = Field(snowflake)
    consumed = Field(bool)


class GuildApplicationCommandPermissions(SlottedModel):
    id = Field(snowflake)
    application_id = Field(snowflake)
    guild_id = Field(snowflake)
    permissions = ListField(ApplicationCommandPermissions)


class InteractionType:
    PING = 1
    APPLICATION_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4
    MODAL_SUBMIT = 5


class InteractionContextType:
    GUILD = 0
    BOT_DM = 1
    PRIVATE_CHANNEL = 2


class Interaction(SlottedModel):
    id = Field(snowflake)
    application_id = Field(snowflake)
    type = Field(enum(InteractionType))
    data = Field(InteractionData)
    guild_id = Field(snowflake)
    guild = Field(Guild, create=False)
    channel = Field(Channel)
    channel_id = Field(snowflake)
    member = Field(GuildMember, create=False)
    user = Field(User, create=False)
    token = Field(text)
    version = Field(int)
    message = Field(Message, create=False)
    app_permissions = Field(PermissionValue)
    locale = Field(text)
    guild_locale = Field(text)
    entitlements = ListField(Entitlement)
    entitlement_sku_ids = ListField(int)
    authorizing_integration_owners = DictField(text, int)
    context = Field(enum(InteractionContextType))
    attachment_size_limit = Field(int)

    def __repr__(self):
        return '<Interaction id={} channel_id={}>'.format(self.id, self.channel_id)

    def __int__(self):
        return self.id

    # TODO: REMOVE. Interaction object gives a partial channel and partial guild object. Depending on context and use case, you won't be able to pull these from state OR the api.
    # @cached_property
    # def channel(self):
    #     if self.guild_id:
    #         if self.channel_id in self.client.state.threads:
    #             return self.client.state.threads.get(self.channel_id)
    #         elif self.channel_id in self.client.state.channels:
    #             return self.client.state.channels.get(self.channel_id)
    #     elif self.channel_id in self.client.state.dms:
    #         return self.client.state.dms[self.channel_id]
    #     elif self.context == InteractionContextType.PRIVATE_CHANNEL:
    #         return self._channel
    #     return self.client.api.channels_get(self.channel_id)

    @cached_property
    def thread(self):
        if self.channel_id in self.client.state.threads:
            return self.client.state.threads.get(self.channel_id)

    # TODO: REMOVE. Interaction object gives a partial channel and partial guild object. Depending on context and use case, you won't be able to pull these from state OR the api.
    # @cached_property
    # def guild(self):
    #     if self.context != InteractionContextType.GUILD:
    #         return
    #     if self.channel.is_dm:
    #         return
    #     if self.guild_id:
    #         return self.client.state.guilds.get(self.guild_id)
    #     elif self.channel and self.channel.guild:
    #         return self.channel.guild

    def pin(self):
        return self.channel.create_pin(self)

    def unpin(self):
        return self.channel.delete_pin(self)

    def reply(self, type=4, choices=None, modal=None, *args, **kwargs):
        if type == InteractionCallbackType.MODAL:
            if not modal:
                raise Exception("Modal not passed to method.")
            if isinstance(modal, dict):
                return self.client.api.interactions_create(self.id, self.token, type, data=modal)
            else:
                return self.client.api.interactions_create(self.id, self.token, type, data=modal.to_dict())
        elif type == InteractionCallbackType.APPLICATION_COMMAND_AUTOCOMPLETE_RESULT:

            if not choices:
                raise Exception("Choices not passed to method.")
            parsed = []
            for choice in choices:
                if isinstance(choice, dict):
                    parsed.append(choice)
                else:
                    parsed.append(choice.to_dict())

            return self.client.api.interactions_create(self.id, self.token, type, data={"choices": parsed})
        else:
            return self.client.api.interactions_create_reply(self.id, self.token, type=type, *args, **kwargs)

    def followup(self, *args, **kwargs):
        return self.client.api.interactions_followup_create(self.token, *args, **kwargs)

    def reply_modal(self, modal):
        raise Exception("Deprecated: Please use event.reply(type=InteractionCallbackType.MODAL, modal=MODAL)")

    def reply_autocomplete(self, choices):
        raise Exception("Deprecated: Please use event.reply(type=InteractionCallbackType.APPLICATION_COMMAND_AUTOCOMPLETE_RESULT, choices=[CHOICES])")

    def edit(self, *args, **kwargs):
        return self.client.api.interactions_edit_reply(self.client.state.me.id, self.token, *args, **kwargs)

    def delete(self):
        return self.client.api.interactions_delete_reply(self.client.state.me.id, self.token)

    def get_reactors(self, emoji, *args, **kwargs):
        if isinstance(emoji, Emoji):
            emoji = emoji.to_string()

        return Paginator(
            self.client.api.channels_messages_reactions_get,
            'after',
            self.channel.id,
            self.id,
            emoji,
            *args,
            **kwargs)

    def add_reaction(self, emoji):
        if isinstance(emoji, Emoji):
            emoji = emoji.to_string()

        self.client.api.channels_messages_reactions_create(self.channel_id, self.id, emoji)

    def delete_reaction(self, emoji, user=None):
        if isinstance(emoji, Emoji):
            emoji = emoji.to_string()

        if user:
            user = to_snowflake(user)

        self.client.api.channels_messages_reactions_delete(self.channel_id, self.id, emoji, user)

    def delete_single_reaction(self, emoji):
        if isinstance(emoji, Emoji):
            emoji = emoji.to_string()

        self.client.api.channels_messages_reactions_delete_emoji(self.channel_id, self.id, emoji)

    def delete_all_reactions(self):
        self.client.api.channels_messages_reactions_delete_all(self.channel_id, self.id)


class InteractionCallbackType:
    PONG = 1
    # ACKNOWLEDGE = 2  # DEPRECATED
    # CHANNEL_MESSAGE = 3  # DEPRECATED
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6
    UPDATE_MESSAGE = 7
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8
    MODAL = 9
    PREMIUM_REQUIRED = 10
    LAUNCH_ACTIVITY = 12


class InteractionCallbackData(SlottedModel):
    tts = Field(bool)
    content = Field(text)
    embeds = ListField(MessageEmbed)
    allowed_mentions = Field(AllowedMentions)
    flags = Field(MessageFlagValue)
    components = ListField(component)
    attachments = ListField(MessageAttachment)
    poll = Field(MessagePoll)

class InteractionResponse(Interaction):
    type = Field(enum(InteractionCallbackType))
    data = Field(InteractionCallbackData)

    def __repr__(self):
        return '<InteractionResponse id={} channel_id={}>'.format(self.id, self.channel_id)

    def __int__(self):
        return self.id


class InteractionFollowupMessage(Message):
    token = Field(text)

    def edit(self, *args, **kwargs):
        self.client.api.interactions_followup_edit(self.token, self.id, *args, **kwargs)

    def delete(self, *args, **kwargs):
        self.client.api.interactions_followup_delete(self.token, self.id)

