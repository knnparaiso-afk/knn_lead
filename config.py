import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Sem DATABASE_URL, a aplicação continua usando SQLite localmente.
# No Render, defina DATABASE_URL com a URL do PostgreSQL.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or None
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    # Normaliza URLs antigas para o esquema aceito pelo driver PostgreSQL.
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    os.path.join(BASE_DIR, "instance", "knn.db")
)

IS_PRODUCTION = os.getenv("RENDER", "").strip().lower() == "true"
if IS_PRODUCTION and not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não está configurada. Defina a URL interna do PostgreSQL no Render."
    )

_secret_key = os.getenv("SECRET_KEY", "").strip()
if IS_PRODUCTION and not _secret_key:
    raise RuntimeError(
        "Configure SECRET_KEY nas variáveis de ambiente antes de iniciar em produção."
    )
SECRET_KEY = _secret_key or "dev-secret-key-apenas-para-uso-local"

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
_admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
if IS_PRODUCTION and not _admin_password:
    raise RuntimeError(
        "Configure ADMIN_PASSWORD nas variáveis de ambiente antes de iniciar em produção."
    )
ADMIN_PASSWORD = _admin_password or "knn123"

BASE_URL = os.getenv(
    "BASE_URL",
    "http://192.168.1.44:5000"
).strip().rstrip("/")

try:
    ENGLISH_PASS_REQUIRED = int(os.getenv("ENGLISH_PASS_REQUIRED", "3"))
except ValueError as exc:
    raise RuntimeError("ENGLISH_PASS_REQUIRED precisa ser um número inteiro.") from exc

if ENGLISH_PASS_REQUIRED < 1:
    raise RuntimeError("ENGLISH_PASS_REQUIRED precisa ser pelo menos 1.")
