from dill import dumps as dill_dumps, loads as dill_loads
from gipc import pipe as gipc_pipe, start_process as gipc_start_process
from gevent import sleep as gevent_sleep
from gevent.event import AsyncResult as GeventAsyncResult
from gevent.pool import Pool as GeventPool
from logging import INFO as LOGGING_INFO

from disco.client import Client
from disco.bot import Bot, BotConfig
from disco.api.client import APIClient
from disco.gateway.ipc import GIPCProxy
from disco.util.logging import setup_logging, LOG_FORMAT
from disco.util.snowflake import calculate_shard
from disco.util.serializer import dump_function, load_function


def run_shard(config, shard_id, pipe):
    setup_logging(
        level=LOGGING_INFO,
        format=f'{shard_id} ' + LOG_FORMAT,
    )

    config.shard_id = shard_id
    client = Client(config)
    bot = Bot(client, BotConfig(config.bot))
    bot.sharder = GIPCProxy(bot, pipe)
    bot.shards = ShardHelper(config.shard_count, bot)
    bot.run_forever()


class ShardHelper:
    def __init__(self, count, bot):
        self.count = count
        self.bot = bot

    def keys(self):
        for sid in range(self.count):
            yield sid

    def on(self, sid, func, timeout=None):
        if sid == self.bot.client.config.shard_id:
            result = GeventAsyncResult()
            result.set(func(self.bot))
            return result

        return self.bot.sharder.call(('run_on', ), sid, dump_function(func)).wait(timeout=timeout)

    def all(self, func, timeout=None):
        pool = GeventPool(self.count)
        return dict(zip(
            range(self.count),
            pool.imap(
                lambda i: self.on(i, func, timeout),
                range(self.count),
            ),
        ))

    def for_id(self, sid, func, timeout=None):
        shard = calculate_shard(self.count, sid)
        return self.on(shard, func, timeout)


class AutoSharder:
    def __init__(self, config):
        self.config = config
        self.client = APIClient(config.token)
        self.shards = {}
        self.config.shard_count = self.client.gateway_bot_get()['shards'] if not hasattr(config, 'shard_count') else config.shard_count

    def run_on(self, sid, raw):
        func = load_function(raw)
        return self.shards[sid].execute(func).wait(timeout=15)

    def run(self):
        for shard_id in range(self.config.shard_count):
            if self.config.manhole_enable and shard_id != 0:
                self.config.manhole_enable = False

            self.start_shard(shard_id)
            gevent_sleep(6)

        setup_logging(
            level=LOGGING_INFO,
            format=f'{id} ' + LOG_FORMAT,
        )

    def start_shard(self, sid):
        cpipe, ppipe = gipc_pipe(duplex=True, encoder=dill_dumps, decoder=dill_loads)
        gipc_start_process(run_shard, (self.config, sid, cpipe), name=f'shard{sid}')
        self.shards[sid] = GIPCProxy(self, ppipe)
