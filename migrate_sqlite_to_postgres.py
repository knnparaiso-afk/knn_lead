"""Migra os dados do SQLite local para um PostgreSQL VAZIO.

Execute na raiz do projeto depois de definir DATABASE_URL para a URL EXTERNA
fornecida pelo Render (não publique nem compartilhe essa URL).
"""
import os
import sqlite3
import sys

from config import DATABASE_PATH, DATABASE_URL
from database import init_db

TABLE_ORDER = (
    "usuarios",
    "campanhas",
    "locais",
    "qr_codes",
    "recompensas",
    "descobertas",
    "premios",
)
BUSINESS_TABLES = ("usuarios", "campanhas", "locais", "qr_codes", "descobertas", "premios")
DEFAULT_REWARDS = {
    ("Aula experimental", "Uma aula experimental na KNN.", 0, 1),
    ("Teste de nivelamento", "Teste de nivelamento de inglês.", 0, 1),
    ("Desconto especial", "Desconto especial oferecido pela KNN.", 0, 1),
    (
        "Experiência com parceiro",
        "Experiência especial com um parceiro da campanha.",
        0,
        1,
    ),
}


def fail(message):
    raise RuntimeError(message)


def table_exists(cursor, table_name):
    cursor.execute("SELECT to_regclass(%s) AS table_ref", (f"public.{table_name}",))
    return cursor.fetchone()["table_ref"] is not None


def ensure_destination_is_empty(pg_connection):
    cursor = pg_connection.cursor()
    for table in BUSINESS_TABLES:
        if table_exists(cursor, table):
            cursor.execute(f'SELECT COUNT(*) AS total FROM "{table}"')
            if cursor.fetchone()["total"]:
                fail(
                    f'O PostgreSQL já tem dados na tabela {table}. '
                    "A migração foi cancelada para evitar sobrescrever dados."
                )

    if table_exists(cursor, "recompensas"):
        cursor.execute('SELECT nome, descricao, quantidade, ativa FROM "recompensas"')
        reward_rows = cursor.fetchall()
        current_rewards = {
            (row["nome"], row["descricao"], row["quantidade"], row["ativa"])
            for row in reward_rows
        }
        # Só permite as quatro recompensas-padrão que init_db cria num banco vazio.
        if current_rewards and current_rewards != DEFAULT_REWARDS:
            fail(
                "A tabela recompensas já contém configurações personalizadas. "
                "A migração foi cancelada para evitar apagar esses dados."
            )
        if len(reward_rows) not in (0, len(DEFAULT_REWARDS)):
            fail(
                "A tabela recompensas contém registros que não parecem ser apenas "
                "os padrões iniciais; migração cancelada."
            )
    cursor.close()


def main():
    if not DATABASE_URL:
        fail(
            "DATABASE_URL não foi definida. Configure a URL EXTERNA do PostgreSQL "
            "no terminal antes de executar este script."
        )

    sqlite_path = os.path.abspath(DATABASE_PATH)
    if not os.path.isfile(sqlite_path):
        fail(f"Banco SQLite não encontrado: {sqlite_path}")

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        fail("Instale as dependências com: python -m pip install -r requirements.txt")

    print(f"Origem SQLite: {sqlite_path}")
    print("Destino PostgreSQL: URL definida (credenciais ocultas).")
    print("Atenção: o banco PostgreSQL de destino precisa estar vazio.")
    confirm = input("Digite MIGRAR para iniciar a cópia dos dados: ").strip()
    if confirm != "MIGRAR":
        print("Migração cancelada; nenhum dado foi copiado.")
        return

    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    pg_connection = None

    try:
        pg_connection = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

        # Confirma antes de criar tabelas/seed para não tocar num banco já utilizado.
        ensure_destination_is_empty(pg_connection)
        pg_connection.rollback()
        pg_connection.close()
        pg_connection = None

        # Cria/atualiza tabelas e dados iniciais do aplicativo no destino.
        init_db()
        pg_connection = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

        # Proteção repetida logo antes do TRUNCATE.
        ensure_destination_is_empty(pg_connection)
        pg_connection.rollback()

        source_tables = {
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing_tables = set(TABLE_ORDER) - source_tables
        if missing_tables:
            fail("Tabelas não encontradas no SQLite: " + ", ".join(sorted(missing_tables)))

        pg_cursor = pg_connection.cursor()
        pg_cursor.execute(
            "TRUNCATE TABLE premios, descobertas, qr_codes, campanhas, locais, usuarios, recompensas "
            "RESTART IDENTITY CASCADE"
        )

        for table in TABLE_ORDER:
            source_cursor = source.execute(f'SELECT * FROM "{table}"')
            source_columns = [col[0] for col in source_cursor.description]
            pg_cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s",
                (table,),
            )
            pg_columns = {row["column_name"] for row in pg_cursor.fetchall()}
            unexpected = set(source_columns) - pg_columns
            if unexpected:
                fail(
                    f"A tabela {table} tem colunas que não existem no PostgreSQL: "
                    + ", ".join(sorted(unexpected))
                )

            if not source_columns:
                continue
            col_sql = ", ".join(f'"{col}"' for col in source_columns)
            values_sql = ", ".join(["%s"] * len(source_columns))
            insert_sql = f'INSERT INTO "{table}" ({col_sql}) VALUES ({values_sql})'
            total = 0
            while True:
                batch = source_cursor.fetchmany(1000)
                if not batch:
                    break
                pg_cursor.executemany(insert_sql, [tuple(row) for row in batch])
                total += len(batch)
            print(f"{table}: {total} registros copiados")

        # Ajusta sequências de IDs após inserir explicitamente os IDs antigos.
        for table in TABLE_ORDER:
            pg_cursor.execute(
                f"SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                f"COALESCE((SELECT MAX(id) FROM \"{table}\"), 1), "
                f"EXISTS (SELECT 1 FROM \"{table}\")) AS sequence_value",
                (f"public.{table}",),
            )

        pg_connection.commit()
        print("Migração concluída. Confira os totais no sistema antes de colocar o site no ar.")
    except Exception:
        if pg_connection is not None:
            pg_connection.rollback()
        raise
    finally:
        source.close()
        if pg_connection is not None:
            pg_connection.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)
