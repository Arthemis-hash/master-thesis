#!/usr/bin/env python3
"""
Database initialization script for Air Quality Platform
Creates admin and test users on first startup
Run: python3 init_admin.py
"""

import os
import sys
import bcrypt

# Database configuration from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://airquality_user:CHANGE_ME_STRONG_PASSWORD@postgres:5432/airquality_db",
)


def create_admin_users():
    """Create admin and test users in the database"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    # Parse DATABASE_URL
    # Format: postgresql://user:password@host:port/dbname
    db_parts = DATABASE_URL.replace("postgresql://", "").split("/")
    db_host_port = db_parts[0].split("@")
    db_creds = db_host_port[0].split(":")
    db_host = db_host_port[1].split(":")
    db_name = db_parts[1].split("?")[0]

    db_user = db_creds[0]
    db_pass = db_creds[1] if len(db_creds) > 1 else ""
    db_host = db_host[0]
    db_port = db_host[1] if len(db_host) > 1 else "5432"

    print(f"Connecting to database at {db_host}:{db_port}/{db_name}")

    try:
        conn = psycopg2.connect(
            host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_pass
        )
        conn.autocommit = True
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Hash password
        password = "test123"
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt(rounds=10)
        ).decode("utf-8")

        print(f"Password hash generated: {password_hash[:20]}...")

        # Create admin user (with RGPD fields)
        cursor.execute(
            """
            INSERT INTO users (email, password_hash, first_name, last_name, role, is_active, gdpr_consent_given)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO NOTHING
            RETURNING id, email
        """,
            (
                "admin@airquality.local",
                password_hash,
                "Admin",
                "User",
                "admin",
                True,
                True,
            ),
        )

        admin_result = cursor.fetchone()
        if admin_result:
            print(f"✓ Admin user created: {admin_result['email']}")
        else:
            print("✓ Admin user already exists")

        # Create test user (with RGPD fields)
        cursor.execute(
            """
            INSERT INTO users (email, password_hash, first_name, last_name, role, is_active, gdpr_consent_given)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO NOTHING
            RETURNING id, email
        """,
            (
                "test@airquality.local",
                password_hash,
                "Test",
                "User",
                "user",
                True,
                True,
            ),
        )

        test_result = cursor.fetchone()
        if test_result:
            print(f"✓ Test user created: {test_result['email']}")
        else:
            print("✓ Test user already exists")

        cursor.close()
        conn.close()

        print("\n========================================")
        print("Database initialization complete!")
        print("========================================")
        print("Admin credentials:")
        print("  Email: admin@airquality.local")
        print("  Password: test123")
        print("")
        print("Test user credentials:")
        print("  Email: test@airquality.local")
        print("  Password: test123")
        print("========================================")

    except psycopg2.OperationalError as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    create_admin_users()
