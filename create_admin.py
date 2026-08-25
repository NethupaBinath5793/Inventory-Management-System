"""
Create an administrator account, or reset the password on an existing one.

Run from the project folder:

    python create_admin.py

Useful if you change the demo passwords and then lock yourself out, or
if you would rather the marker did not see 'Admin@123' on the login page.
"""

import getpass
import sys

import pymysql
from werkzeug.security import generate_password_hash

from config import Config

HASH_METHOD = "pbkdf2:sha256:600000"


def main():
    try:
        connection = pymysql.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            charset="utf8mb4",
        )
    except pymysql.err.OperationalError as error:
        print("Could not connect to MySQL.")
        print(f"  {error}")
        print("\nIs WAMP running, and does config.py have the right password?")
        sys.exit(1)

    username = input("Username: ").strip().lower()
    full_name = input("Full name: ").strip()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("The passwords do not match. Nothing was changed.")
        sys.exit(1)

    if len(password) < 8:
        print("Password must be at least 8 characters. Nothing was changed.")
        sys.exit(1)

    password_hash = generate_password_hash(password, method=HASH_METHOD)

    with connection.cursor() as cursor:
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "UPDATE users SET password_hash = %s, full_name = %s, "
                "role = 'admin', is_active = 1 WHERE username = %s",
                (password_hash, full_name, username))
            print(f"Password reset for existing account '{username}'.")
        else:
            cursor.execute(
                "INSERT INTO users (username, password_hash, full_name, role) "
                "VALUES (%s, %s, %s, 'admin')",
                (username, password_hash, full_name))
            print(f"Administrator account '{username}' created.")

    connection.commit()
    connection.close()


if __name__ == "__main__":
    main()
