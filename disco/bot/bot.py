try:
    import regex as re
except ImportError:
    import re
import os
import gevent
import inspect
import importlib

from gevent.pywsgi import WSGIServer

from disco.bot.plugin import find_loadable_plugins
from disco.bot.command import CommandEvent, CommandLevels
from disco.bot.storage import Storage
from disco.types.guild import GuildMember
from disco.util.config import Config
from disco.util.enum import get_enum_value_by_name
from disco.util.logging import LoggingClass
from disco.util.serializer import Serializer
from disco.util.threadlocal import ThreadLocal


class BotConfig(Config):
    """
    An object which is used to configure and define the runtime configuration for
    a bot.

    Attributes
    ----------
    levels : dict(snowflake, str)
        Mapping of user IDs/role IDs to :class:`disco.bot.commands.CommandLevels`
        which is used for the default commands_level_getter.
    plugins : list[string]
        List of plugin modules to load.
    commands_enabled : bool
        Whether this bot instance should utilize command parsing. Generally this
        should be true, unless your bot is only handling events and has no user
        interaction.
    commands_require_mention : bool
        Whether messages must mention the bot to be considered for command parsing.
    commands_mention_rules : dict(str, bool)
        A dictionary describing what mention types can be considered a mention
        of the bot when using :attr:`commands_require_mention`. This dictionary
        can contain the following keys: `here`, `everyone`, `role`, `user`. When
        a key's value is set to true, the mention type will be considered for
        command parsing.
    commands_prefix : str
        A string prefix that is required for a message to be considered for
        command parsing.  **DEPRECATED**
    command_prefixes : list[string]
        A list of string prefixes that are required for a message to be considered
        for command parsing.
    commands_prefix_getter : Optional[function]
        A function which takes in a message object and returns an array of strings
        (prefixes).
    commands_allow_edit : bool
        If true, the bot will reparse an edited message if it was the last sent
        message in a channel, and did not previously trigger a command. This is
        helpful for allowing edits to typed commands.
    commands_level_getter : function
        If set, a function which when given a GuildMember or User, returns the
        relevant :class:`disco.bot.commands.CommandLevels`.
    commands_group_abbrev : bool
        If true, command groups may be abbreviated to the least common variation.
        E.g. the grouping 'test' may be abbreviated down to 't', unless 'tag' exists,
        in which case it may be abbreviated down to 'te'.
    plugin_config_provider : Optional[function]
        If set, this function will replace the default configuration loading
        function, which normally attempts to load a file located at config/plugin_name.fmt
        where fmt is the plugin_config_format. The function here should return
        a valid configuration object which the plugin understands.
    plugin_config_format : str
        The serialization format plugin configuration files are in.
    plugin_config_dir : str
        The directory plugin configuration is located within.
    http_enabled : bool
        Whether to enable the built-in Flask server which allows plugins to handle
        and route HTTP requests.
    http_logging : bool
        Whether to enable the built-in wsgi logging mechanism.
    http_host : str
        The host string for the HTTP Flask server (if enabled).
    http_port : int
        The port for the HTTP Flask server (if enabled).
    """
    deprecated = {'commands_prefix': 'command_prefixes'}

    levels = {}
    plugins = []
    plugin_config = {}
    shared_config = {}

    commands_enabled = True
    commands_require_mention = True
    commands_mention_rules = {
        # 'here': False,
        'everyone': False,
        'role': True,
        'user': True,
    }
    commands_prefix = ''  # now deprecated
    command_prefixes = []
    commands_prefix_getter = None
    commands_allow_edit = False
    commands_level_getter = None
    commands_group_abbrev = True

    plugin_config_provider = None
    plugin_config_format = 'json'
    plugin_config_dir = 'config'

    storage_enabled = False
    storage_fsync = True
    storage_serializer = 'json'
    storage_path = 'storage.json'

    http_enabled = False
    http_logging = True
    http_host = '0.0.0.0'
    http_port = 7575


class Bot(LoggingClass):
    """
    Disco's implementation of a simple but extendable Discord bot. Bots consist
    of a set of plugins, and a Disco Client.

    Parameters
    ----------
    client : :class:`disco.client.Client`
        The client this bot should utilize for its connection.
    config : Optional[:class:`BotConfig`]
        The configuration to use for this bot. If not provided will use the defaults
        inside :class:`BotConfig`.

    Attributes
    ----------
    client : `disco.client.Client`
        The client instance for this bot.
    config : `BotConfig`
        The bot configuration instance for this bot.
    plugins : dict(str, :class:`disco.bot.plugin.Plugin`)
        Any plugins this bot has loaded.
    """
    def __init__(self, client, config=None):
        self.client = client
        self.config = config or BotConfig()

        # Shard manager
        self.shards = None

        # The context carries information about events in a threadlocal storage
        self.ctx = ThreadLocal()

        # The storage object acts as a dynamic contextual aware store
        self.storage = None
        if self.config.storage_enabled:
            self.storage = Storage(self.ctx, self.config.from_prefix('storage'))

        # If the manhole is enabled, add this bot as a local
        if self.client.config.manhole_enable:
            self.client.manhole_locals['bot'] = self

        # Setup HTTP server (Flask app) if enabled
        self.http = None
        if self.config.http_enabled and int(self.client.config.shard_id) == 0:
            try:
                from flask import Flask
            except ImportError:
                self.log.warning('Failed to enable HTTP server, Flask is not installed')

            self.log.info(f'Starting HTTP server bound to {self.config.http_host}:{self.config.http_port}')
            self.http = Flask('disco')
            self.http_server = WSGIServer((self.config.http_host, self.config.http_port), self.http, log=self.log if self.config.http_logging else None)
            self.http_server_greenlet = gevent.spawn(self.http_server.serve_forever)

        self.plugins = {}
        self.group_abbrev = {}

        # Only bind event listeners if we're going to parse commands
        if self.config.commands_enabled and (self.config.commands_require_mention or len(self.config.command_prefixes)):
            self.client.events.on('MessageCreate', self.on_message_create)

            if self.config.commands_allow_edit:
                self.client.events.on('MessageUpdate', self.on_message_update)

        # If we have a level getter, and it is a string, try to load it
        if isinstance(self.config.commands_level_getter, str):
            mod, func = self.config.commands_level_getter.rsplit('.', 1)
            mod = importlib.import_module(mod)
            self.config.commands_level_getter = getattr(mod, func)

        # Stores the last message for every single channel
        self.last_message_cache = {}

        # Stores a giant regex matcher for all commands
        self.command_matches_re = None

        # Finally, load all the plugin modules that where passed with the config
        for plugin_mod in self.config.plugins:
            self.add_plugin_module(plugin_mod)

        # Convert our configured mapping of entities to levels into something
        #  we can actually use. This ensures IDs are converted properly, and maps
        #  any level names (e.g. `role_id: admin`) map to their numerical values.
        for entity_id, level in tuple(self.config.levels.items()):
            del self.config.levels[entity_id]
            entity_id = int(entity_id) if str(entity_id).isdigit() else entity_id
            level = int(level) if str(level).isdigit() else get_enum_value_by_name(CommandLevels, level)
            self.config.levels[entity_id] = level

    @classmethod
    def from_cli(cls, *plugins):
        """
        Creates a new instance of the bot using the utilities inside the
        :mod:`disco.cli` module. Allows passing in a set of uninitialized
        plugin classes to load.

        Parameters
        ---------
        plugins : Optional[list(:class:`disco.bot.plugin.Plugin`)]
            Any plugins to load after creating the new bot instance.
        """
        from disco.cli import disco_main
        inst = cls(disco_main())

        for plugin in plugins:
            inst.add_plugin(plugin)

        return inst

    @property
    def commands(self):
        """
        Generator of all commands the bots plugins have defined.
        """
        for plugin in self.plugins.values():
            for command in plugin.commands:
                yield command

    def recompute(self):
        """
        Called when a plugin is loaded/unloaded to recompute internal state.
        """
        if self.config.commands_group_abbrev:
            groups = {command.group for command in self.commands if command.group}
            self.group_abbrev = self.compute_group_abbrev(groups)

        self.compute_command_matches_re()

    def compute_group_abbrev(self, groups):
        """
        Computes all possible abbreviations for a command grouping.
        """
        # For the first pass, we just want to compute each groups possible
        #  abbreviations that don't conflict with each other.
        possible = {}
        for group in groups:
            for index in range(1, len(group)):
                current = group[:index]
                if current in possible:
                    possible[current] = None
                else:
                    possible[current] = group

        # Now, we want to compute the actual shortest abbreviation out of the
        #  possible ones
        result = {}
        for abbrev, group in possible.items():
            if not group:
                continue

            if group in result:
                if len(abbrev) < len(result[group]):
                    result[group] = abbrev
            else:
                result[group] = abbrev

        return result

    def compute_command_matches_re(self):
        """
        Computes a single regex which matches all possible command combinations.
        """
        commands = tuple(self.commands)
        re_str = '|'.join(command.regex(grouped=False) for command in commands)
        if re_str:
            self.command_matches_re = re.compile(re_str, re.I)
        else:
            self.command_matches_re = None

    def get_commands_for_message(self, require_mention, mention_rules, prefixes, msg=None, content=None):
        """
        Generator of all commands that a given message object triggers, based on
        the bots plugins and configuration.

        Parameters
        ---------
        require_mention : bool
            Checks if the message starts with a mention (and then ignores the prefix(es))
        mention_rules : dict(str, bool)
            Whether `user`, `everyone`, and `role` mentions are allowed. Defaults to:
            `{'user': True, 'everyone': False, 'role': False}`
        prefixes : list[string]
            A list of prefixes to check the message starts with.
        msg : :class:`disco.types.message.Message`
            The message object to parse and find matching commands for.
        content : str
            The content a message would contain if we were providing a command from one.

        Yields
        -------
        tuple(:class:`disco.bot.command.Command`, `re.MatchObject`)
            All commands the message triggers.
        """
        if not (require_mention or len(prefixes)):
            return []

        content = msg.content if msg else content

        if require_mention and msg:
            mention_direct = msg.is_mentioned(self.client.state.me)
            mention_everyone = msg.mention_everyone

            mention_roles = []
            if msg.guild:
                mention_roles = tuple(filter(lambda r: msg.is_mentioned(r),
                                            msg.guild.get_member(self.client.state.me).roles))

            if any((
                mention_rules.get('user', True) and mention_direct,
                mention_rules.get('everyone', False) and mention_everyone,
                mention_rules.get('role', False) and any(mention_roles),
                msg.channel.is_dm,
            )):
                if mention_direct:
                    if msg.guild:
                        member = msg.guild.get_member(self.client.state.me)
                        if member:
                            # Filter both the normal and nick mentions
                            content = content.replace(member.user.mention, '', 1)
                    else:
                        content = content.replace(self.client.state.me.mention, '', 1)
                elif mention_everyone:
                    content = content.replace('@everyone', '', 1)
                elif mention_roles:
                    for role in mention_roles:
                        content = content.replace('<@{}>'.format(role), '', 1)
                else:
                    return []

            content = content.lstrip()
        if len(prefixes):
            # Scan through the prefixes to find the first one that matches.
            # This may lead to unexpected results, but said unexpectedness
            # should be easy to avoid. An example of the unexpected results
            # that may occur would be if one prefix was `!` and one was `!a`.
            proceed = False
            for prefix in prefixes:
                if prefix and content.startswith(prefix):
                    content = content[len(prefix):]
                    proceed = True
                    break

            if not proceed:
                return []

        try:
            if not self.command_matches_re or not self.command_matches_re.match(content, concurrent=True):
                return []
        except:
            if not self.command_matches_re or not self.command_matches_re.match(content):
                return []

        options = []
        for command in self.commands:
            try:
                match = command.compiled_regex.match(content, concurrent=True)
            except:
                match = command.compiled_regex.match(content)
            if match:
                options.append((command, match))

        return sorted(options, key=lambda obj: obj[0].group is None)

    def get_level(self, actor):
        level = CommandLevels.DEFAULT

        if callable(self.config.commands_level_getter):
            level = self.config.commands_level_getter(self, actor)
        else:
            if actor.id in self.config.levels:
                level = self.config.levels[actor.id]

            if isinstance(actor, GuildMember):
                for rid in actor.roles:
                    if rid in self.config.levels and self.config.levels[rid] > level:
                        level = self.config.levels[rid]

        return level

    def check_command_permissions(self, command, event):
        if not command.level:
            return True

        if event.message:
            level = self.get_level(event.author if not event.guild else event.member)
        elif event.interaction:
            level = self.get_level(event.interaction.user if not event.interaction.member else event.interaction.member)

        if level >= command.level:
            return True
        return False

    def handle_command_event(self, event, content=None):
        """
        Attempts to handle a newly created or edited command events in the context of
        command parsing/triggering. Calls all relevant commands the message triggers.

        Parameters
        ---------
        event : :class:'Event'
            The newly created or updated event object to parse/handle.
        content : :class:'Message'
            Used for on_message_update below

        Returns
        -------
        bool
            Whether any commands where successfully triggered by the message.
        """
        if self.config.commands_enabled:
            commands = []
            custom_message_prefixes = None
            if event.message:
                if self.config.commands_prefix_getter:
                    custom_message_prefixes = (self.config.commands_prefix_getter(event.message))

                commands = self.get_commands_for_message(
                    self.config.commands_require_mention,
                    self.config.commands_mention_rules,
                    custom_message_prefixes or self.config.command_prefixes,
                    event.message,
                )

            elif content:
                commands = self.get_commands_for_message(False, {}, ['/'], content=content)

            if not len(commands):
                return False

            for command, match in commands:
                if not self.check_command_permissions(command, event):
                    continue

                if command.plugin.execute(CommandEvent(command, event, match)):
                    return True
            return False
        return

    def on_message_create(self, event):
        if event.author.id == self.client.state.me.id:
            return

        result = self.handle_command_event(event)

        if self.config.commands_allow_edit:
            self.last_message_cache[event.message.channel_id] = (event.message, result)

    def on_message_update(self, event):
        if not self.config.commands_allow_edit:
            return

        # Ignore messages that do not have content, these can happen when only
        #  some message fields are updated.
        if not event.message.content:
            return

        obj = self.last_message_cache.get(event.message.channel_id)
        if not obj:
            return

        msg, triggered = obj
        if msg.id == event.message.id and not triggered:
            msg.inplace_update(event.message)
            triggered = self.handle_message(msg)

            self.last_message_cache[msg.channel_id] = (msg, triggered)

    def add_plugin(self, inst, config=None, ctx=None):
        """
        Adds and loads a plugin, based on its class.

        Parameters
        ----------
        inst : subclass (or instance therein) of `disco.bot.plugin.Plugin`
            Plugin class to initialize and load.
        config : Optional
            The configuration to load the plugin with.
        ctx : Optional[dict]
            Context (previous state) to pass the plugin. Usually used along w/
            unload.
        """
        if inspect.isclass(inst):
            if not config:
                if callable(self.config.plugin_config_provider):
                    config = self.config.plugin_config_provider(inst)
                else:
                    config = self.load_plugin_config(inst)

            inst = inst(self, config)

        if inst.__class__.__name__ in self.plugins:
            self.log.warning('Attempted to add already added plugin %s', inst.__class__.__name__)
            raise Exception('Cannot add already added plugin: {}'.format(inst.__class__.__name__))

        self.ctx['plugin'] = self.plugins[inst.__class__.__name__] = inst
        self.plugins[inst.__class__.__name__].load(ctx or {})
        self.recompute()
        self.ctx.drop()

    def rmv_plugin(self, cls):
        """
        Unloads and removes a plugin based on its class.

        Parameters
        ----------
        cls : subclass of :class:`disco.bot.plugin.Plugin`
            Plugin class to unload and remove.
        """
        if not hasattr(cls, '__name__') or cls.__name__ not in self.plugins:
            try:
                cls = cls.__class__
                assert cls.__name__ in self.plugins
            except:
                raise Exception('Cannot remove non-existent plugin: {}'.format(cls.__name__))

        ctx = {}
        self.plugins[cls.__name__].unload(ctx)
        del self.plugins[cls.__name__]
        self.recompute()
        return ctx

    def reload_plugin(self, cls):
        """
        Reloads a plugin.
        """
        if not hasattr(cls, '__name__') or cls.__name__ not in self.plugins:
            try:
                cls = cls.__class__
                assert cls.__name__ in self.plugins
            except:
                raise Exception('Cannot reload non-existent plugin: {}'.format(cls.__name__))

        config = self.plugins[cls.__name__].config

        ctx = self.rmv_plugin(cls)
        module = importlib.reload(inspect.getmodule(cls))
        self.add_plugin(getattr(module, cls.__name__), config, ctx)

    def run_forever(self):
        """
        Runs this bots core loop forever.
        """
        self.client.run_forever()

    def add_plugin_module(self, path, config=None):
        """
        Adds and loads a plugin, based on its module path.
        """
        self.log.info(f'Adding plugin module at path "{path}"')
        mod = importlib.import_module(path)
        loaded = False

        plugins = find_loadable_plugins(mod)
        for plugin in plugins:
            loaded = True
            self.add_plugin(plugin, config)

        if not loaded:
            raise Exception(f'Could not find any plugins to load within module {path}')

    def load_plugin_config(self, cls):
        name = cls.__name__.lower()
        if name.endswith('plugin'):
            name = name[:-6]

        path = os.path.join(
            self.config.plugin_config_dir, name) + '.' + self.config.plugin_config_format

        data = {}
        if self.config.shared_config:
            data.update(self.config.shared_config)

        if name in self.config.plugin_config:
            data.update(self.config.plugin_config[name])

        if os.path.exists(path):
            with open(path, 'r') as f:
                data.update(Serializer.loads(self.config.plugin_config_format, f.read()))
                f.close()

        if hasattr(cls, 'config_cls'):
            inst = cls.config_cls()
            if data:
                inst.update(data)
            return inst

        return data
