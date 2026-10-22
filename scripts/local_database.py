"""Create/start only this project's isolated development cluster; never touches system DBs."""

import os
import secrets
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
private = root / ".private"
private.mkdir(exist_ok=True, mode=0o700)
data = private / "pgdata"
password_file = private / "pgpassword"
if not password_file.exists():
    password_file.write_text(secrets.token_urlsafe(36))
    password_file.chmod(0o600)
password = password_file.read_text().strip()
if not data.exists():
    subprocess.run(
        [
            "initdb",
            "-D",
            str(data),
            "-U",
            "eku",
            "--encoding=UTF8",
            "--locale=C",
            "--auth-local=trust",
            "--auth-host=scram-sha-256",
            "--pwfile",
            str(password_file),
        ],
        check=True,
    )
if subprocess.run(["pg_ctl", "-D", str(data), "status"], capture_output=True).returncode:
    subprocess.run(
        [
            "pg_ctl",
            "-D",
            str(data),
            "-l",
            str(private / "postgres.log"),
            "-o",
            "-p 55432 -h 127.0.0.1 -k ''",
            "start",
        ],
        check=True,
    )
env = dict(os.environ, PGPASSWORD=password)
exists = subprocess.run(
    [
        "psql",
        "-h",
        "127.0.0.1",
        "-p",
        "55432",
        "-U",
        "eku",
        "-d",
        "postgres",
        "-Atc",
        "SELECT 1 FROM pg_database WHERE datname='eku'",
    ],
    check=True,
    env=env,
    capture_output=True,
    text=True,
).stdout.strip()
if not exists:
    subprocess.run(
        ["createdb", "-h", "127.0.0.1", "-p", "55432", "-U", "eku", "eku"], check=True, env=env
    )
env_file = root / ".env"
if not env_file.exists():
    env_file.write_text(
        f"DJANGO_ENV=development\nDJANGO_SECRET_KEY={secrets.token_urlsafe(64)}\nDATABASE_URL=postgresql://eku:{password}@127.0.0.1:55432/eku\nDJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver\n"
    )
    env_file.chmod(0o600)
print("PostgreSQL lokal proyek siap di 127.0.0.1:55432; konfigurasi privat di .env.")
