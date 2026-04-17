from gevent import sleep as gevent_sleep, spawn as gevent_spawn
from gevent.event import Event as GeventEvent
from requests import JSONDecodeError
from time import monotonic

from disco.util.logging import LoggingClass


class RouteState(LoggingClass):
    """
    An object which stores ratelimit state for a given method/url route
    combination (as specified in :class:`disco.api.http.Routes`).

    Parameters
    ----------
    route : tuple(HTTPMethod, str)
        The route which this RouteState is for.
    response : :class:`requests.Response`
        The response object for the last request made to the route, should contain
        the standard rate limit headers.

    Attributes
    ---------
    route : tuple(HTTPMethod, str)
        The route which this RouteState is for.
    remaining : int
        The number of remaining requests to the route before the rate limit will
        be hit, triggering a 429 response.
    reset_time : int
        A UNIX epoch timestamp (in seconds) after which this rate limit is reset.
    event : :class:`gevent.event.Event`
        An event that is used to block all requests while a route is in the
        cooldown stage.
    """
    def __init__(self, route, response):
        self.route = route
        self.bucket = None
        self.remaining = 1
        self.reset_time = 0.0
        self.event = None
        self.scope = None

        self.update(response)

    def __repr__(self):
        return '<RouteState route={}>'.format(' '.join(self.route))

    @property
    def chilled(self):
        """
        Whether this route is currently being cooled-down (aka waiting until reset_time).
        """
        return self.event is not None

    @property
    def next_will_ratelimit(self):
        """
        Whether the next request to the route (at this moment in time) will
        trigger the rate limit.
        """
        return self.remaining <= 1 and monotonic() <= self.reset_time

    def update(self, response):
        """
        Updates this route with the provided Requests response object. It's expected
        the response has the required headers, however in the case that it doesn't,
        this function has no effect.
        """
        if 'X-RateLimit-Bucket' in response.headers:
            self.bucket = response.headers.get('X-RateLimit-Bucket')

        if 'X-RateLimit-Scope' in response.headers:
            self.scope = response.headers.get('X-RateLimit-Scope')

        if 'X-RateLimit-Remaining' in response.headers:
            self.remaining = int(response.headers.get('X-RateLimit-Remaining', 0))

        if 'X-RateLimit-Reset-After' in response.headers:
            self.reset_time = monotonic() + float(response.headers.get('X-RateLimit-Reset-After'))

    def wait(self):
        """
        Waits until this route is no longer under a cooldown.

        Returns
        -------
        float
            The duration we waited for, in seconds or zero if we didn't have to
            wait at all.
        """
        if not self.event or self.event.is_set():
            return 0

        start = monotonic()
        self.event.wait()
        return monotonic() - start

    def cooldown(self):
        """
        Waits for the current route to be cooled-down (aka waiting until reset time).
        """
        if self.reset_time - monotonic() <= 0:
            return 0

        if self.event:
            return self.wait()
        self.event = GeventEvent()
        delay = (self.reset_time - monotonic()) + 0.05
        self.log.debug('Cooling down bucket %s for %s seconds', self, delay)
        gevent_sleep(delay)
        self.event.set()
        self.event = None
        return delay


class RateLimiter(LoggingClass):
    """
    An in-memory store of ratelimit states for all routes we've ever called.

    Attributes
    ----------
    states : dict(tuple(HTTPMethod, str), :class:`RouteState`)
        Contains a :class:`RouteState` for each route the RateLimiter is currently
        tracking.
    """
    def __init__(self, max_queries_per_second=50):
        self.states = {}
        self.buckets = {}
        self.global_requests = []
        self.max_queries_per_second = max_queries_per_second

    def _get_state(self, route):
        state = self.states.get(route)

        # If this route is mapped to a bucket, use shared state
        if state and state.bucket and state.bucket in self.buckets:
            return self.buckets[state.bucket]

        return state

    def check(self, route):
        """
        Checks whether a given route can be called. This function will return
        immediately if no rate-limit cooldown is being imposed for the given
        route, or will wait indefinitely until the route is finished being
        cooled-down. This function should be called before making a request to
        the specified route.

        Parameters
        ----------
        route : tuple(HTTPMethod, str)
            The route that will be checked.

        Returns
        -------
        float
            The number of seconds we had to wait for this rate limit, or zero
            if no time was waited.
        """
        total = 0
        if None in self.states:
            total += self._check(None)
        total += self._check(route)

        now = monotonic()
        self.global_requests = [t for t in self.global_requests if now - t < 1.0]
        while len(self.global_requests) >= self.max_queries_per_second:
            delay = 1.0 - (monotonic() - self.global_requests[0])
            if delay > 0:
                gevent_sleep(delay)
            now = monotonic()
            self.global_requests = [t for t in self.global_requests if now - t < 1.0]
        self.global_requests.append(now)

        return total

    def _check(self, route):
        if route in self.states:
            # If the route is being cooled off, we need to wait until its ready
            state = self._get_state(route)

            if state.chilled:
                return state.wait()

            if state.next_will_ratelimit:
                return gevent_spawn(state.cooldown).get()

        return 0

    def update(self, route, response):
        """
        Updates the given routes state with the rate-limit headers inside the
        response from a previous call to the route.

        Parameters
        ---------
        route : tuple(HTTPMethod, str)
            The route that will be updated.
        response : :class:`requests.Response`
            The response object for the last request to the route, whose headers
            will be used to update the routes rate limit state.
        """
        if 'X-RateLimit-Global' in response.headers or response.headers.get('X-RateLimit-Scope') == 'global':
            route = None
        else:
            try:
                if response.status_code == 429 and response.json().get('global', False):
                    route = None
            except JSONDecodeError:
                pass

        if route in self.states:
            state = self.states[route]
            state.update(response)
        else:
            state = RouteState(route, response)
            self.states[route] = state

        if state.bucket:
            self.buckets[state.bucket] = state
