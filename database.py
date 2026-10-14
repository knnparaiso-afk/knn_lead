import os
import re
import sqlite3

from config import DATABASE_PATH, DATABASE_URL


# O esquema fica escrito em sintaxe SQLite, para preservar o comportamento local.
# Quando DATABASE_URL está configurada, as diferenças de DDL são traduzidas para PostgreSQL.
SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    whatsapp TEXT NOT NULL,
    email TEXT,
    idade INTEGER,
    data_cadastro TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campanhas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    semana INTEGER NOT NULL,
    frase TEXT NOT NULL,
    traducao TEXT NOT NULL,
    opcao_a TEXT,
    opcao_b TEXT,
    opcao_c TEXT,
    resposta_correta TEXT DEFAULT 'A',
    data_inicio TEXT,
    data_fim TEXT,
    ativa INTEGER NOT NULL DEFAULT 0,
    data_criacao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS locais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    endereco TEXT,
    parceiro TEXT,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS qr_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    campanha_id INTEGER NOT NULL,
    local_id INTEGER NOT NULL,
    data_criacao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campanha_id) REFERENCES campanhas(id) ON DELETE CASCADE,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS descobertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    campanha_id INTEGER NOT NULL,
    local_id INTEGER NOT NULL,
    qr_code_id INTEGER NOT NULL,
    data_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (campanha_id) REFERENCES campanhas(id) ON DELETE CASCADE,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE,
    FOREIGN KEY (qr_code_id) REFERENCES qr_codes(id) ON DELETE CASCADE,
    UNIQUE(usuario_id, campanha_id)
);

CREATE TABLE IF NOT EXISTS recompensas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    descricao TEXT,
    quantidade INTEGER NOT NULL DEFAULT 0,
    ativa INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS premios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    recompensa_id INTEGER NOT NULL,
    data_desbloqueio TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_utilizacao TEXT,
    status TEXT NOT NULL DEFAULT 'disponivel',
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (recompensa_id) REFERENCES recompensas(id) ON DELETE CASCADE,
    UNIQUE(usuario_id)
);

-- Registra a versão do aviso e cada autorização declarada no cadastro.
CREATE TABLE IF NOT EXISTS registros_consentimento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    versao TEXT NOT NULL,
    texto TEXT NOT NULL,
    data_consentimento TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Contadores compartilhados entre workers e reinícios da aplicação.
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    bucket_key TEXT PRIMARY KEY,
    window_start BIGINT NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_rate_limit_buckets_window_start
    ON rate_limit_buckets(window_start);
"""


def _replace_question_marks(sql):
    """Troca placeholders ? por %s sem alterar strings/comentários SQL."""
    result = []
    i = 0
    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False

    while i < len(sql):
        char = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""

        if in_line_comment:
            result.append(char)
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            result.append(char)
            if char == "*" and nxt == "/":
                result.append(nxt)
                i += 2
                in_block_comment = False
            else:
                i += 1
            continue

        if not in_single and not in_double and char == "-" and nxt == "-":
            result.extend([char, nxt])
            i += 2
            in_line_comment = True
            continue

        if not in_single and not in_double and char == "/" and nxt == "*":
            result.extend([char, nxt])
            i += 2
            in_block_comment = True
            continue

        if char == "'" and not in_double:
            result.append(char)
            if in_single and nxt == "'":
                result.append(nxt)
                i += 2
                continue
            in_single = not in_single
            i += 1
            continue

        if char == '"' and not in_single:
            result.append(char)
            if in_double and nxt == '"':
                result.append(nxt)
                i += 2
                continue
            in_double = not in_double
            i += 1
            continue

        if char == "?" and not in_single and not in_double:
            result.append("%s")
        else:
            result.append(char)
        i += 1

    return "".join(result)


def _translate_postgres_sql(sql):
    sql = _replace_question_marks(sql)
    # No esquema do projeto, datas/horas são armazenadas como TEXT para manter
    # o mesmo formato e comportamento que a aplicação usa com SQLite.
    sql = re.sub(
        r"\bCURRENT_TIMESTAMP\b(?!\s*::text)",
        "CURRENT_TIMESTAMP::text",
        sql,
        flags=re.IGNORECASE,
    )
    return sql


class PostgreSQLConnection:
    """Adaptador mínimo para que o app use execute/commit/close como no sqlite3."""

    def __init__(self, raw_connection):
        self._raw_connection = raw_connection

    def execute(self, sql, parameters=None):
        cursor = self._raw_connection.cursor()
        translated = _translate_postgres_sql(sql)
        if parameters is None:
            cursor.execute(translated)
        else:
            cursor.execute(translated, parameters)
        return cursor

    def executemany(self, sql, seq_of_parameters):
        cursor = self._raw_connection.cursor()
        cursor.executemany(_translate_postgres_sql(sql), seq_of_parameters)
        return cursor

    def executescript(self, script):
        # O DDL deste projeto não contém funções/procedures com blocos internos;
        # portanto cada comando pode ser executado separadamente.
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)

    def commit(self):
        self._raw_connection.commit()

    def rollback(self):
        self._raw_connection.rollback()

    def close(self):
        self._raw_connection.close()


def get_connection():
    if DATABASE_URL:
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError as exc:
            raise RuntimeError(
                "DATABASE_URL está definida, mas psycopg2-binary não está instalado. "
                "Execute: pip install -r requirements.txt"
            ) from exc

        raw_connection = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
        )
        return PostgreSQLConnection(raw_connection)

    os.makedirs(os.path.dirname(os.path.abspath(DATABASE_PATH)), exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _migrate_sqlite_schema(connection):
    colunas_usuario = {
        coluna["name"]
        for coluna in connection.execute("PRAGMA table_info(usuarios)").fetchall()
    }
    if "idade" not in colunas_usuario:
        connection.execute("ALTER TABLE usuarios ADD COLUMN idade INTEGER")

    colunas_campanhas = {
        coluna["name"]
        for coluna in connection.execute("PRAGMA table_info(campanhas)").fetchall()
    }
    if "opcao_a" not in colunas_campanhas:
        connection.execute("ALTER TABLE campanhas ADD COLUMN opcao_a TEXT")
    if "opcao_b" not in colunas_campanhas:
        connection.execute("ALTER TABLE campanhas ADD COLUMN opcao_b TEXT")
    if "opcao_c" not in colunas_campanhas:
        connection.execute("ALTER TABLE campanhas ADD COLUMN opcao_c TEXT")
    if "resposta_correta" not in colunas_campanhas:
        connection.execute(
            "ALTER TABLE campanhas ADD COLUMN resposta_correta TEXT DEFAULT 'A'"
        )
    if "categoria" not in colunas_campanhas:
        connection.execute(
            "ALTER TABLE campanhas ADD COLUMN categoria TEXT DEFAULT 'frases'"
        )


def _migrate_postgres_schema(connection):
    # IF NOT EXISTS permite atualizar bancos criados por versões anteriores.
    connection.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS idade INTEGER")
    connection.execute("ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS opcao_a TEXT")
    connection.execute("ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS opcao_b TEXT")
    connection.execute("ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS opcao_c TEXT")
    connection.execute(
        "ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS resposta_correta TEXT DEFAULT 'A'"
    )
    connection.execute(
        "ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS categoria TEXT DEFAULT 'frases'"
    )


def init_db():
    connection = get_connection()
    try:
        if DATABASE_URL:
            schema_pg = SCHEMA_SQLITE.replace(
                "INTEGER PRIMARY KEY AUTOINCREMENT",
                "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
            )
            connection.executescript(schema_pg)
            _migrate_postgres_schema(connection)
        else:
            connection.executescript(SCHEMA_SQLITE)
            _migrate_sqlite_schema(connection)

        # Corrige registros antigos de campanhas que ainda não tinham opções separadas.
        campanhas_existentes = connection.execute(
            "SELECT id, traducao, opcao_a FROM campanhas"
        ).fetchall()
        for camp in campanhas_existentes:
            if not camp["opcao_a"]:
                primeira_opcao = (
                    camp["traducao"].split("|")[0].strip()
                    if camp["traducao"]
                    else "Vejo você lá"
                )
                connection.execute(
                    """
                    UPDATE campanhas
                    SET opcao_a = ?,
                        opcao_b = 'Onde você está?',
                        opcao_c = 'Bom te ver ontem',
                        resposta_correta = 'A'
                    WHERE id = ?
                    """,
                    (primeira_opcao, camp["id"]),
                )

        quantidade = connection.execute(
            "SELECT COUNT(*) AS total FROM recompensas"
        ).fetchone()["total"]

        if quantidade == 0:
            connection.executemany(
                """
                INSERT INTO recompensas (nome, descricao, quantidade)
                VALUES (?, ?, ?)
                """,
                [
                    ("Aula experimental", "Uma aula experimental na KNN.", 0),
                    ("Teste de nivelamento", "Teste de nivelamento de inglês.", 0),
                    ("Desconto especial", "Desconto especial oferecido pela KNN.", 0),
                    (
                        "Experiência com parceiro",
                        "Experiência especial com um parceiro da campanha.",
                        0,
                    ),
                ],
            )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
