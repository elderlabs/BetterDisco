import six
import json
import warnings

from contextlib import contextmanager
from gevent.local import local
from six.moves.urllib.parse import quote

from disco.api.http import Routes, HTTPClient, to_bytes
from disco.util.logging import LoggingClass
from disco.util.sanitize import S
from disco.types.user import User
from disco.types.message import Message
from disco.types.oauth import Application, Connection
from disco.types.guild import (
    Guild, GuildMember, GuildBan, GuildEmbed, PruneCount, Role, GuildEmoji,
    AuditLogEntry, Integration,
)
from disco.types.channel import Channel
from disco.types.invite import Invite
from disco.types.voice import VoiceRegion
from disco.types.webhook import Webhook


def optional(**kwargs):
    """
    Takes a set of keyword arguments, creating a dictionary with only the non-
    null values.

    :returns: dict
    """
    return {k: v for k, v in six.iteritems(kwargs) if v is not None}


def _reason_header(value):
    return optional(**{'X-Audit-Log-Reason': quote(to_bytes(value)) if value else None})


class Responses(list):
    def rate_limited_duration(self):
        return sum(i.rate_limited_duration for i in self)

    @property
    def rate_limited(self):
        return self.rate_limited_duration() != 0


class APIClient(LoggingClass):
    """
    An abstraction over a :class:`disco.api.http.HTTPClient`, which composes
    requests from provided data, and fits models with the returned data. The APIClient
    is the only path to the API used within models/other interfaces, and it's
    the recommended path for all third-party users/implementations.

    Parameters
    ----------
    token : str
        The Discord authentication token (without prefixes) to be used for all
        HTTP requests.
    client : Optional[:class:`disco.client.Client`]
        The Disco client this APIClient is a member of. This is used when constructing
        and fitting models from response data.

    Attributes
    ----------
    client : Optional[:class:`disco.client.Client`]
        The Disco client this APIClient is a member of.
    http : :class:`disco.http.HTTPClient`
        The HTTPClient this APIClient uses for all requests.
    """
    def __init__(self, token, client=None):
        super(APIClient, self).__init__()

        self.client = client
        self.http = HTTPClient(token, self._after_requests)

        self._captures = local()

    def _after_requests(self, response):
        if not hasattr(self._captures, 'responses'):
            return

        self._captures.responses.append(response)

    @contextmanager
    def capture(self):
        """
        Context manager which captures all requests made, returning a special
        `Responses` list, which can be used to introspect raw API responses. This
        method is a low-level utility which should only be used by experienced users.
        """
        responses = Responses()
        self._captures.responses = responses

        try:
            yield responses
        finally:
            delattr(self._captures, 'responses')

    def gateway_get(self):
        data = self.http(Routes.GATEWAY_GET).json()
        return data

    def gateway_bot_get(self):
        data = self.http(Routes.GATEWAY_BOT_GET).json()
        return data

    def oauth2_applications_me_get(self):
        r = self.http(Routes.OAUTH2_APPLICATIONS_ME)
        return Application.create(self.client, r.json())

    def channels_get(self, channel):
        r = self.http(Routes.CHANNELS_GET, dict(channel=channel))
        return Channel.create(self.client, r.json())

    def channels_modify(self, channel, reason=None, **kwargs):
        r = self.http(
            Routes.CHANNELS_MODIFY,
            dict(channel=channel),
            json=kwargs,
            headers=_reason_header(reason))
        return Channel.create(self.client, r.json())

    def channels_delete(self, channel, reason=None):
        r = self.http(
            Routes.CHANNELS_DELETE,
            dict(channel=channel),
            headers=_reason_header(reason))
        return Channel.create(self.client, r.json())

    def channels_typing(self, channel):
        self.http(Routes.CHANNELS_TYPING, dict(channel=channel))

    def channels_messages_list(self, channel, around=None, before=None, after=None, limit=50):
        r = self.http(Routes.CHANNELS_MESSAGES_LIST, dict(channel=channel), params=optional(
            around=around,
            before=before,
            after=after,
            limit=limit,
        ))

        return Message.create_map(self.client, r.json())

    def channels_messages_get(self, channel, message):
        r = self.http(Routes.CHANNELS_MESSAGES_GET, dict(channel=channel, message=message))
        return Message.create(self.client, r.json())

    def channels_messages_create(
            self,
            channel,
            content=None,
            nonce=None,
            tts=False,
            attachment=None,
            attachments=[],
            embed=None,
            sanitize=False):

        payload = {
            'nonce': nonce,
            'tts': tts,
        }

        if attachment:
            attachments = [attachment]
            warnings.warn(
                'attachment kwarg has been deprecated, switch to using attachments with a list',
                DeprecationWarning)

        if content:
            if sanitize:
                content = S(content)
            payload['content'] = content

        if embed:
            payload['embed'] = embed.to_dict()

        if attachments:
            if len(attachments) > 1:
                files = {
                    'file{}'.format(idx): tuple(i) for idx, i in enumerate(attachments)
                }
            else:
                files = {
                    'file': tuple(attachments[0]),
                }

            r = self.http(
                Routes.CHANNELS_MESSAGES_CREATE,
                dict(channel=channel),
                data={'payload_json': json.dumps(payload)},
                files=files,
            )
        else:
            r = self.http(Routes.CHANNELS_MESSAGES_CREATE, dict(channel=channel), json=payload)

        return Message.create(self.client, r.json())

    def channels_messages_modify(self, channel, message, content=None, embed=None, sanitize=False):
        payload = {}

        if content is not None:
            if sanitize:
                content = S(content)
            payload['content'] = content

        if embed:
            payload['embed'] = embed.to_dict()

        r = self.http(Routes.CHANNELS_MESSAGES_MODIFY,
                      dict(channel=channel, message=message),
                      json=payload)
        return Message.create(self.client, r.json())

    def channels_messages_delete(self, channel, message):
        self.http(Routes.CHANNELS_MESSAGES_DELETE, dict(channel=channel, message=message))

    def channels_messages_delete_bulk(self, channel, messages):
        self.http(Routes.CHANNELS_MESSAGES_DELETE_BULK, dict(channel=channel), json={'messages': messages})

    def channels_messages_reactions_get(self, channel, message, emoji, after=None, limit=100):
        r = self.http(
            Routes.CHANNELS_MESSAGES_REACTIONS_GET,
            dict(channel=channel, message=message, emoji=emoji),
            params={'after': after, 'limit': limit})
        return User.create_map(self.client, r.json())

    def channels_messages_reactions_create(self, channel, message, emoji):
        self.http(Routes.CHANNELS_MESSAGES_REACTIONS_CREATE, dict(channel=channel, message=message, emoji=emoji))

    def channels_messages_reactions_delete(self, channel, message, emoji, user=None):
        route = Routes.CHANNELS_MESSAGES_REACTIONS_DELETE_ME
        obj = dict(channel=channel, message=message, emoji=emoji)

        if user:
            route = Routes.CHANNELS_MESSAGES_REACTIONS_DELETE_USER
            obj['user'] = user

        self.http(route, obj)

    def channels_messages_reactions_delete_all(self, channel, message):
        self.http(Routes.CHANNELS_MESSAGES_REACTIONS_DELETE_ALL, dict(channel=channel, message=message))

    def channels_permissions_modify(self, channel, permission, allow, deny, typ, reason=None):
        self.http(Routes.CHANNELS_PERMISSIONS_MODIFY, dict(channel=channel, permission=permission), json={
            'allow': allow,
            'deny': deny,
            'type': typ,
        }, headers=_reason_header(reason))

    def channels_permissions_delete(self, channel, permission, reason=None):
        self.http(
            Routes.CHANNELS_PERMISSIONS_DELETE,
            dict(channel=channel, permission=permission), headers=_reason_header(reason),
        )

    def channels_invites_list(self, channel):
        r = self.http(Routes.CHANNELS_INVITES_LIST, dict(channel=channel))
        return Invite.create_map(self.client, r.json())

    def channels_invites_create(self, channel, max_age=86400, max_uses=0, temporary=False, unique=False, reason=None):
        r = self.http(Routes.CHANNELS_INVITES_CREATE, dict(channel=channel), json={
            'max_age': max_age,
            'max_uses': max_uses,
            'temporary': temporary,
            'unique': unique,
        }, headers=_reason_header(reason))
        return Invite.create(self.client, r.json())

    def channels_pins_list(self, channel):
        r = self.http(Routes.CHANNELS_PINS_LIST, dict(channel=channel))
        return Message.create_map(self.client, r.json())

    def channels_pins_create(self, channel, message):
        self.http(Routes.CHANNELS_PINS_CREATE, dict(channel=channel, message=message))

    def channels_pins_delete(self, channel, message):
        self.http(Routes.CHANNELS_PINS_DELETE, dict(channel=channel, message=message))

    def channels_webhooks_create(self, channel, name=None, avatar=None):
        r = self.http(Routes.CHANNELS_WEBHOOKS_CREATE, dict(channel=channel), json=optional(
            name=name,
            avatar=avatar,
        ))
        return Webhook.create(self.client, r.json())

    def channels_webhooks_list(self, channel):
        r = self.http(Routes.CHANNELS_WEBHOOKS_LIST, dict(channel=channel))
        return Webhook.create_map(self.client, r.json())

    def guilds_get(self, guild):
        r = self.http(Routes.GUILDS_GET, dict(guild=guild))
        return Guild.create(self.client, r.json())

    def guilds_modify(self, guild, reason=None, **kwargs):
        r = self.http(Routes.GUILDS_MODIFY, dict(guild=guild), json=kwargs, headers=_reason_header(reason))
        return Guild.create(self.client, r.json())

    def guilds_delete(self, guild):
        self.http(Routes.GUILDS_DELETE, dict(guild=guild))

    def guilds_create(
            self,
            name,
            region=None,
            icon=None,
            verification_level=None,
            default_message_notifications=None,
            explicit_content_filter=None,
            roles=None,
            channels=None):

        payload = {
            'name': name,
            'roles': (roles or []),
            'channels': (channels or []),
        }

        payload.update(optional(
            region=region,
            icon=icon,
            verification_level=verification_level,
            default_message_notifications=default_message_notifications,
            explicit_content_filter=explicit_content_filter,
        ))

        r = self.http(Routes.GUILDS_CREATE, json=payload)
        return Guild.create(self.client, r.json())

    def guilds_channels_list(self, guild):
        r = self.http(Routes.GUILDS_CHANNELS_LIST, dict(guild=guild))
        return Channel.create_hash(self.client, 'id', r.json(), guild_id=guild)

    def guilds_channels_create(
            self,
            guild,
            channel_type,
            name,
            bitrate=None,
            user_limit=None,
            permission_overwrites=[],
            nsfw=None,
            parent_id=None,
            position=None,
            reason=None):

        payload = {
            'name': name,
            'type': channel_type,
            'permission_overwrites': [i.to_dict() for i in permission_overwrites],
            'parent_id': parent_id,
        }

        payload.update(optional(
            nsfw=nsfw,
            bitrate=bitrate,
            user_limit=user_limit,
            position=position,
        ))

        r = self.http(
            Routes.GUILDS_CHANNELS_CREATE,
            dict(guild=guild),
            json=payload,
            headers=_reason_header(reason))
        return Channel.create(self.client, r.json(), guild_id=guild)

    def guilds_channels_modify(self, guild, channel, position, reason=None):
        self.http(Routes.GUILDS_CHANNELS_MODIFY, dict(guild=guild), json={
            'id': channel,
            'position': position,
        }, headers=_reason_header(reason))

    def guilds_members_list(self, guild, limit=1000, after=None):
        r = self.http(Routes.GUILDS_MEMBERS_LIST, dict(guild=guild), params=optional(
            limit=limit,
            after=after,
        ))
        return GuildMember.create_hash(self.client, 'id', r.json(), guild_id=guild)

    def guilds_members_get(self, guild, member):
        r = self.http(Routes.GUILDS_MEMBERS_GET, dict(guild=guild, member=member))
        return GuildMember.create(self.client, r.json(), guild_id=guild)

    def guilds_members_modify(self, guild, member, reason=None, **kwargs):
        self.http(
            Routes.GUILDS_MEMBERS_MODIFY,
            dict(guild=guild, member=member),
            json=kwargs,
            headers=_reason_header(reason))

    def guilds_members_roles_add(self, guild, member, role, reason=None):
        self.http(
            Routes.GUILDS_MEMBERS_ROLES_ADD,
            dict(guild=guild, member=member, role=role),
            headers=_reason_header(reason))

    def guilds_members_roles_remove(self, guild, member, role, reason=None):
        self.http(
            Routes.GUILDS_MEMBERS_ROLES_REMOVE,
            dict(guild=guild, member=member, role=role),
            headers=_reason_header(reason))

    def guilds_members_me_nick(self, guild, nick):
        self.http(Routes.GUILDS_MEMBERS_ME_NICK, dict(guild=guild), json={'nick': nick})

    def guilds_members_add(self, guild, member, access_token, nick=None, roles=None, mute=None, deaf=None):
        payload = {
            'access_token': access_token
        }

        payload.update(optional(
            nick=nick,
            roles=roles,
            mute=mute,
            deaf=deaf,
        ))

        self.http(Routes.GUILDS_MEMBERS_ADD, dict(guild=guild, member=member), json=payload)

    def guilds_members_kick(self, guild, member, reason=None):
        self.http(Routes.GUILDS_MEMBERS_KICK, dict(guild=guild, member=member), headers=_reason_header(reason))

    def guilds_bans_list(self, guild):
        r = self.http(Routes.GUILDS_BANS_LIST, dict(guild=guild))
        return GuildBan.create_hash(self.client, 'user.id', r.json())

    def guilds_bans_get(self, guild, user):
        r = self.http(Routes.GUILDS_BANS_GET, dict(guild=guild, user=user))
        return GuildBan.create(self.client, r.json())

    def guilds_bans_create(self, guild, user, delete_message_days=0, reason=None):
        self.http(Routes.GUILDS_BANS_CREATE, dict(guild=guild, user=user), params={
            'delete-message-days': delete_message_days,
            'reason': reason,
        }, headers=_reason_header(reason))

    def guilds_bans_delete(self, guild, user, reason=None):
        self.http(
            Routes.GUILDS_BANS_DELETE,
            dict(guild=guild, user=user),
            headers=_reason_header(reason))

    def guilds_prune_count_get(self, guild, days=None):
        r = self.http(Routes.GUILDS_PRUNE_COUNT, dict(guild=guild), params=optional(days=days))
        return PruneCount.create(self.client, r.json())

    def guilds_prune_create(self, guild, days=None, compute_prune_count=None):
        r = self.http(Routes.GUILDS_PRUNE_CREATE, dict(guild=guild), params=optional(
            days=days,
            compute_prune_count=compute_prune_count,
        ))
        return PruneCount.create(self.client, r.json())

    def guilds_roles_list(self, guild):
        r = self.http(Routes.GUILDS_ROLES_LIST, dict(guild=guild))
        return Role.create_map(self.client, r.json(), guild_id=guild)

    def guilds_roles_create(
            self,
            guild,
            name=None,
            permissions=None,
            color=None,
            hoist=None,
            mentionable=None,
            reason=None):

        r = self.http(
            Routes.GUILDS_ROLES_CREATE,
            dict(guild=guild),
            json=optional(
                name=name,
                permissions=permissions,
                color=color,
                hoist=hoist,
                mentionable=mentionable,
            ),
            headers=_reason_header(reason))
        return Role.create(self.client, r.json(), guild_id=guild)

    def guilds_roles_modify_batch(self, guild, roles, reason=None):
        r = self.http(Routes.GUILDS_ROLES_MODIFY_BATCH, dict(guild=guild), json=roles, headers=_reason_header(reason))
        return Role.create_map(self.client, r.json(), guild_id=guild)

    def guilds_roles_modify(
            self,
            guild,
            role,
            name=None,
            hoist=None,
            color=None,
            permissions=None,
            position=None,
            mentionable=None,
            reason=None):

        r = self.http(
            Routes.GUILDS_ROLES_MODIFY,
            dict(guild=guild, role=role),
            json=optional(
                name=name,
                hoist=hoist,
                color=color,
                permissions=permissions,
                position=position,
                mentionable=mentionable,
            ),
            headers=_reason_header(reason))
        return Role.create(self.client, r.json(), guild_id=guild)

    def guilds_roles_delete(self, guild, role, reason=None):
        self.http(Routes.GUILDS_ROLES_DELETE, dict(guild=guild, role=role), headers=_reason_header(reason))

    def guilds_voice_regions_list(self, guild):
        r = self.http(Routes.GUILDS_VOICE_REGIONS_LIST, dict(guild=guild))
        return VoiceRegion.create_hash(self.client, 'id', r.json())

    def guilds_invites_list(self, guild):
        r = self.http(Routes.GUILDS_INVITES_LIST, dict(guild=guild))
        return Invite.create_map(self.client, r.json())

    def guilds_integrations_list(self, guild):
        r = self.http(Routes.GUILDS_INTEGRATIONS_LIST, dict(guild=guild))
        return Integration.create_map(self.client, r.json())

    def guilds_integrations_create(self, guild, type, id):
        r = self.http(Routes.GUILDS_INTEGRATIONS_CREATE, dict(guild=guild), json={"type": type, "id": id})
        return Integration.create(r.json())

    def guilds_integrations_modify(
            self,
            guild,
            integration,
            expire_behavior=None,
            expire_grace_period=None,
            enable_emoticons=None):

        self.http(
            Routes.GUILDS_INTEGRATIONS_MODIFY,
            dict(guild=guild, integration=integration),
            json=optional(
                expire_behavior=expire_behavior,
                expire_grace_period=expire_grace_period,
                enable_emoticons=enable_emoticons,
            ))

    def guilds_integrations_delete(self, guild, integration):
        self.http(Routes.GUILDS_INTEGRATIONS_DELETE, dict(guild=guild, integration=integration))

    def guilds_integrations_sync(self, guild, integration):
        self.http(Routes.GUILDS_INTEGRATIONS_SYNC, dict(guild=guild, integration=integration))

    def guilds_vanity_url_get(self, guild):
        r = self.http(Routes.GUILDS_VANITY_URL_GET, dict(guild=guild))
        return Invite.create(self.client, r.json())

    def guilds_embed_get(self, guild):
        r = self.http(Routes.GUILDS_EMBED_GET, dict(guild=guild))
        return GuildEmbed.create(self.client, r.json())

    def guilds_embed_modify(self, guild, reason=None, **kwargs):
        r = self.http(
            Routes.GUILDS_EMBED_MODIFY,
            dict(guild=guild),
            json=kwargs,
            headers=_reason_header(reason))
        return GuildEmbed.create(self.client, r.json())

    def guilds_webhooks_list(self, guild):
        r = self.http(Routes.GUILDS_WEBHOOKS_LIST, dict(guild=guild))
        return Webhook.create_map(self.client, r.json())

    def guilds_emojis_get(self, guild, emoji):
        r = self.http(Routes.GUILDS_EMOJIS_GET, dict(guild=guild, emoji=emoji))
        return GuildEmoji.create(self.client, r.json())

    def guilds_emojis_list(self, guild):
        r = self.http(Routes.GUILDS_EMOJIS_LIST, dict(guild=guild))
        return GuildEmoji.create_map(self.client, r.json())

    def guilds_emojis_create(self, guild, reason=None, **kwargs):
        r = self.http(
            Routes.GUILDS_EMOJIS_CREATE,
            dict(guild=guild),
            json=kwargs,
            headers=_reason_header(reason))
        return GuildEmoji.create(self.client, r.json(), guild_id=guild)

    def guilds_emojis_modify(self, guild, emoji, reason=None, **kwargs):
        r = self.http(
            Routes.GUILDS_EMOJIS_MODIFY,
            dict(guild=guild, emoji=emoji),
            json=kwargs,
            headers=_reason_header(reason))
        return GuildEmoji.create(self.client, r.json(), guild_id=guild)

    def guilds_emojis_delete(self, guild, emoji, reason=None):
        self.http(
            Routes.GUILDS_EMOJIS_DELETE,
            dict(guild=guild, emoji=emoji),
            headers=_reason_header(reason))

    def guilds_auditlogs_list(self, guild, before=None, user_id=None, action_type=None, limit=50):
        r = self.http(Routes.GUILDS_AUDITLOGS_LIST, dict(guild=guild), params=optional(
            before=before,
            user_id=user_id,
            action_type=int(action_type) if action_type else None,
            limit=limit,
        ))

        data = r.json()

        users = User.create_hash(self.client, 'id', data['users'])
        webhooks = Webhook.create_hash(self.client, 'id', data['webhooks'])
        return AuditLogEntry.create_map(self.client, r.json()['audit_log_entries'], users, webhooks, guild_id=guild)

    def users_get(self, user):
        r = self.http(Routes.USERS_GET, dict(user=user))
        return User.create(self.client, r.json())

    def users_me_get(self):
        r = self.http(Routes.USERS_ME_GET)
        return User.create(self.client, r.json())

    def users_me_patch(self, payload):
        r = self.http(Routes.USERS_ME_PATCH, json=payload)
        return User.create(self.client, r.json())

    def users_me_guilds_list(self):
        r = self.http(Routes.USERS_ME_GUILDS_LIST)
        return Guild.create_hash(self.client, 'id', r.json())

    def users_me_guilds_delete(self, guild):
        self.http(Routes.USERS_ME_GUILDS_DELETE, dict(guild=guild))

    def users_me_dms_create(self, recipient_id):
        r = self.http(Routes.USERS_ME_DMS_CREATE, json={
            'recipient_id': recipient_id,
        })
        return Channel.create(self.client, r.json())

    def users_me_connections_list(self):
        r = self.http(Routes.USERS_ME_CONNECTIONS_LIST)
        return Connection.create_map(self.client, r.json())

    def invites_get(self, invite):
        r = self.http(Routes.INVITES_GET, dict(invite=invite))
        return Invite.create(self.client, r.json())

    def invites_delete(self, invite, reason=None):
        r = self.http(Routes.INVITES_DELETE, dict(invite=invite), headers=_reason_header(reason))
        return Invite.create(self.client, r.json())

    def voice_regions_list(self):
        r = self.http(Routes.VOICE_REGIONS_LIST)
        return VoiceRegion.create_hash(self.client, 'id', r.json())

    def webhooks_get(self, webhook):
        r = self.http(Routes.WEBHOOKS_GET, dict(webhook=webhook))
        return Webhook.create(self.client, r.json())

    def webhooks_modify(self, webhook, name=None, avatar=None, reason=None):
        r = self.http(Routes.WEBHOOKS_MODIFY, dict(webhook=webhook), json=optional(
            name=name,
            avatar=avatar,
        ), headers=_reason_header(reason))
        return Webhook.create(self.client, r.json())

    def webhooks_delete(self, webhook, reason=None):
        self.http(Routes.WEBHOOKS_DELETE, dict(webhook=webhook), headers=_reason_header(reason))

    def webhooks_token_get(self, webhook, token):
        r = self.http(Routes.WEBHOOKS_TOKEN_GET, dict(webhook=webhook, token=token))
        return Webhook.create(self.client, r.json())

    def webhooks_token_modify(self, webhook, token, name=None, avatar=None):
        r = self.http(Routes.WEBHOOKS_TOKEN_MODIFY, dict(webhook=webhook, token=token), json=optional(
            name=name,
            avatar=avatar,
        ))
        return Webhook.create(self.client, r.json())

    def webhooks_token_delete(self, webhook, token):
        self.http(Routes.WEBHOOKS_TOKEN_DELETE, dict(webhook=webhook, token=token))

    def webhooks_token_execute(self, webhook, token, data, wait=False):
        obj = self.http(
            Routes.WEBHOOKS_TOKEN_EXECUTE,
            dict(webhook=webhook, token=token),
            json=optional(**data), params={'wait': int(wait)})

        if wait:
            return Message.create(self.client, obj.json())
