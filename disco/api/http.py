import gevent
import random
import requests
import platform

from requests import __version__ as requests_version
from requests.exceptions import ConnectionError

from disco import VERSION as disco_version
from disco.util.logging import LoggingClass
from disco.api.ratelimit import RateLimiter


class HTTPMethod:
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    PATCH = 'PATCH'
    DELETE = 'DELETE'


def random_backoff():
    """
    Returns a random backoff (in milliseconds) to be used for any error the
    client suspects is transient. Will always return a value between 500 and
    5000 milliseconds.

    :returns: a random backoff in milliseconds.
    :rtype: float
    """
    return random.randint(500, 5000) / 1000.0


class Routes:
    """
    Simple Python object-enum of all method/url route combinations available to
    this client.
    """
    # Gateway
    GATEWAY_GET = (HTTPMethod.GET, '/gateway')
    GATEWAY_BOT_GET = (HTTPMethod.GET, '/gateway/bot')

    # OAUTH2
    OAUTH2 = '/oauth2'
    OAUTH2_TOKEN = (HTTPMethod.POST, OAUTH2 + '/token')
    OAUTH2_TOKEN_REVOKE = (HTTPMethod.POST, OAUTH2 + '/token/revoke')
    OAUTH2_APPLICATIONS_ME = (HTTPMethod.GET, OAUTH2 + '/applications/@me')
    OAUTH2_AUTHORIZE = (HTTPMethod.GET, OAUTH2 + '/authorize')

    # Channels
    CHANNELS = '/channels/{channel}'
    CHANNELS_GET = (HTTPMethod.GET, CHANNELS)
    CHANNELS_MODIFY = (HTTPMethod.PATCH, CHANNELS)
    CHANNELS_DELETE = (HTTPMethod.DELETE, CHANNELS)
    CHANNELS_TYPING = (HTTPMethod.POST, CHANNELS + '/typing')
    CHANNELS_MESSAGES_LIST = (HTTPMethod.GET, CHANNELS + '/messages')
    CHANNELS_MESSAGES_GET = (HTTPMethod.GET, CHANNELS + '/messages/{message}')
    CHANNELS_MESSAGES_CREATE = (HTTPMethod.POST, CHANNELS + '/messages')
    CHANNELS_MESSAGES_MODIFY = (HTTPMethod.PATCH, CHANNELS + '/messages/{message}')
    CHANNELS_MESSAGES_DELETE = (HTTPMethod.DELETE, CHANNELS + '/messages/{message}')
    CHANNELS_MESSAGES_DELETE_BULK = (HTTPMethod.POST, CHANNELS + '/messages/bulk-delete')
    CHANNELS_MESSAGES_REACTIONS_GET = (HTTPMethod.GET, CHANNELS + '/messages/{message}/reactions/{emoji}')
    CHANNELS_MESSAGES_REACTIONS_CREATE = (HTTPMethod.PUT, CHANNELS + '/messages/{message}/reactions/{emoji}/@me')
    CHANNELS_MESSAGES_REACTIONS_DELETE_ALL = (HTTPMethod.DELETE, CHANNELS + '/messages/{message}/reactions')
    CHANNELS_MESSAGES_REACTIONS_DELETE_ME = (HTTPMethod.DELETE, CHANNELS + '/messages/{message}/reactions/{emoji}/@me')
    CHANNELS_MESSAGES_REACTIONS_DELETE_USER = (HTTPMethod.DELETE,
                                               CHANNELS + '/messages/{message}/reactions/{emoji}/{user}')
    CHANNELS_MESSAGES_REACTIONS_DELETE_EMOJI = (HTTPMethod.DELETE, CHANNELS + '/messages/{message}/reactions/{emoji}')
    CHANNELS_MESSAGES_PUBLISH = (HTTPMethod.POST, CHANNELS + '/messages/{message}/crosspost')
    CHANNELS_MESSAGES_THREAD_START = (HTTPMethod.POST, CHANNELS + '/messages/{message}/threads')
    CHANNELS_PERMISSIONS_MODIFY = (HTTPMethod.PUT, CHANNELS + '/permissions/{permission}')
    CHANNELS_PERMISSIONS_DELETE = (HTTPMethod.DELETE, CHANNELS + '/permissions/{permission}')
    CHANNELS_INVITES_LIST = (HTTPMethod.GET, CHANNELS + '/invites')
    CHANNELS_INVITES_CREATE = (HTTPMethod.POST, CHANNELS + '/invites')
    CHANNELS_PINS_LIST = (HTTPMethod.GET, CHANNELS + '/pins')
    CHANNELS_PINS_CREATE = (HTTPMethod.PUT, CHANNELS + '/pins/{message}')
    CHANNELS_PINS_DELETE = (HTTPMethod.DELETE, CHANNELS + '/pins/{message}')
    CHANNELS_WEBHOOKS_CREATE = (HTTPMethod.POST, CHANNELS + '/webhooks')
    CHANNELS_WEBHOOKS_LIST = (HTTPMethod.GET, CHANNELS + '/webhooks')
    CHANNELS_THREAD_START = (HTTPMethod.POST, CHANNELS + '/threads')
    CHANNELS_THREAD_MEMBERS = CHANNELS + '/thread-members'
    CHANNELS_THREAD_JOIN = (HTTPMethod.PUT, CHANNELS_THREAD_MEMBERS + '/@me')
    CHANNELS_THREAD_LEAVE = (HTTPMethod.DELETE, CHANNELS_THREAD_MEMBERS + '/@me')
    CHANNELS_THREAD_MEMBER_ADD = (HTTPMethod.PUT, CHANNELS_THREAD_MEMBERS + '/{member}')
    CHANNELS_THREAD_MEMBER_REMOVE = (HTTPMethod.DELETE, CHANNELS_THREAD_MEMBERS + '/{member}')
    CHANNELS_THREAD_MEMBER_GET = (HTTPMethod.GET, CHANNELS_THREAD_MEMBERS + '/{member}')
    CHANNELS_THREAD_MEMBERS_LIST = (HTTPMethod.GET, CHANNELS_THREAD_MEMBERS)
    CHANNELS_THREADS = CHANNELS + '/threads'
    CHANNELS_THREADS_LIST = (HTTPMethod.GET, CHANNELS_THREADS + '/active')
    CHANNELS_THREADS_LIST_ARCHIVED_PUBLIC = (HTTPMethod.GET, CHANNELS_THREADS + '/archived/public')
    CHANNELS_THREADS_LIST_ARCHIVED_PRIVATE = (HTTPMethod.GET, CHANNELS_THREADS + '/archived/private')
    CHANNELS_THREADS_LIST_JOINED_PRIVATE = (HTTPMethod.GET, CHANNELS + '/users/@me/threads/archived/private')

    # Stickers
    STICKER = '/stickers'
    STICKER_GET = (HTTPMethod.GET, STICKER + '/{sticker}')
    STICKERS_NITRO_GET = (HTTPMethod.GET, '/sticker-packs')

    # Guilds
    GUILDS = '/guilds/{guild}'
    GUILDS_GET = (HTTPMethod.GET, GUILDS)
    GUILDS_CREATE = (HTTPMethod.POST, '/guilds')
    GUILDS_MODIFY = (HTTPMethod.PATCH, GUILDS)
    GUILDS_DELETE = (HTTPMethod.DELETE, GUILDS)
    GUILDS_CHANNELS_LIST = (HTTPMethod.GET, GUILDS + '/channels')
    GUILDS_CHANNELS_CREATE = (HTTPMethod.POST, GUILDS + '/channels')
    GUILDS_CHANNELS_MODIFY = (HTTPMethod.PATCH, GUILDS + '/channels')
    GUILDS_MEMBERS_LIST = (HTTPMethod.GET, GUILDS + '/members')
    GUILDS_MEMBERS_GET = (HTTPMethod.GET, GUILDS + '/members/{member}')
    GUILDS_MEMBERS_MODIFY = (HTTPMethod.PATCH, GUILDS + '/members/{member}')
    GUILDS_MEMBERS_ROLES_ADD = (HTTPMethod.PUT, GUILDS + '/members/{member}/roles/{role}')
    GUILDS_MEMBERS_ROLES_REMOVE = (HTTPMethod.DELETE, GUILDS + '/members/{member}/roles/{role}')
    GUILDS_MEMBERS_ME_NICK = (HTTPMethod.PATCH, GUILDS + '/members/@me/nick')
    GUILDS_MEMBERS_KICK = (HTTPMethod.DELETE, GUILDS + '/members/{member}')
    GUILDS_MEMBERS_ADD = (HTTPMethod.PUT, GUILDS + '/members/{member}')
    GUILDS_BANS_LIST = (HTTPMethod.GET, GUILDS + '/bans')
    GUILDS_BANS_GET = (HTTPMethod.GET, GUILDS + '/bans/{user}')
    GUILDS_BANS_CREATE = (HTTPMethod.PUT, GUILDS + '/bans/{user}')
    GUILDS_BANS_DELETE = (HTTPMethod.DELETE, GUILDS + '/bans/{user}')
    GUILDS_ROLES_LIST = (HTTPMethod.GET, GUILDS + '/roles')
    GUILDS_ROLES_CREATE = (HTTPMethod.POST, GUILDS + '/roles')
    GUILDS_ROLES_MODIFY_BATCH = (HTTPMethod.PATCH, GUILDS + '/roles')
    GUILDS_ROLES_MODIFY = (HTTPMethod.PATCH, GUILDS + '/roles/{role}')
    GUILDS_ROLES_DELETE = (HTTPMethod.DELETE, GUILDS + '/roles/{role}')
    GUILDS_PRUNE_COUNT = (HTTPMethod.GET, GUILDS + '/prune')
    GUILDS_PRUNE_CREATE = (HTTPMethod.POST, GUILDS + '/prune')
    GUILDS_VOICE_REGIONS_LIST = (HTTPMethod.GET, GUILDS + '/regions')
    GUILDS_VANITY_URL_GET = (HTTPMethod.GET, GUILDS + '/vanity-url')
    GUILDS_INVITES_LIST = (HTTPMethod.GET, GUILDS + '/invites')
    GUILDS_INTEGRATIONS_LIST = (HTTPMethod.GET, GUILDS + '/integrations')
    GUILDS_INTEGRATIONS_CREATE = (HTTPMethod.POST, GUILDS + '/integrations')
    GUILDS_INTEGRATIONS_MODIFY = (HTTPMethod.PATCH, GUILDS + '/integrations/{integration}')
    GUILDS_INTEGRATIONS_DELETE = (HTTPMethod.DELETE, GUILDS + '/integrations/{integration}')
    GUILDS_INTEGRATIONS_SYNC = (HTTPMethod.POST, GUILDS + '/integrations/{integration}/sync')
    GUILDS_EMBED_GET = (HTTPMethod.GET, GUILDS + '/widget')
    GUILDS_EMBED_MODIFY = (HTTPMethod.PATCH, GUILDS + '/embed')
    GUILDS_WEBHOOKS_LIST = (HTTPMethod.GET, GUILDS + '/webhooks')
    GUILDS_EMOJIS_LIST = (HTTPMethod.GET, GUILDS + '/emojis')
    GUILDS_EMOJIS_CREATE = (HTTPMethod.POST, GUILDS + '/emojis')
    GUILDS_EMOJIS_GET = (HTTPMethod.GET, GUILDS + '/emojis/{emoji}')
    GUILDS_EMOJIS_MODIFY = (HTTPMethod.PATCH, GUILDS + '/emojis/{emoji}')
    GUILDS_EMOJIS_DELETE = (HTTPMethod.DELETE, GUILDS + '/emojis/{emoji}')
    GUILDS_PREVIEW_GET = (HTTPMethod.GET, GUILDS + '/preview')
    GUILDS_AUDITLOGS_LIST = (HTTPMethod.GET, GUILDS + '/audit-logs')
    GUILDS_DISCOVERY_REQUIREMENTS = (HTTPMethod.GET, GUILDS + '/discovery-requirements')
    GUILDS_TEMPLATES = GUILDS + '/templates'
    GUILDS_TEMPLATE_GET = (HTTPMethod.GET, GUILDS_TEMPLATES + '/{template}')
    GUILDS_CREATE_WITH_TEMPLATE = (HTTPMethod.POST, GUILDS_TEMPLATES + '/{template}')
    GUILDS_TEMPLATES_GET = (HTTPMethod.GET, GUILDS_TEMPLATES)
    GUILDS_TEMPLATE_CREATE = (HTTPMethod.POST, GUILDS_TEMPLATES)
    GUILDS_TEMPLATE_SYNC = (HTTPMethod.PUT, GUILDS_TEMPLATES + '/{template}')
    GUILDS_TEMPLATE_MODIFY = (HTTPMethod.PATCH, GUILDS_TEMPLATES + '/{template}')
    GUILDS_TEMPLATE_DELETE = (HTTPMethod.DELETE, GUILDS_TEMPLATES + '/{template}')
    GUILDS_THREADS = GUILDS + '/threads'
    GUILDS_THREADS_ACTIVE = (HTTPMethod.GET, GUILDS_THREADS + '/active')
    GUILDS_EVENTS = GUILDS + '/scheduled-events'
    GUILDS_EVENTS_GET = (HTTPMethod.GET, GUILDS_EVENTS)
    GUILDS_EVENT_GET = (HTTPMethod.GET, GUILDS_EVENTS + '/{event}')
    GUILDS_EVENT_USERS_GET = (HTTPMethod.GET, GUILDS_EVENTS + '/{event}/users')
    GUILDS_EVENTS_CREATE = (HTTPMethod.POST, GUILDS_EVENTS)
    GUILDS_EVENTS_MODIFY = (HTTPMethod.PATCH, GUILDS_EVENTS + '/{event}')
    GUILDS_EVENTS_DELETE = (HTTPMethod.DELETE, GUILDS_EVENTS + '/{event}')
    GUILDS_STICKERS = GUILDS + STICKER
    GUILDS_STICKERS_GET = (HTTPMethod.GET, GUILDS_STICKERS)
    GUILDS_STICKER_GET = (HTTPMethod.GET, GUILDS_STICKERS + '/{sticker}')
    GUILDS_STICKER_CREATE = (HTTPMethod.POST, GUILDS_STICKERS)
    GUILDS_STICKER_MODIFY = (HTTPMethod.PATCH, GUILDS_STICKERS + '/{sticker}')
    GUILDS_STICKER_DELETE = (HTTPMethod.DELETE, GUILDS_STICKERS + '/{sticker}')
    GUILDS_AUTOMODERATION = GUILDS + '/auto-moderation'
    GUILDS_AUTOMODERATION_RULES_GET = (HTTPMethod.GET, GUILDS_AUTOMODERATION + '/rules')
    GUILDS_AUTOMODERATION_RULE_GET = (HTTPMethod.GET, GUILDS_AUTOMODERATION + '/rules/{rule}')
    GUILDS_AUTOMODERATION_RULES_CREATE = (HTTPMethod.POST, GUILDS_AUTOMODERATION + '/rules')
    GUILDS_AUTOMODERATION_RULES_MODIFY = (HTTPMethod.PATCH, GUILDS_AUTOMODERATION + '/rules/{rule}')
    GUILDS_AUTOMODERATION_RULES_DELETE = (HTTPMethod.DELETE, GUILDS_AUTOMODERATION + '/rules/{rule}')

    # Users
    USERS = '/users'
    USERS_ME_GET = (HTTPMethod.GET, USERS + '/@me')
    USERS_ME_PATCH = (HTTPMethod.PATCH, USERS + '/@me')
    USERS_ME_GUILDS_LIST = (HTTPMethod.GET, USERS + '/@me/guilds')
    USERS_ME_GUILDS_DELETE = (HTTPMethod.DELETE, USERS + '/@me/guilds/{guild}')
    USERS_ME_DMS_LIST = (HTTPMethod.GET, USERS + '/@me/channels')
    USERS_ME_DMS_CREATE = (HTTPMethod.POST, USERS + '/@me/channels')
    USERS_ME_CONNECTIONS_LIST = (HTTPMethod.GET, USERS + '/@me/connections')
    USERS_GET = (HTTPMethod.GET, USERS + '/{user}')

    # Invites
    INVITES = '/invites'
    INVITES_GET = (HTTPMethod.GET, INVITES + '/{invite}')
    INVITES_DELETE = (HTTPMethod.DELETE, INVITES + '/{invite}')

    # Voice
    VOICE = '/voice'
    VOICE_REGIONS_LIST = (HTTPMethod.GET, VOICE + '/regions')

    # Webhooks
    WEBHOOKS = '/webhooks/{webhook}'
    WEBHOOKS_GET = (HTTPMethod.GET, WEBHOOKS)
    WEBHOOKS_MODIFY = (HTTPMethod.PATCH, WEBHOOKS)
    WEBHOOKS_DELETE = (HTTPMethod.DELETE, WEBHOOKS)
    WEBHOOKS_TOKEN_GET = (HTTPMethod.GET, WEBHOOKS + '/{token}')
    WEBHOOKS_TOKEN_MODIFY = (HTTPMethod.PATCH, WEBHOOKS + '/{token}')
    WEBHOOKS_TOKEN_DELETE = (HTTPMethod.DELETE, WEBHOOKS + '/{token}')
    WEBHOOKS_TOKEN_EXECUTE = (HTTPMethod.POST, WEBHOOKS + '/{token}')
    WEBHOOKS_MESSAGE_GET = (HTTPMethod.GET, WEBHOOKS + '/token/{token}/messages/{message}')
    WEBHOOKS_MESSAGE_MODIFY = (HTTPMethod.PATCH, WEBHOOKS + '/token/{token}/messages/{message}')
    WEBHOOKS_MESSAGE_DELETE = (HTTPMethod.DELETE, WEBHOOKS + '/token/{token}/messages/{message}')

    # Applications
    APPLICATIONS = '/applications/{application}'
    APPLICATIONS_GLOBAL_COMMANDS_GET = (HTTPMethod.GET, APPLICATIONS + '/commands')
    APPLICATIONS_GLOBAL_COMMANDS_CREATE = (HTTPMethod.POST, APPLICATIONS + '/commands')
    APPLICATIONS_GLOBAL_COMMAND_GET = (HTTPMethod.GET, APPLICATIONS + '/command/{command}')
    APPLICATIONS_GLOBAL_COMMANDS_MODIFY = (HTTPMethod.PATCH, APPLICATIONS + '/commands/{command}')
    APPLICATIONS_GLOBAL_COMMANDS_DELETE = (HTTPMethod.DELETE, APPLICATIONS + '/commands/{command}')
    APPLICATION_GLOBAL_BULK_OVERWRITE = (HTTPMethod.PUT, APPLICATIONS + '/commands')
    APPLICATIONS_GUILD_COMMANDS_GET = (HTTPMethod.GET, APPLICATIONS + '/guilds/{guild}/commands')
    APPLICATIONS_GUILD_COMMANDS_CREATE = (HTTPMethod.POST, APPLICATIONS + '/guilds/{guild}/commands')
    APPLICATIONS_GUILD_COMMAND_GET = (HTTPMethod.GET, APPLICATIONS + '/guilds/{guild}/commands/{command}')
    APPLICATIONS_GUILD_COMMANDS_MODIFY = (HTTPMethod.PATCH, APPLICATIONS + '/guilds/{guild}/commands/{command}')
    APPLICATIONS_GUILD_COMMANDS_DELETE = (HTTPMethod.DELETE, APPLICATIONS + '/guilds/{guild}/commands/{command}')
    APPLICATION_GUILD_BULK_OVERWRITE = (HTTPMethod.PUT, APPLICATIONS + '/guilds/{guild}/commands')
    APPLICATIONS_GUILD_COMMANDS_PERMISSIONS_GET = (HTTPMethod.GET, APPLICATIONS + '/guilds/{guild}/commands/permissions')
    APPLICATIONS_GUILD_COMMAND_PERMISSIONS_GET = (HTTPMethod.GET,
                                                  APPLICATIONS + '/guilds/{guild}/commands/{command}/permissions')
    APPLICATIONS_GUILD_COMMAND_PERMISSIONS_MODIFY = (HTTPMethod.PUT,
                                                     APPLICATIONS + '/guilds/{guild}/commands/{command}/permissions')
    APPLICATIONS_GUILD_COMMANDS_PERMISSIONS_MODIFY = (HTTPMethod.PUT,
                                                      APPLICATIONS + '/guilds/{guild}/commands/permissions')

    # Interactions
    INTERACTIONS = '/webhooks/{id}/{token}'
    INTERACTIONS_CREATE = (HTTPMethod.POST, '/interactions/{id}/{token}/callback')
    INTERACTIONS_GET_ORIGINAL_RESPONSE = (HTTPMethod.GET, INTERACTIONS + '/messages/@original')
    INTERACTIONS_EDIT = (HTTPMethod.PATCH, INTERACTIONS + '/messages/@original')
    INTERACTIONS_DELETE = (HTTPMethod.DELETE, INTERACTIONS + '/messages/@original')
    INTERACTIONS_FOLLOWUP_CREATE = (HTTPMethod.POST, INTERACTIONS)
    INTERACTIONS_FOLLOWUP_EDIT = (HTTPMethod.PATCH, INTERACTIONS + '/messages/{message}')
    INTERACTIONS_FOLLOWUP_DELETE = (HTTPMethod.DELETE, INTERACTIONS + '/messages/{message}')

    # Stages
    STAGES = '/stage-instances'
    STAGES_CREATE = (HTTPMethod.POST, STAGES)
    STAGES_GET = (HTTPMethod.GET, STAGES + '/{channel}')
    STAGES_MODIFY = (HTTPMethod.PATCH, STAGES + '/{channel}')
    STAGES_DELETE = (HTTPMethod.DELETE, STAGES + '/{channel}')


class APIResponse:
    def __init__(self):
        self.response = None
        self.exception = None
        self.rate_limited_duration = 0


class APIException(Exception):
    """
    Exception thrown when an HTTP-client level error occurs. Usually this will
    be a non-success status-code, or a transient network issue.

    Attributes
    ----------
    status_code : int
        The status code returned by the API for the request that triggered this
        error.
    """
    def __init__(self, response, retries=None):
        self.response = response
        self.retries = retries

        self.code = 0
        self.msg = 'Request Failed ({})'.format(response.status_code)
        self.errors = {}

        if self.retries:
            self.msg += ' after {} retries'.format(self.retries)

        # Try to decode JSON, and extract params
        try:
            data = self.response.json()

            if 'code' in data:
                self.code = data['code']
                self.errors = data.get('errors', {})
                self.msg = '{} ({} - {})'.format(data['message'], self.code, self.errors)
            elif len(data) == 1:
                key, value = list(data.items())[0]
                if not isinstance(value, str):
                    value = ', '.join(value)
                self.msg = 'Request Failed: {}: {}'.format(key, value)
        except ValueError:
            pass

        # DEPRECATED: left for backwards compat
        self.status_code = response.status_code
        self.content = response.content

        super(APIException, self).__init__(self.msg)


class HTTPClient(LoggingClass):
    """
    A simple HTTP client which wraps the requests library, adding support for
    Discords rate-limit headers, authorization, and request/response validation.
    """
    BASE_URL = 'https://discord.com/api/v9'
    MAX_RETRIES = 5

    def __init__(self, token, after_request=None):
        super(HTTPClient, self).__init__()

        py_version = platform.python_version()

        self.limiter = RateLimiter()
        self.after_request = after_request

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DiscordBot (https://github.com/elderlabs/betterdisco {}) Python/{} requests/{}'.format(
                disco_version,
                py_version,
                requests_version),
        })

        if token:
            self.session.headers['Authorization'] = 'Bot ' + token

    def __call__(self, route, args=None, **kwargs):
        return self.call(route, args, **kwargs)

    def call(self, route, args=None, **kwargs):
        """
        Makes a request to the given route (as specified in
        :class:`disco.api.http.Routes`) with a set of URL arguments, and keyword
        arguments passed to requests.

        Parameters
        ----------
        route : tuple(:class:`HTTPMethod`, str)
            The method.URL combination that when compiled with URL arguments
            creates a requestable route which the HTTPClient will make the
            request too.
        args : dict(str, str)
            A dictionary of URL arguments that will be compiled with the raw URL
            to create the requestable route. The HTTPClient uses this to track
            rate limits as well.
        kwargs : dict
            Keyword arguments that will be passed along to the requests library.

        Raises
        ------
        APIException
            Raised when an unrecoverable error occurs, or when we've exhausted
            the number of retries.

        Returns
        -------
        :class:`requests.Response`
            The response object for the request.
        """
        args = args or {}
        retry = kwargs.pop('retry_number', 0)

        # Build the bucket URL
        args = {k: v for k, v in args.items()}
        filtered = {k: (v if k in ('guild', 'channel') else '') for k, v in args.items()}
        bucket = (route[0], route[1].format(**filtered))

        response = APIResponse()

        # Possibly wait if we're rate limited
        response.rate_limited_duration = self.limiter.check(bucket)

        self.log.debug('KW: %s', kwargs)

        # Make the actual request
        url = self.BASE_URL + route[1].format(**args)
        self.log.info('%s %s %s', route[0], url, '({})'.format(kwargs.get('params')) if kwargs.get('params') else '')
        try:
            r = self.session.request(route[0], url, **kwargs)

            if self.after_request:
                response.response = r
                self.after_request(response)

            # Update rate limiter
            self.limiter.update(bucket, r)

            # If we got a success status code, just return the data
            if r.status_code < 400:
                return r
            elif r.status_code != 429 and 400 <= r.status_code < 500:
                self.log.warning('Request failed with code %s: %s', r.status_code, r.content)
                response.exception = APIException(r)
                raise response.exception
            elif r.status_code in [429, 500, 502, 503]:
                if r.status_code == 429:
                    self.log.warning('Request responded w/ 429, retrying (but this should not happen, check your clock sync)')

                # If we hit the max retries, throw an error
                retry += 1
                if retry > self.MAX_RETRIES:
                    self.log.error('Failing request, hit max retries')
                    raise APIException(r, retries=self.MAX_RETRIES)

                backoff = random_backoff()
                if r.status_code in [500, 502, 503]:
                    self.log.warning('Request to `{}` failed with code {}, retrying after {}s'.format(
                        url, r.status_code, backoff,
                    ))
                else:
                    self.log.warning('Request to `{}` failed with code {}, retrying after {}s ({})'.format(
                        url, r.status_code, backoff, r.content,
                    ))
                gevent.sleep(backoff)

                # Otherwise just recurse and try again
                return self(route, args, retry_number=retry, **kwargs)
        except ConnectionError:
            # Catch ConnectionResetError
            backoff = random_backoff()
            self.log.warning('Request to `{}` failed with ConnectionError, retrying after {}s'.format(url, backoff))
            gevent.sleep(backoff)
            return self(route, args, retry_number=retry, **kwargs)
        except requests.exceptions.Timeout:
            backoff = random_backoff()
            self.log.warning('Request to `{}` failed with ConnectionTimeout, retrying after {}s')
            gevent.sleep(backoff)
            return self(route, args, retry_number=retry, **kwargs)
