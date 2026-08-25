"""
Database access layer.

One MySQL connection is opened per HTTP request and closed when that
request finishes. Flask's `g` object is the right place to hang it:
`g` is scoped to a single request, so two users hitting the site at
the same time never share a connection.

Every query in this application goes through query_all / query_one /
execute below. They all use parameterised SQL (%s placeholders), which
is what stops SQL injection - the driver sends the query and the values
separately, so a value can never be read as SQL.
"""

import pymysql
from pymysql.cursors import DictCursor
from flask import g, current_app


def get_db():
    """Return the connection for this request, opening it if needed."""
    if "db" not in g:
        g.db = pymysql.connect(
            host=current_app.config["MYSQL_HOST"],
            port=current_app.config["MYSQL_PORT"],
            user=current_app.config["MYSQL_USER"],
            password=current_app.config["MYSQL_PASSWORD"],
            database=current_app.config["MYSQL_DB"],
            charset="utf8mb4",
            cursorclass=DictCursor,   # rows arrive as dicts, not tuples
            autocommit=False,         # we commit explicitly, so we can roll back
        )
    return g.db


def close_db(exception=None):
    """Close the request's connection. Registered as a teardown handler."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_all(sql, params=None):
    """Run a SELECT and return every row as a list of dicts."""
    with get_db().cursor() as cursor:
        cursor.execute(sql, params or ())
        return cursor.fetchall()


def query_one(sql, params=None):
    """Run a SELECT and return the first row as a dict, or None."""
    with get_db().cursor() as cursor:
        cursor.execute(sql, params or ())
        return cursor.fetchone()


def execute(sql, params=None):
    """
    Run an INSERT / UPDATE / DELETE and commit.

    Returns the new primary key for an INSERT, or the number of rows
    affected otherwise. If anything raises, the transaction is rolled
    back so a half-finished write is never left in the database.
    """
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or ())
            result = cursor.lastrowid or cursor.rowcount
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise


def init_app(app):
    """Attach close_db to the app so connections are always released."""
    app.teardown_appcontext(close_db)
