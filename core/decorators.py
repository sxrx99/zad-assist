from functools import wraps
from .db_pool import DatabaseConnectionPool

def use_db_pool(cls):
    """Class decorator to manage database connections."""
    
    original_init = cls.__init__

    @wraps(original_init)
    def new_init(self, *args, **kwargs):
        self.db_pool = DatabaseConnectionPool()  # Ensure db_pool is initialized
        original_init(self, *args, **kwargs)

    cls.__init__ = new_init

    # Wrap each method that may require a database connection
    for attr in dir(cls):
        # Skip special methods and DRF's internal methods
        if attr.startswith("__") or attr in ["get_extra_actions", "as_view", "get_queryset"]:
            continue

        method = getattr(cls, attr)
        if callable(method):
            # Create a closure that captures the current method
            def create_wrapper(method_ref):
                @wraps(method_ref)
                def wrapper(self, *args, **kwargs):
                    connection = self.db_pool.get_connection()
                    try:
                        return method_ref(self, connection, *args, **kwargs)
                    finally:
                        self.db_pool.release_connection(connection)
                return wrapper
            
            # Set the wrapped method
            setattr(cls, attr, create_wrapper(method))

    return cls