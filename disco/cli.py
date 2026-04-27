"""
The CLI module is a small utility that can be used as an easy entry point for
creating and running bots/clients.
"""
from libnacl import nacl  # silences fork() warnings
from gevent.monkey import patch_all as monkey_patch_all; monkey_patch_all()

from os import path as os_path
import logging
from argparse import ArgumentParser


parser = ArgumentParser()

# Command line specific arguments
parser.add_argument('--run-bot', help='Run a disco bot on this client', action='store_true', default=False)
parser.add_argument('--plugin', help='Load plugins into the bot', nargs='*', default=[])
parser.add_argument('--config', help='Configuration file', default=None)
parser.add_argument('--shard-auto', help='Automatically run all shards', action='store_true', default=False)

# Configuration overrides
parser.add_argument('--token', help='Bot Authentication Token', default=None)
parser.add_argument('--shard-id', help='Current shard number/id', default=None)
parser.add_argument('--shard-count', help='Total number of shards', default=None)
parser.add_argument('--max-reconnects', help='Maximum reconnect attempts', default=None)
parser.add_argument('--log-level', help='log level', default=None)
parser.add_argument('--manhole', action='store_true', help='Enable the manhole', default=None)
parser.add_argument('--manhole-bind', help='host:port for the manhole to bind to', default=None)
parser.add_argument('--encoder', help='Encoder for gateway data', default=None)
parser.add_argument('--gateway_url', help='WS API endpoint to connect to', default=None)
parser.add_argument('--http_gateway_url', help='HTTP API endpoint to connect to', default=None)
parser.add_argument('--gateway_version', help='API endpoint version', default=None)
parser.add_argument('--shutdown_on_cloudflare_429', help='Shutdown on Cloudflare ratelimiting', default=False)
parser.add_argument('--max_queries_per_second', help='Max number of outbound queries to the API per second', default=None)


# Mapping of argument names to configuration overrides
CONFIG_OVERRIDE_MAPPING = {
    'token': 'token',
    'shard_id': 'shard_id',
    'shard_count': 'shard_count',
    'max_reconnects': 'max_reconnects',
    'log_level': 'log_level',
    'manhole': 'manhole_enable',
    'manhole_bind': 'manhole_bind',
    'encoder': 'encoder',
    'gateway_url': 'gateway_url',
    'http_gateway_url': 'http_gateway_url',
    'gateway_version': 'gateway_version',
    'shutdown_on_cloudflare_429': 'shutdown_on_cloudflare_429',
    'max_queries_per_second': 'max_queries_per_second',
}


def disco_main(run=False):
    """
    Creates an argument parser and parses a standard set of command line arguments,
    creating a new :class:`Client`.

    Returns
    -------
    :class:`Client`
        A new Client from the provided command line arguments.
    """
    from disco.client import Client, ClientConfig
    from disco.bot import Bot, BotConfig
    from disco.util.logging import setup_logging

    # Parse out all command line arguments
    args = parser.parse_args()

    # Create the base configuration object
    if args.config:
        config = ClientConfig.from_file(args.config)
    else:
        if os_path.exists('config.json'):
            config = ClientConfig.from_file('config.json')
        elif os_path.exists('config.yaml'):
            config = ClientConfig.from_file('config.yaml')
        else:
            config = ClientConfig()

    for arg_key, config_key in CONFIG_OVERRIDE_MAPPING.items():
        if getattr(args, arg_key) is not None:
            setattr(config, config_key, getattr(args, arg_key))

    # Set up the auto-sharder
    if args.shard_auto:
        from disco.gateway.sharder import AutoSharder
        AutoSharder(config).run()
        return

    # Setup logging based on the configured level
    setup_logging(level=getattr(logging, config.log_level.upper()))

    # Build out client object
    client = Client(config)

    # If applicable, build the bot and load plugins
    bot = None
    if args.run_bot or hasattr(config, 'bot'):
        bot_config = BotConfig(config.bot) if hasattr(config, 'bot') else BotConfig()
        if not hasattr(bot_config, 'plugins'):
            bot_config.plugins = args.plugin
        else:
            bot_config.plugins += args.plugin

        bot = Bot(client, bot_config)

    if run:
        (bot or client).run_forever()

    return bot or client


if __name__ == '__main__':
    try:
        disco_main(True)
    except KeyboardInterrupt:
        print('\nShutting down...')
    finally:
        from sys import exit as sys_exit
        sys_exit(0)
