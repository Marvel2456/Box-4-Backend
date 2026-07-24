import os
import sys
import time
import psycopg2

def wait_for_db():
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', 'db')
    db_port = os.getenv('DB_PORT', '5432')

    if db_name and db_user:
        print("Waiting for PostgreSQL database to start...")
        for i in range(30):
            try:
                conn = psycopg2.connect(
                    dbname=db_name,
                    user=db_user,
                    password=db_password,
                    host=db_host,
                    port=db_port,
                    connect_timeout=2
                )
                conn.close()
                print("PostgreSQL database is available!")
                return
            except psycopg2.OperationalError as e:
                print(f"PostgreSQL not ready yet (attempt {i+1}/30)...")
                time.sleep(1)
        print("Error: PostgreSQL connection timed out.")
        sys.exit(1)
    else:
        print("No PostgreSQL configuration detected. Skipping wait (using SQLite).")

if __name__ == '__main__':
    wait_for_db()
