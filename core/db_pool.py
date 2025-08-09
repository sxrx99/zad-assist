import psycopg2
from psycopg2 import pool
import os

class DatabaseConnectionPool:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnectionPool, cls).__new__(cls)
            cls._instance.connection_pool = None  
            cls._instance.initialize_pool()
        return cls._instance

    def initialize_pool(self):
        """Initialize the connection pool using environment variables or Django settings."""
        if self.connection_pool is None: 
            try:
                self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=20,  
                    user=os.getenv("PG_USER"),  # Use environment variables
                    password="admin",
                    host="postgresql",
                    port=os.getenv("PG_PORT"),
                    database=os.getenv("PG_DB"),
                )
                print("Connection pool created successfully")
            except Exception as e:
                print(f"Error initializing connection pool: {e}")
                self.connection_pool = None  # Reset on error

    def get_connection(self):
        """Get a connection from the pool."""
        if self.connection_pool is None:
            raise Exception("Connection pool is not initialized.")
        return self.connection_pool.getconn()

    def release_connection(self, connection):
        """Release a connection back to the pool."""
        if self.connection_pool is not None:
            self.connection_pool.putconn(connection)

    def close_all_connections(self):
        """Close all connections in the pool."""
        if self.connection_pool is not None:
            self.connection_pool.closeall()
            self.connection_pool = None  