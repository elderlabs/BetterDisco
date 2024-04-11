from gevent import sleep as gevent_sleep
from random import randint as random_randint
from requests import Session as RequestsSession, __version__ as requests_version, ConnectionError, Timeout
from platform import python_version

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
    return random_randint(500, 5000) / 1000.0


class Routes:
    """
    Simple Python object-enum of all method/url route combinations available to this client.
    """
    APPLICATIONS = '/applications/{application}'
    APPLICATIONS_GLOBAL_COMMANDS_BULK_OVERWRITE = (HTTPMethod.PUT, APPLICATIONS + '/commands')
    APPLICATIONS_GLOBAL_COMMANDS_CREATE = (HTTPMethod.POST, APPLICATIONS + '/commands')
    APPLICATIONS_GLOBAL_COMMANDS_DELETE = (HTTPMethod.DELETE, APPLICATIONS + '/commands/{command}')
    APPLICATIONS_GLOBAL_COMMANDS_GET = (HTTPMethod.GET, APPLICATIONS + '/command/{command}')
    APPLICATIONS_GLOBAL_COMMANDS_LIST = (HTTPMethod.GET, APPLICATIONS + '/commands')
    APPLICATIONS_GLOBAL_COMMANDS_MODIFY = (HTTPMethod.PATCH, APPLICATIONS + '/commands/{command}')
    APPLICATIONS_GUILD_COMMANDS_BULK_OVERWRITE = (HTTPMethod.PUT, APPLICATIONS + '/guilds/{guild}/commands')
    APPLICATIONS_GUILD_COMMANDS_CREATE = (HTTPMethod.POST, APPLICATIONS + '/guilds/{guild}/commands')
    APPLICATIONS_GUILD_COMMANDS_DELETE = (HTTPMethod.DELETE, APPLICATIONS + '/guilds/{guild}/commands/{command}')
    APPLICATIONS_GUILD_COMMANDS_GET = (HTTPMethod.GET, APPLICATIONS + '/guilds/{guild}/commands/{command}')
    APPLICATIONS_GUILD_COMMANDS_LIST = (HTTPMethod.GET, APPLICATIONS + '/guilds/{guild}/commands')
    APPLICATIONS_GUILD_COMMANDS_MODIFY = (HTTPMethod.PATCH, APPLICATIONS + '/guilds/{guild}/commands/{command}')
    APPLICATIONS_GUILD_COMMANDS_PERMISSIONS_GET = (HTTPMethod.GET, APPLICATIONS + '/guilds/{guild}/commands/{command}/permissions')
    APPLICATIONS_GUILD_COMMANDS_PERMISSIONS_LIST = (HTTPMethod.GET, APPLICATIONS + '/guilds/{guild}/commands/permissions')
    APPLICATIONS_GUILD_COMMANDS_PERMISSIONS_MODIFY = (HTTPMethod.PUT, APPLICATIONS + '/guilds/{guild}/commands/{command}/permissions')
    APPLICATIONS_ME_GET = (HTTPMethod.GET, '/applications/@me')
    APPLICATIONS_ME_MODIFY = (HTTPMethod.PATCH, '/applications/@me')
    APPLICATIONS_ROLE_CONNECTIONS_METADATA_GET = (HTTPMethod.GET, APPLICATIONS + '/role-connections/metadata')
    APPLICATIONS_ROLE_CONNECTIONS_METADATA_MODIFY = (HTTPMethod.PUT, APPLICATIONS + '/role-connections/metadata')

    CHANNELS = '/channels/{channel}'
    CHANNELS_DELETE = (HTTPMethod.DELETE, CHANNELS)
    CHANNELS_DMS_GROUP_ADD = (HTTPMethod.PUT, CHANNELS + '/recipients/{user}')
    CHANNELS_DMS_GROUP_REMOVE = (HTTPMethod.DELETE, CHANNELS + '/recipients/{user}')
    CHANNELS_FOLLOW = (HTTPMethod.POST, CHANNELS + '/followers')
    CHANNELS_GET = (HTTPMethod.GET, CHANNELS)
    CHANNELS_INVITES_CREATE = (HTTPMethod.POST, CHANNELS + '/invites')
    CHANNELS_INVITES_LIST = (HTTPMethod.GET, CHANNELS + '/invites')
    CHANNELS_MESSAGES_BULK_DELETE = (HTTPMethod.POST, CHANNELS + '/messages/bulk-delete')
    CHANNELS_MESSAGES_CREATE = (HTTPMethod.POST, CHANNELS + '/messages')
    CHANNELS_MESSAGES_DELETE = (HTTPMethod.DELETE, CHANNELS + '/messages/{message}')
    CHANNELS_MESSAGES_GET = (HTTPMethod.GET, CHANNELS + '/messages/{message}')
    CHANNELS_MESSAGES_LIST = (HTTPMethod.GET, CHANNELS + '/messages')
    CHANNELS_MESSAGES_MODIFY = (HTTPMethod.PATCH, CHANNELS + '/messages/{message}')
    CHANNELS_MESSAGES_POST = (HTTPMethod.POST, CHANNELS + '/messages/{message}/crosspost')
    CHANNELS_MESSAGES_REACTIONS_ALL_DELETE = (HTTPMethod.DELETE, CHANNELS + '/messages/{message}/reactions')
    CHANNELS_MESSAGES_REACTIONS_CREATE = (HTTPMethod.PUT, CHANNELS + '/messages/{message}/reactions/{emoji}/@me')
    CHANNELS_MESSAGES_REACTIONS_EMOJI_DELETE = (HTTPMethod.DELETE, CHANNELS + '/messages/{message}/reactions/{emoji}')
    CHANNELS_MESSAGES_REACTIONS_GET = (HTTPMethod.GET, CHANNELS + '/messages/{message}/reactions/{emoji}')
    CHANNELS_MESSAGES_REACTIONS_ME_DELETE = (HTTPMethod.DELETE, CHANNELS + '/messages/{message}/reactions/{emoji}/@me')
    CHANNELS_MESSAGES_REACTIONS_USER_DELETE = (HTTPMethod.DELETE, CHANNELS + '/messages/{message}/reactions/{emoji}/{user}')
    CHANNELS_MESSAGES_THREAD_CREATE = (HTTPMethod.POST, CHANNELS + '/messages/{message}/threads')
    CHANNELS_MODIFY = (HTTPMethod.PATCH, CHANNELS)
    CHANNELS_PERMISSIONS_DELETE = (HTTPMethod.DELETE, CHANNELS + '/permissions/{permission}')
    CHANNELS_PERMISSIONS_MODIFY = (HTTPMethod.PUT, CHANNELS + '/permissions/{permission}')
    CHANNELS_PINS_CREATE = (HTTPMethod.PUT, CHANNELS + '/pins/{message}')
    CHANNELS_PINS_DELETE = (HTTPMethod.DELETE, CHANNELS + '/pins/{message}')
    CHANNELS_PINS_LIST = (HTTPMethod.GET, CHANNELS + '/pins')
    CHANNELS_THREADS = CHANNELS + '/threads'
    CHANNELS_THREADS_LIST = (HTTPMethod.GET, CHANNELS_THREADS + '/active')
    CHANNELS_THREADS_PRIVATE_ARCHIVED_LIST = (HTTPMethod.GET, CHANNELS_THREADS + '/archived/private')
    CHANNELS_THREADS_PRIVATE_JOINED_LIST = (HTTPMethod.GET, CHANNELS + '/users/@me/threads/archived/private')
    CHANNELS_THREADS_PUBLIC_ARCHIVED_LIST = (HTTPMethod.GET, CHANNELS_THREADS + '/archived/public')
    CHANNELS_THREAD_CREATE = (HTTPMethod.POST, CHANNELS + '/threads')
    CHANNELS_THREAD_MEMBERS = CHANNELS + '/thread-members'
    CHANNELS_THREAD_JOIN = (HTTPMethod.PUT, CHANNELS_THREAD_MEMBERS + '/@me')
    CHANNELS_THREAD_LEAVE = (HTTPMethod.DELETE, CHANNELS_THREAD_MEMBERS + '/@me')
    CHANNELS_THREAD_MEMBERS_ADD = (HTTPMethod.PUT, CHANNELS_THREAD_MEMBERS + '/{member}')
    CHANNELS_THREAD_MEMBERS_GET = (HTTPMethod.GET, CHANNELS_THREAD_MEMBERS + '/{member}')
    CHANNELS_THREAD_MEMBERS_LIST = (HTTPMethod.GET, CHANNELS_THREAD_MEMBERS)
    CHANNELS_THREAD_MEMBERS_REMOVE = (HTTPMethod.DELETE, CHANNELS_THREAD_MEMBERS + '/{member}')
    CHANNELS_TYPING = (HTTPMethod.POST, CHANNELS + '/typing')
    CHANNELS_WEBHOOKS_CREATE = (HTTPMethod.POST, CHANNELS + '/webhooks')
    CHANNELS_WEBHOOKS_LIST = (HTTPMethod.GET, CHANNELS + '/webhooks')

    GATEWAY_GET = (HTTPMethod.GET, '/gateway')
    GATEWAY_BOT_GET = (HTTPMethod.GET, '/gateway/bot')

    GUILDS = '/guilds/{guild}'
    GUILDS_AUDIT_LOGS_LIST = (HTTPMethod.GET, GUILDS + '/audit-logs')
    GUILDS_AUTOMOD_RULES_CREATE = (HTTPMethod.POST, GUILDS + '/auto-moderation/rules')
    GUILDS_AUTOMOD_RULES_DELETE = (HTTPMethod.DELETE, GUILDS + '/auto-moderation/rules/{rule}')
    GUILDS_AUTOMOD_RULES_GET = (HTTPMethod.GET, GUILDS + '/auto-moderation/rules/{rule}')
    GUILDS_AUTOMOD_RULES_LIST = (HTTPMethod.GET, GUILDS + '/auto-moderation/rules')
    GUILDS_AUTOMOD_RULES_MODIFY = (HTTPMethod.PATCH, GUILDS + '/auto-moderation/rules/{rule}')
    GUILDS_BANS_CREATE = (HTTPMethod.PUT, GUILDS + '/bans/{user}')
    GUILDS_BANS_DELETE = (HTTPMethod.DELETE, GUILDS + '/bans/{user}')
    GUILDS_BANS_GET = (HTTPMethod.GET, GUILDS + '/bans/{user}')
    GUILDS_BANS_LIST = (HTTPMethod.GET, GUILDS + '/bans')
    GUILDS_CHANNELS_CREATE = (HTTPMethod.POST, GUILDS + '/channels')
    GUILDS_CHANNELS_LIST = (HTTPMethod.GET, GUILDS + '/channels')
    GUILDS_CHANNELS_MODIFY = (HTTPMethod.PATCH, GUILDS + '/channels')
    GUILDS_CREATE = (HTTPMethod.POST, '/guilds')
    GUILDS_DELETE = (HTTPMethod.DELETE, GUILDS)
    GUILDS_DISCOVERY_REQUIREMENTS_GET = (HTTPMethod.GET, GUILDS + '/discovery-requirements')  # UNLISTED
    GUILDS_EMOJIS_CREATE = (HTTPMethod.POST, GUILDS + '/emojis')
    GUILDS_EMOJIS_DELETE = (HTTPMethod.DELETE, GUILDS + '/emojis/{emoji}')
    GUILDS_EMOJIS_GET = (HTTPMethod.GET, GUILDS + '/emojis/{emoji}')
    GUILDS_EMOJIS_LIST = (HTTPMethod.GET, GUILDS + '/emojis')
    GUILDS_EMOJIS_MODIFY = (HTTPMethod.PATCH, GUILDS + '/emojis/{emoji}')
    GUILDS_EVENTS_DELETE = (HTTPMethod.DELETE, GUILDS + '/scheduled-events/{event}')
    GUILDS_EVENTS_GET = (HTTPMethod.GET, GUILDS + '/scheduled-events/{event}')
    GUILDS_EVENTS_MODIFY = (HTTPMethod.PATCH, GUILDS + '/scheduled-events/{event}')
    GUILDS_EVENTS_USERS_LIST = (HTTPMethod.GET, GUILDS + '/scheduled-events/{event}/users')
    GUILDS_GET = (HTTPMethod.GET, GUILDS)
    GUILDS_INTEGRATIONS_CREATE = (HTTPMethod.POST, GUILDS + '/integrations')
    GUILDS_INTEGRATIONS_DELETE = (HTTPMethod.DELETE, GUILDS + '/integrations/{integration}')
    GUILDS_INTEGRATIONS_LIST = (HTTPMethod.GET, GUILDS + '/integrations')
    GUILDS_INTEGRATIONS_MODIFY = (HTTPMethod.PATCH, GUILDS + '/integrations/{integration}')  # DEPRECATE?
    GUILDS_INTEGRATIONS_SYNC = (HTTPMethod.POST, GUILDS + '/integrations/{integration}/sync')  # DEPRECATE?
    GUILDS_INVITES_LIST = (HTTPMethod.GET, GUILDS + '/invites')
    GUILDS_MEMBERS_ADD = (HTTPMethod.PUT, GUILDS + '/members/{member}')
    GUILDS_MEMBERS_GET = (HTTPMethod.GET, GUILDS + '/members/{member}')
    GUILDS_MEMBERS_LIST = (HTTPMethod.GET, GUILDS + '/members')
    GUILDS_MEMBERS_ME_MODIFY = (HTTPMethod.PATCH, GUILDS + '/members/@me')
    GUILDS_MEMBERS_MODIFY = (HTTPMethod.PATCH, GUILDS + '/members/{member}')
    GUILDS_MEMBERS_REMOVE = (HTTPMethod.DELETE, GUILDS + '/members/{member}')
    GUILDS_MEMBERS_ROLES_ADD = (HTTPMethod.PUT, GUILDS + '/members/{member}/roles/{role}')
    GUILDS_MEMBERS_ROLES_REMOVE = (HTTPMethod.DELETE, GUILDS + '/members/{member}/roles/{role}')
    GUILDS_MEMBERS_SEARCH = (HTTPMethod.GET, GUILDS + '/members/search')
    GUILDS_MEMBERS_SEARCH_NEW = (HTTPMethod.GET, GUILDS + '/members-search')
    GUILDS_MESSAGES_SEARCH = (HTTPMethod.GET, GUILDS + '/messages/search')
    GUILDS_MFA_LEVEL_MODIFY = (HTTPMethod.POST, GUILDS + '/mfa')
    GUILDS_MODIFY = (HTTPMethod.PATCH, GUILDS)
    GUILDS_ONBOARDING_GET = (HTTPMethod.GET, GUILDS + '/onboarding')
    GUILDS_ONBOARDING_MODIFY = (HTTPMethod.PUT, GUILDS + '/onboarding')
    GUILDS_PREVIEW_GET = (HTTPMethod.GET, GUILDS + '/preview')
    GUILDS_PRUNE_COUNT = (HTTPMethod.GET, GUILDS + '/prune')
    GUILDS_PRUNE_CREATE = (HTTPMethod.POST, GUILDS + '/prune')
    GUILDS_ROLES_BATCH_MODIFY = (HTTPMethod.PATCH, GUILDS + '/roles')
    GUILDS_ROLES_CREATE = (HTTPMethod.POST, GUILDS + '/roles')
    GUILDS_ROLES_DELETE = (HTTPMethod.DELETE, GUILDS + '/roles/{role}')
    GUILDS_ROLES_LIST = (HTTPMethod.GET, GUILDS + '/roles')
    GUILDS_ROLES_MODIFY = (HTTPMethod.PATCH, GUILDS + '/roles/{role}')
    GUILDS_STICKERS = GUILDS + '/stickers'
    GUILDS_STICKERS_CREATE = (HTTPMethod.POST, GUILDS_STICKERS)
    GUILDS_STICKERS_DELETE = (HTTPMethod.DELETE, GUILDS_STICKERS + '/{sticker}')
    GUILDS_STICKERS_GET = (HTTPMethod.GET, GUILDS_STICKERS + '/{sticker}')
    GUILDS_STICKERS_LIST = (HTTPMethod.GET, GUILDS_STICKERS)
    GUILDS_STICKERS_MODIFY = (HTTPMethod.PATCH, GUILDS_STICKERS + '/{sticker}')
    GUILDS_TEMPLATES = GUILDS + '/templates'
    GUILDS_TEMPLATES_CREATE = (HTTPMethod.POST, GUILDS_TEMPLATES)
    GUILDS_TEMPLATES_DELETE = (HTTPMethod.DELETE, GUILDS_TEMPLATES + '/{template}')
    GUILDS_TEMPLATES_GET = (HTTPMethod.GET, GUILDS_TEMPLATES + '/{template}')
    GUILDS_TEMPLATES_LIST = (HTTPMethod.GET, GUILDS_TEMPLATES)
    GUILDS_TEMPLATES_MODIFY = (HTTPMethod.PATCH, GUILDS_TEMPLATES + '/{template}')
    GUILDS_TEMPLATES_SYNC = (HTTPMethod.PUT, GUILDS_TEMPLATES + '/{template}')
    GUILDS_THREADS = GUILDS + '/threads'
    GUILDS_THREADS_LIST = (HTTPMethod.GET, GUILDS_THREADS + '/active')
    GUILDS_VANITY_URL_GET = (HTTPMethod.GET, GUILDS + '/vanity-url')
    GUILDS_VOICE_REGIONS_LIST = (HTTPMethod.GET, GUILDS + '/regions')
    GUILDS_VOICE_STATES_ME_MODIFY = (HTTPMethod.PATCH, GUILDS + '/voice-states/@me')
    GUILDS_VOICE_STATES_MODIFY = (HTTPMethod.PATCH, GUILDS + '/voice-states/{member}')
    GUILDS_WEBHOOKS_LIST = (HTTPMethod.GET, GUILDS + '/webhooks')
    GUILDS_WELCOME_SCREEN_GET = (HTTPMethod.GET, GUILDS + '/welcome-screen')
    GUILDS_WELCOME_SCREEN_MODIFY = (HTTPMethod.PATCH, GUILDS + '/welcome-screen')
    GUILDS_WIDGET_GET = (HTTPMethod.GET, GUILDS + '/widget.json')
    GUILDS_WIDGET_IMAGE_GET = (HTTPMethod.GET, GUILDS + '/widget.png')
    GUILDS_WIDGET_MODIFY = (HTTPMethod.PATCH, GUILDS + '/widget')
    GUILDS_WIDGET_SETTINGS_GET = (HTTPMethod.GET, GUILDS + '/widget')
    GUILDS_WITH_TEMPLATE_CREATE = (HTTPMethod.POST, GUILDS_TEMPLATES + '/{template}')

    INTERACTIONS = '/webhooks/{id}/{token}'
    INTERACTIONS_CREATE = (HTTPMethod.POST, '/interactions/{id}/{token}/callback')
    INTERACTIONS_DELETE = (HTTPMethod.DELETE, INTERACTIONS + '/messages/@original')
    INTERACTIONS_FOLLOWUP_CREATE = (HTTPMethod.POST, INTERACTIONS)
    INTERACTIONS_FOLLOWUP_DELETE = (HTTPMethod.DELETE, INTERACTIONS + '/messages/{message}')
    INTERACTIONS_FOLLOWUP_GET = (HTTPMethod.GET, INTERACTIONS + '/messages/{message}')
    INTERACTIONS_FOLLOWUP_MODIFY = (HTTPMethod.PATCH, INTERACTIONS + '/messages/{message}')
    INTERACTIONS_MODIFY = (HTTPMethod.PATCH, INTERACTIONS + '/messages/@original')
    INTERACTIONS_ORIGINAL_RESPONSE_GET = (HTTPMethod.GET, INTERACTIONS + '/messages/@original')

    INVITES = '/invites/{invite}'
    INVITES_DELETE = (HTTPMethod.DELETE, INVITES)
    INVITES_GET = (HTTPMethod.GET, INVITES)

    OAUTH2 = '/oauth2'
    OAUTH2_APPLICATIONS_ME_GET = (HTTPMethod.GET, OAUTH2 + '/applications/@me')
    OAUTH2_AUTHORIZATION_GET = (HTTPMethod.GET, OAUTH2 + '/authorize')
    OAUTH2_AUTHORIZATION_ME_GET = (HTTPMethod.GET, OAUTH2 + '/@me')
    OAUTH2_TOKEN_GET = (HTTPMethod.POST, OAUTH2 + '/token')
    OAUTH2_TOKEN_REVOKE = (HTTPMethod.POST, OAUTH2 + '/token/revoke')

    STAGES = '/stage-instances'
    STAGES_CREATE = (HTTPMethod.POST, STAGES)
    STAGES_DELETE = (HTTPMethod.DELETE, STAGES + '/{channel}')
    STAGES_GET = (HTTPMethod.GET, STAGES + '/{channel}')
    STAGES_MODIFY = (HTTPMethod.PATCH, STAGES + '/{channel}')

    STICKERS = '/stickers'
    STICKERS_GET = (HTTPMethod.GET, STICKERS + '/{sticker}')
    STICKERS_NITRO_GET = (HTTPMethod.GET, '/sticker-packs')

    USERS = '/users'
    USERS_GET = (HTTPMethod.GET, USERS + '/{user}')
    USERS_ME_CONNECTIONS_LIST = (HTTPMethod.GET, USERS + '/@me/connections')
    USERS_ME_CONNECTIONS_ROLE_GET = (HTTPMethod.GET, USERS + '/@me/applications/{application}/role-connection')
    USERS_ME_CONNECTIONS_ROLE_MODIFY = (HTTPMethod.PUT, USERS + '/@me/applications/{application}/role-connection')
    USERS_ME_DMS_CREATE = (HTTPMethod.POST, USERS + '/@me/channels')
    USERS_ME_DMS_GROUP_CREATE = (HTTPMethod.POST, USERS + '/@me/channels')
    USERS_ME_DMS_LIST = (HTTPMethod.GET, USERS + '/@me/channels')  # DEPRECATE?
    USERS_ME_GET = (HTTPMethod.GET, USERS + '/@me')
    USERS_ME_GUILDS_DELETE = (HTTPMethod.DELETE, USERS + '/@me/guilds/{guild}')
    USERS_ME_GUILDS_LIST = (HTTPMethod.GET, USERS + '/@me/guilds')
    USERS_ME_GUILDS_MEMBER_GET = (HTTPMethod.GET, USERS + '/@me/guilds/{guild}/member')
    USERS_ME_MODIFY = (HTTPMethod.PATCH, USERS + '/@me')

    VOICE = '/voice'
    VOICE_REGIONS_LIST = (HTTPMethod.GET, VOICE + '/regions')

    WEBHOOKS = '/webhooks/{webhook}'
    WEBHOOKS_DELETE = (HTTPMethod.DELETE, WEBHOOKS)
    WEBHOOKS_GET = (HTTPMethod.GET, WEBHOOKS)
    WEBHOOKS_MESSAGE_DELETE = (HTTPMethod.DELETE, WEBHOOKS + '/token/{token}/messages/{message}')
    WEBHOOKS_MESSAGE_GET = (HTTPMethod.GET, WEBHOOKS + '/token/{token}/messages/{message}')
    WEBHOOKS_MESSAGE_MODIFY = (HTTPMethod.PATCH, WEBHOOKS + '/token/{token}/messages/{message}')
    WEBHOOKS_MODIFY = (HTTPMethod.PATCH, WEBHOOKS)
    WEBHOOKS_TOKEN_DELETE = (HTTPMethod.DELETE, WEBHOOKS + '/{token}')
    WEBHOOKS_TOKEN_EXECUTE = (HTTPMethod.POST, WEBHOOKS + '/{token}')
    WEBHOOKS_TOKEN_EXECUTE_GITHUB = (HTTPMethod.POST, WEBHOOKS + '/{token}/github')
    WEBHOOKS_TOKEN_EXECUTE_SLACK = (HTTPMethod.POST, WEBHOOKS + '/{token}/slack')
    WEBHOOKS_TOKEN_GET = (HTTPMethod.GET, WEBHOOKS + '/{token}')
    WEBHOOKS_TOKEN_MODIFY = (HTTPMethod.PATCH, WEBHOOKS + '/{token}')


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

        py_version = python_version()

        self.limiter = RateLimiter()
        self.after_request = after_request

        self.session = RequestsSession()
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
                err = r.json()
                if err and 'code' in err and 'message' in err:
                    self.log.warning(f'Request failed with status code {r.status_code}: {err["code"]} - {err["message"]}')
                else:
                    self.log.warning(f'Request failed with status code {r.status_code}: {str(r.content, "utf=8")}')
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
                        url, r.status_code, backoff, str(r.content, "utf=8"),
                    ))
                gevent_sleep(backoff)

                # Otherwise just recurse and try again
                return self(route, args, retry_number=retry, **kwargs)
        except ConnectionError:
            # Catch ConnectionResetError
            backoff = random_backoff()
            self.log.warning('Request to `{}` failed with ConnectionError, retrying after {}s'.format(url, backoff))
            gevent_sleep(backoff)
            return self(route, args, retry_number=retry, **kwargs)
        except Timeout:
            backoff = random_backoff()
            self.log.warning('Request to `{}` failed with ConnectionTimeout, retrying after {}s')
            gevent_sleep(backoff)
            return self(route, args, retry_number=retry, **kwargs)
