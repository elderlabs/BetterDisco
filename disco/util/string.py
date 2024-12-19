try:
    from regex import sub as re_sub
except ImportError:
    from re import sub as re_sub


# Taken from inflection library
def underscore(word):
    word = re_sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', word)
    word = re_sub(r'([a-z\d])([A-Z])', r'\1_\2', word)
    word = word.replace('-', '_')
    return word.lower()
