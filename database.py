import os
import re
import sqlite3
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

from config import DATABASE_PATH, DATABASE_URL, QR_LOCAL_GENERICO
from telefones import normalizar_whatsapp


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
    categoria TEXT DEFAULT 'frases',
    chamada TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL DEFAULT '',
    comunidade_url TEXT NOT NULL DEFAULT '',
    comunidade_nacional_url TEXT NOT NULL DEFAULT '',
    ativa INTEGER NOT NULL DEFAULT 0,
    exibir_faixa INTEGER NOT NULL DEFAULT 0,
    arquivada INTEGER NOT NULL DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS qrs_avulsos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    parceiro TEXT NOT NULL,
    origem TEXT NOT NULL DEFAULT 'qr',
    data_criacao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ativo INTEGER NOT NULL DEFAULT 1,
    campanha_id INTEGER REFERENCES campanhas(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS cadastros_qr_avulso (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    qr_avulso_id INTEGER NOT NULL,
    data_cadastro TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (qr_avulso_id) REFERENCES qrs_avulsos(id) ON DELETE CASCADE,
    UNIQUE(usuario_id, qr_avulso_id)
);
CREATE INDEX IF NOT EXISTS idx_cadastros_qr_avulso_data
    ON cadastros_qr_avulso(data_cadastro);

-- Log exclusivo dos QR Codes avulsos, sem dados pessoais ou vínculo com campanhas.
CREATE TABLE IF NOT EXISTS eventos_qr_avulso (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qr_avulso_id INTEGER NOT NULL,
    evento TEXT NOT NULL,
    data_evento TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qr_avulso_id) REFERENCES qrs_avulsos(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_eventos_qr_avulso_qr_evento
    ON eventos_qr_avulso(qr_avulso_id, evento);
CREATE INDEX IF NOT EXISTS idx_eventos_qr_avulso_qr_id
    ON eventos_qr_avulso(qr_avulso_id, id);

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
    UNIQUE(usuario_id, qr_code_id)
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

CREATE TABLE IF NOT EXISTS app_migrations (
    migration_key TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Métricas agregadas do funil. Não armazena dados pessoais nem identificadores do visitante.
CREATE TABLE IF NOT EXISTS metricas_funil (
    data TEXT NOT NULL,
    evento TEXT NOT NULL,
    qr_code_id INTEGER NOT NULL DEFAULT 0,
    campanha_id INTEGER NOT NULL DEFAULT 0,
    categoria TEXT NOT NULL DEFAULT '',
    origem TEXT NOT NULL DEFAULT 'qr',
    total INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (data, evento, qr_code_id, campanha_id, categoria, origem)
);
CREATE INDEX IF NOT EXISTS idx_metricas_funil_data_evento
    ON metricas_funil(data, evento);

CREATE TABLE IF NOT EXISTS resgates_roleta (
    whatsapp TEXT NOT NULL PRIMARY KEY,
    navegador_id TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL,
    premio TEXT NOT NULL,
    registrado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
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
    connection.create_function("normalizar_whatsapp", 1, normalizar_whatsapp, deterministic=True)
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

    # Migração da restrição UNIQUE de descobertas: de (usuario_id, campanha_id) para (usuario_id, qr_code_id)
    # Se a tabela no SQLite ainda tiver a restrição antiga na definição DDL, recriamos sem perder dados.
    schema_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='descobertas'"
    ).fetchone()
    if schema_sql and "UNIQUE(usuario_id, campanha_id)" in schema_sql["sql"]:
        connection.executescript(
            """
            PRAGMA foreign_keys = OFF;
            CREATE TABLE IF NOT EXISTS descobertas_nova (
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
                UNIQUE(usuario_id, qr_code_id)
            );
            INSERT OR IGNORE INTO descobertas_nova (id, usuario_id, campanha_id, local_id, qr_code_id, data_hora)
                SELECT id, usuario_id, campanha_id, local_id, qr_code_id, data_hora FROM descobertas;
            DROP TABLE descobertas;
            ALTER TABLE descobertas_nova RENAME TO descobertas;
            PRAGMA foreign_keys = ON;
            """
        )


def _migrate_postgres_schema(connection):
    # IF NOT EXISTS permite atualizar bancos criados por versões anteriores.
    for col_ddl in [
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS idade INTEGER",
        "ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS opcao_a TEXT",
        "ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS opcao_b TEXT",
        "ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS opcao_c TEXT",
        "ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS resposta_correta TEXT DEFAULT 'A'",
        "ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS categoria TEXT DEFAULT 'frases'",
    ]:
        try:
            connection.execute(col_ddl)
            connection.commit()
        except Exception:
            connection.rollback()

    # No PostgreSQL, remove a constraint antiga se existir
    try:
        connection.execute(
            "ALTER TABLE descobertas DROP CONSTRAINT IF EXISTS descobertas_usuario_id_campanha_id_key"
        )
        connection.commit()
    except Exception:
        connection.rollback()

    # Verifica se a nova constraint já existe no PostgreSQL antes de tentar criá-la
    try:
        row = connection.execute(
            "SELECT 1 FROM pg_constraint WHERE conname = 'descobertas_usuario_id_qr_code_id_key'"
        ).fetchone()
        connection.commit()
        if not row:
            connection.execute(
                "ALTER TABLE descobertas ADD CONSTRAINT descobertas_usuario_id_qr_code_id_key UNIQUE (usuario_id, qr_code_id)"
            )
            connection.commit()
    except Exception:
        connection.rollback()


def _migrate_qr_location_tracking(connection):
    """Reassocia os QR Codes existentes a um ponto genérico sem alterar os códigos."""
    migration_key = "qr_location_tracking_disabled_v1"
    if DATABASE_URL:
        connection.execute("SELECT pg_advisory_xact_lock(?)", (7193042106,))
    else:
        connection.execute("BEGIN IMMEDIATE")

    aplicada = connection.execute(
        "SELECT migration_key FROM app_migrations WHERE migration_key = ?",
        (migration_key,),
    ).fetchone()
    if aplicada:
        connection.commit()
        return

    local = connection.execute(
        "SELECT id FROM locais WHERE nome = ? ORDER BY id LIMIT 1",
        (QR_LOCAL_GENERICO,),
    ).fetchone()
    if local:
        local_id = local["id"]
        connection.execute(
            "UPDATE locais SET endereco = NULL, parceiro = NULL, ativo = 1 WHERE id = ?",
            (local_id,),
        )
    else:
        connection.execute(
            "INSERT INTO locais (nome, endereco, parceiro, ativo) VALUES (?, NULL, NULL, 1)",
            (QR_LOCAL_GENERICO,),
        )
        local_id = connection.execute(
            "SELECT id FROM locais WHERE nome = ? ORDER BY id LIMIT 1",
            (QR_LOCAL_GENERICO,),
        ).fetchone()["id"]

    # Preserve cada código e sua campanha (por exemplo, jogos e frases), alterando
    # somente a referência ao estabelecimento. As descobertas ficam no mesmo ponto.
    connection.execute("UPDATE qr_codes SET local_id = ?", (local_id,))
    connection.execute("UPDATE descobertas SET local_id = ?", (local_id,))
    connection.execute(
        "UPDATE locais SET ativo = 0 WHERE id <> ?",
        (local_id,),
    )
    connection.execute(
        "INSERT INTO app_migrations (migration_key) VALUES (?)",
        (migration_key,),
    )
    connection.commit()


def _migrate_black_campaigns(connection):
    """Acrescenta a campanha de cadastro direto preservando códigos e histórico."""
    campos = ("chamada", "descricao", "comunidade_url", "comunidade_nacional_url")
    if DATABASE_URL:
        for campo in campos:
            connection.execute(f"ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS {campo} TEXT NOT NULL DEFAULT ''")
        connection.execute(
            "ALTER TABLE qrs_avulsos ADD COLUMN IF NOT EXISTS campanha_id "
            "INTEGER REFERENCES campanhas(id) ON DELETE SET NULL"
        )
    else:
        existentes = {row["name"] for row in connection.execute("PRAGMA table_info(campanhas)").fetchall()}
        for campo in campos:
            if campo not in existentes:
                connection.execute(f"ALTER TABLE campanhas ADD COLUMN {campo} TEXT NOT NULL DEFAULT ''")
        if "campanha_id" not in {row["name"] for row in connection.execute("PRAGMA table_info(qrs_avulsos)").fetchall()}:
            connection.execute("ALTER TABLE qrs_avulsos ADD COLUMN campanha_id INTEGER REFERENCES campanhas(id) ON DELETE SET NULL")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_qrs_avulsos_campanha ON qrs_avulsos(campanha_id)")
    connection.commit()


def _codigo_migracao(connection):
    while True:
        codigo = secrets.token_hex(6).upper()
        if not any(connection.execute(f"SELECT id FROM {tabela} WHERE codigo = ?", (codigo,)).fetchone()
                   for tabela in ("campanhas", "qr_codes", "qrs_avulsos")):
            return codigo


def _migrate_direct_campaigns(connection):
    """Adota os QR Black já impressos uma única vez, preservando IDs e histórico."""
    campos = {
        "campanhas": {"exibir_faixa": "INTEGER NOT NULL DEFAULT 0", "arquivada": "INTEGER NOT NULL DEFAULT 0"},
        "qrs_avulsos": {"origem": "TEXT NOT NULL DEFAULT 'qr'"},
    }
    for tabela, definicoes in campos.items():
        existentes = set() if DATABASE_URL else {
            row["name"] for row in connection.execute(f"PRAGMA table_info({tabela})").fetchall()
        }
        for campo, ddl in definicoes.items():
            if DATABASE_URL or campo not in existentes:
                condicao = "IF NOT EXISTS " if DATABASE_URL else ""
                connection.execute(f"ALTER TABLE {tabela} ADD COLUMN {condicao}{campo} {ddl}")
    connection.commit()

    if DATABASE_URL:
        connection.execute("SELECT pg_advisory_xact_lock(?)", (7193042108,))
    else:
        connection.execute("BEGIN IMMEDIATE")
    chave = "direct_campaigns_adopt_black_qrs_v1"
    if connection.execute("SELECT migration_key FROM app_migrations WHERE migration_key = ?", (chave,)).fetchone():
        connection.commit()
        return

    # A categoria antiga era uma mecânica de cadastro direto, não um tipo sazonal.
    connection.execute("UPDATE campanhas SET categoria = 'cadastro_direto' WHERE categoria = 'black_november'")
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    vigentes = connection.execute(
        "SELECT id FROM campanhas WHERE categoria = 'cadastro_direto' AND ativa = 1 AND arquivada = 0 "
        "AND (data_inicio IS NULL OR data_inicio = '' OR data_inicio <= ?) "
        "AND (data_fim IS NULL OR data_fim = '' OR data_fim >= ?) ORDER BY id DESC", (hoje, hoje),
    ).fetchall()
    avulsos = connection.execute("SELECT id FROM qrs_avulsos WHERE campanha_id IS NULL").fetchall()
    if avulsos:
        # Reutiliza uma Black vigente inequívoca. Em outro caso, a campanha de
        # adoção nasce ativa e sem prazo para não bloquear QR que já funcionava.
        if len(vigentes) == 1:
            campanha_id = vigentes[0]["id"]
        else:
            semana = connection.execute("SELECT COALESCE(MAX(semana), 0) + 1 AS proxima FROM campanhas").fetchone()["proxima"]
            campanha_id = connection.execute(
                "INSERT INTO campanhas (codigo, nome, semana, frase, traducao, categoria, ativa) "
                "VALUES (?, 'Black November', ?, '', '', 'cadastro_direto', 1) RETURNING id",
                (_codigo_migracao(connection), semana),
            ).fetchone()["id"]
        connection.execute("UPDATE qrs_avulsos SET campanha_id = ? WHERE campanha_id IS NULL", (campanha_id,))

    # Landing tem uma origem própria; nunca reutiliza o primeiro QR das ruas.
    for campanha in connection.execute("SELECT id, nome FROM campanhas WHERE categoria = 'cadastro_direto'").fetchall():
        if not connection.execute("SELECT id FROM qrs_avulsos WHERE campanha_id = ? AND origem = 'landing'", (campanha["id"],)).fetchone():
            connection.execute(
                "INSERT INTO qrs_avulsos (codigo, parceiro, campanha_id, origem) VALUES (?, ?, ?, 'landing')",
                (_codigo_migracao(connection), campanha["nome"], campanha["id"]),
            )
    destaque = connection.execute(
        "SELECT id FROM campanhas WHERE ativa = 1 AND arquivada = 0 "
        "AND (data_inicio IS NULL OR data_inicio = '' OR data_inicio <= ?) "
        "AND (data_fim IS NULL OR data_fim = '' OR data_fim >= ?) "
        "ORDER BY CASE WHEN categoria = 'cadastro_direto' THEN 0 ELSE 1 END, id DESC LIMIT 1", (hoje, hoje),
    ).fetchone()
    if destaque:
        connection.execute("UPDATE campanhas SET exibir_faixa = 1 WHERE id = ?", (destaque["id"],))
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_qrs_landing_campanha ON qrs_avulsos(campanha_id) "
        "WHERE origem = 'landing' AND campanha_id IS NOT NULL"
    )
    connection.execute("INSERT INTO app_migrations (migration_key) VALUES (?)", (chave,))
    connection.commit()


def init_db():
    connection = get_connection()
    try:
        if DATABASE_URL:
            schema_pg = SCHEMA_SQLITE.replace(
                "INTEGER PRIMARY KEY AUTOINCREMENT",
                "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
            )
            connection.executescript(schema_pg)
            connection.commit()
            _migrate_postgres_schema(connection)
            connection.commit()
        else:
            connection.executescript(SCHEMA_SQLITE)
            _migrate_sqlite_schema(connection)
            connection.commit()

        _migrate_black_campaigns(connection)
        _migrate_direct_campaigns(connection)
        _migrate_qr_location_tracking(connection)

        # Corrige registros antigos de campanhas que ainda não tinham opções separadas.
        campanhas_existentes = connection.execute(
            "SELECT id, traducao, opcao_a FROM campanhas WHERE categoria IN ('frases', 'jogos')"
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
