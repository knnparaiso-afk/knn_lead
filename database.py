import sqlite3
import os
from config import DATABASE_PATH


def get_connection():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_db():
    connection = get_connection()

    connection.executescript("""
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

            FOREIGN KEY (campanha_id)
                REFERENCES campanhas(id)
                ON DELETE CASCADE,

            FOREIGN KEY (local_id)
                REFERENCES locais(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS descobertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            campanha_id INTEGER NOT NULL,
            local_id INTEGER NOT NULL,
            qr_code_id INTEGER NOT NULL,
            data_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (usuario_id)
                REFERENCES usuarios(id)
                ON DELETE CASCADE,

            FOREIGN KEY (campanha_id)
                REFERENCES campanhas(id)
                ON DELETE CASCADE,

            FOREIGN KEY (local_id)
                REFERENCES locais(id)
                ON DELETE CASCADE,

            FOREIGN KEY (qr_code_id)
                REFERENCES qr_codes(id)
                ON DELETE CASCADE,

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

            FOREIGN KEY (usuario_id)
                REFERENCES usuarios(id)
                ON DELETE CASCADE,

            FOREIGN KEY (recompensa_id)
                REFERENCES recompensas(id)
                ON DELETE CASCADE,

            UNIQUE(usuario_id)
        );
    """)

    # Mantém instalações já existentes compatíveis com a nova captação.
    colunas_usuario = [
        coluna["name"]
        for coluna in connection.execute("PRAGMA table_info(usuarios)").fetchall()
    ]
    if "idade" not in colunas_usuario:
        connection.execute("ALTER TABLE usuarios ADD COLUMN idade INTEGER")

    colunas_campanhas = [
        coluna["name"]
        for coluna in connection.execute("PRAGMA table_info(campanhas)").fetchall()
    ]
    if "opcao_a" not in colunas_campanhas:
        connection.execute("ALTER TABLE campanhas ADD COLUMN opcao_a TEXT")
    if "opcao_b" not in colunas_campanhas:
        connection.execute("ALTER TABLE campanhas ADD COLUMN opcao_b TEXT")
    if "opcao_c" not in colunas_campanhas:
        connection.execute("ALTER TABLE campanhas ADD COLUMN opcao_c TEXT")
    if "resposta_correta" not in colunas_campanhas:
        connection.execute("ALTER TABLE campanhas ADD COLUMN resposta_correta TEXT DEFAULT 'A'")

    if "categoria" not in colunas_campanhas:
        connection.execute("ALTER TABLE campanhas ADD COLUMN categoria TEXT DEFAULT 'frases'")

    # Se a campanha existente tiver traducao com | (ex: "Vejo você lá | Vejo voce la"), limpar para a opcao_a
    campanhas_existentes = connection.execute("SELECT id, traducao, opcao_a FROM campanhas").fetchall()
    for camp in campanhas_existentes:
        if not camp["opcao_a"]:
            primeira_opcao = camp["traducao"].split("|")[0].strip() if camp["traducao"] else "Vejo você lá"
            connection.execute("""
                UPDATE campanhas
                SET opcao_a = ?,
                    opcao_b = 'Onde você está?',
                    opcao_c = 'Bom te ver ontem',
                    resposta_correta = 'A'
                WHERE id = ?
            """, (primeira_opcao, camp["id"]))

    # Recompensas iniciais
    quantidade = connection.execute(
        "SELECT COUNT(*) AS total FROM recompensas"
    ).fetchone()["total"]

    if quantidade == 0:
        connection.executemany(
            """
            INSERT INTO recompensas
            (nome, descricao, quantidade)
            VALUES (?, ?, ?)
            """,
            [
                (
                    "Aula experimental",
                    "Uma aula experimental na KNN.",
                    0
                ),
                (
                    "Teste de nivelamento",
                    "Teste de nivelamento de inglês.",
                    0
                ),
                (
                    "Desconto especial",
                    "Desconto especial oferecido pela KNN.",
                    0
                ),
                (
                    "Experiência com parceiro",
                    "Experiência especial com um parceiro da campanha.",
                    0
                )
            ]
        )

    connection.commit()
    connection.close()
