"""
Configuration for the StockRoom inventory system.

Everything the application needs to know about its environment lives
here, so no connection details are scattered through the code. Values
are read from environment variables where they exist and fall back to
the WAMP defaults, which is what you get on a fresh install.
"""

import os


class Config:
    # --- Flask ---------------------------------------------------
    # Signs the session cookie. On a real deployment this must come
    # from the environment and never be committed to Git.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-before-deployment")

    # --- MySQL (WAMP defaults) -----------------------------------
    # A fresh WAMP install listens on 3306 with user 'root' and an
    # empty password. If you set a root password in phpMyAdmin, put
    # it in MYSQL_PASSWORD below.
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DB = os.environ.get("MYSQL_DB", "inventory_db")

    # --- Application ---------------------------------------------
    CURRENCY = "LKR"
    ITEMS_PER_PAGE = 10
