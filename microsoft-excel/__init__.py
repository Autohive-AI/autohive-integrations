try:
    from .microsoft_excel import microsoft_excel
except ImportError:
    from microsoft_excel import microsoft_excel

__all__ = ["microsoft_excel"]
