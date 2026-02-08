try:
    from .microsoft_word import microsoft_word
    __all__ = ['microsoft_word']
except ImportError:
    pass
