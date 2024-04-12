try:
    from regex import compile as re_compile
except ImportError:
    from re import compile as re_compile


# Zero width (non-rendering) space that can be used to escape mentions
ZERO_WIDTH_SPACE = '\u200B'

# A grave-looking character that can be used to escape codeblocks
MODIFIER_GRAVE_ACCENT = '\u02CB'

# This regex matches all possible mention combinations.
MENTION_RE = re_compile('<?([@|#][!|&]?[0-9]+|@everyone|@here)>?')


def _re_sub_mention(mention):
    mention = mention.group(1)
    if '#' in mention:
        return ('#' + ZERO_WIDTH_SPACE).join(mention.split('#', 1))
    elif '@' in mention:
        return ('@' + ZERO_WIDTH_SPACE).join(mention.split('@', 1))
    else:
        return mention


def S(text, escape_mentions=True, escape_codeblocks=False, escape_rtl=False):
    if not isinstance(text, str):
        text = str(text)

    if escape_mentions:
        text = MENTION_RE.sub(_re_sub_mention, text)

    if escape_codeblocks:
        text = text.replace('`', MODIFIER_GRAVE_ACCENT)

    if escape_rtl:
        text = '\u202B' + text + '\u202B'

    return text
