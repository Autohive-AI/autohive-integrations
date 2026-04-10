try:
    from .shopify_customer import shopify_customer
except ImportError:
    from shopify_customer import shopify_customer

__all__ = ['shopify_customer']
