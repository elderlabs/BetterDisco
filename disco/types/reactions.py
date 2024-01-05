from disco.types.base import SlottedModel, snowflake, Field, text, cached_property, ListField, enum, str_or_int
from disco.types.user import User


class Emoji(SlottedModel):
    """
    Represents either a standard or custom Discord emoji.

    Attributes
    ----------
    id : snowflake?
        The emoji ID (will be none if this is not a custom emoji).
    name : str
        The name of this emoji.
    animated : bool
        Whether this emoji is animated.
    """
    id = Field(snowflake)
    name = Field(text)
    user = Field(User, create=False)
    require_colons = Field(bool)
    managed = Field(bool)
    animated = Field(bool)
    available = Field(bool)
    guild_id = Field(snowflake)
    version = Field(int)

    def __str__(self):
        return '<{}:{}:{}>'.format('a' if self.animated else '', self.name, self.id if self.id else '')

    def __int__(self):
        return self.id

    def __repr__(self):
        return f'<Emoji {"id=" + str(self.id) if self.id else ""} name={self.name}>'

    def __eq__(self, other):
        if isinstance(other, Emoji):
            return self.id == other.id and self.name == other.name
        raise NotImplementedError

    @property
    def url(self):
        return 'https://cdn.discordapp.com/emojis/{}.{}'.format(self.id, 'gif' if self.animated else 'png')

    @cached_property
    def custom(self):
        return bool(self.id)


class MessageReactionCountDetails(SlottedModel):
    burst = Field(int)
    normal = Field(int)


class MessageReaction(SlottedModel):
    """
    A reaction of one emoji (multiple users) to a message.

    Attributes
    ----------
    emoji : `Emoji`
        The emoji which was reacted.
    count : int
        The number of users who reacted with this emoji.
    me : bool
        Whether the current user reacted with this emoji.
    """
    count = Field(int)
    count_details = Field(MessageReactionCountDetails)
    me = Field(bool)
    me_burst = Field(bool)
    emoji = Field(Emoji)
    burst_colors = Field(str_or_int)


class StickerTypes:
    STANDARD = 1
    GUILD = 2


class StickerFormatTypes:
    PNG = 1
    APNG = 2
    LOTTIE = 3
    GIF = 4


class StickerItem(SlottedModel):
    id = Field(snowflake)
    name = Field(text)
    format_type = Field(enum(StickerFormatTypes))


class Sticker(SlottedModel):
    id = Field(snowflake)
    pack_id = Field(snowflake)
    name = Field(text)
    description = Field(text)
    tags = Field(text)
    type = Field(enum(StickerTypes))
    format_type = Field(enum(StickerFormatTypes))
    available = Field(bool)
    guild_id = Field(snowflake)
    user = Field(User)
    sort_value = Field(int)

    def __repr__(self):
        return '<Sticker {} name={}>'.format('id=' + str(self.id) if self.id else '', self.name)

    def __str__(self):
        return self.name

    def __int__(self):
        return self.id


class StickerPack(SlottedModel):
    id = Field(snowflake)
    stickers = ListField(Sticker)
    name = Field(text)
    sku_id = Field(snowflake)
    cover_sticker_id = Field(snowflake)
    description = Field(text)
    banner_asset_id = Field(snowflake)
