from datetime import datetime, UTC

UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
DISCORD_EPOCH = 1420070400000


def to_datetime(snowflake):
    """
    Converts a snowflake to a UTC datetime.
    """
    return datetime.fromtimestamp(to_unix(snowflake), tz=UTC)


def to_unix(snowflake):
    return to_unix_ms(snowflake) / 1000


def to_unix_ms(snowflake):
    return (int(snowflake) >> 22) + DISCORD_EPOCH


def from_datetime(date):
    return from_timestamp((date - UNIX_EPOCH).total_seconds())


def from_timestamp(ts):
    return from_timestamp_ms(ts * 1000.0)


def from_timestamp_ms(ts):
    return int(ts - DISCORD_EPOCH) << 22


def to_snowflake(i):
    if isinstance(i, int):
        return i
    elif isinstance(i, str):
        return int(i)
    elif hasattr(i, 'id'):
        return i.id
    elif isinstance(i, datetime):
        return from_datetime(i)

    raise Exception('{} ({}) is not convertible to a snowflake'.format(type(i), i))


def calculate_shard(shard_count, guild_id):
    return (guild_id >> 22) % shard_count
