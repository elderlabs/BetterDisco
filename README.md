# BetterDisco
_BetterDisco_ is an up-to-date modernized fork of Disco, a library witten by b1nzy, the creator of Discord's API, iirc. 
_Disco_ is a _library_, written in Python 3 to interface with [Discord's API](https://discord.com/developers/docs/intro) as _efficiently_ and _effectively_ as possible. 
Disco is _expressive_, and contains a _functional interface_. 
Disco is built for _performance_ and _efficiency_. 
Disco is _scalable_ and works well in large and small deployments. 
Disco is _configurable_ and _modular_. 
Disco contains evented network and IO pipes, courtesy of `gevent`. 
_Buzzwords **100**._ WYSIWYG. 


## Installation
Disco is designed to run both as a generic-use library, and as a standalone bot toolkit. Installing disco is as easy as running `pip install betterdisco-py --upgrade --no-cache-dir`, however, additional options are available for extended features, performance, and support:

| _This_                        | Installs _these_                                            | _Why?_                                                                         |
|-------------------------------|-------------------------------------------------------------|--------------------------------------------------------------------------------|
| `betterdisco-py`              | `gevent`, `requests`, `websocket-client`                    | Required for base Disco functionality.                                         |
| `betterdisco-py[http]`        | `flask`                                                     | Useful for hosting an API to interface with your bot.                          |
| `betterdisco-py[performance]` | `erlpack`, `isal`, `regex`, `pylibyaml`, `ujson`, `wsaccel` | Useful for performance improvement in several areas. _I am speed._             |
| `betterdisco-py[sharding]`    | `gipc`, `dill`                                              | Required for auto-sharding and inter-process communication.                    |
| `betterdisco-py[voice]`       | `libnacl`                                                   | Required for VC connectivity and features.                                     |
| `betterdisco-py[yaml]`        | `pyyaml`                                                    | Required for YAML support, particularly if using `config.yaml`.                |
| `betterdisco-py[all]`         | _**All of the above**, unless otherwise noted._             | **All additional packages**, for the poweruser that _absolutely needs it all_. |


## Examples
Simple bot using the built-in bot authoring tools:

```python
from disco.bot import Plugin


class SimplePlugin(Plugin):
    # Plugins provide an easy interface for listening to Discord events
    @Plugin.listen('ChannelCreate')
    def on_channel_create(self, event):
        event.channel.send_message('Woah, a new channel huh!')

    # They also provide an easy-to-use command component
    @Plugin.command('ping')
    def on_ping_command(self, event):
        event.reply('Pong!')

    # Which includes command argument parsing
    @Plugin.command('echo', '<content:str...>')
    def on_echo_command(self, event, content):
        event.reply(content)
```

Using the default bot configuration, we can now run this script like so:

`python -m disco.cli --token="MY_DISCORD_TOKEN" --run-bot --plugin simpleplugin`

And commands can be triggered by mentioning the bot (configured by the BotConfig.command_require_mention flag):

![](http://i.imgur.com/Vw6T8bi.png)

### For further information and configuration options, please refer to our documentation first and foremost.