from disco.types.user import User
from disco.types.base import SlottedModel, snowflake, Field, text, cached_property, ListField, enum


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
    animated = Field(bool)

    @cached_property
    def custom(self) -> bool:
        return bool(self.id)

    def __eq__(self, other):
        if isinstance(other, Emoji):
            return self.id == other.id and self.name == other.name
        raise NotImplementedError

    def to_string(self) -> str:
        if self.id:
            return '{}:{}'.format(self.name, self.id)
        return self.name


class MessageReactionEmoji(Emoji):
    """
    Represents an emoji which was used as a reaction on a message.

    Attributes
    ----------
    count : int
        The number of users who reacted with this emoji.
    me : bool
        Whether the current user reacted with this emoji.
    emoji : `MessageReactionEmoji`
        The emoji which was reacted.
    """
    id = Field(snowflake)
    name = Field(text)
    roles = ListField(snowflake)
    user = Field(User)
    require_colons = Field(bool)
    managed = Field(bool)
    animated = Field(bool)


class MessageReaction(SlottedModel):
    """
    A reaction of one emoji (multiple users) to a message.

    Attributes
    ----------
    emoji : `MessageReactionEmoji`
        The emoji which was reacted.
    count : int
        The number of users who reacted with this emoji.
    me : bool
        Whether the current user reacted with this emoji.
    """
    emoji = Field(MessageReactionEmoji)
    count = Field(int)
    me = Field(bool)


class StickerTypes:
    STANDARD = 1
    GUILD = 2


class StickerFormatTypes:
    PNG = 1
    APNG = 2
    LOTTIE = 3


class StickerItemStructure(SlottedModel):
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


class StickerPack(SlottedModel):
    id = Field(snowflake)
    stickers = ListField(Sticker)
    name = Field(text)
    sku_id = Field(snowflake)
    cover_sticker_id = Field(snowflake)
    description = Field(text)
    banner_asset_id = Field(snowflake)
