import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DATABASE_PATH = os.path.join(BASE_DIR, "instance", "knn.db")

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-secret-key-troque-em-producao"
)

ADMIN_USERNAME = os.getenv(
    "ADMIN_USERNAME",
    "admin"
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "knn123"
)

# Durante o desenvolvimento:
BASE_URL = os.getenv(
    "BASE_URL",
    "http://192.168.1.109:5000"
)

ENGLISH_PASS_REQUIRED = 3
