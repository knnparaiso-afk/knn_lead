from itsdangerous import URLSafeTimedSerializer
from config import ENGLISH_PASS_REQUIRED, SECRET_KEY
from database import get_connection, PostgreSQLConnection
from telefones import normalizar_whatsapp

_signer = URLSafeTimedSerializer(SECRET_KEY, salt="knn-participante-salt")


def gerar_token_participante(usuario_id):
    """Gera token assinado e seguro com o ID do participante para persistir no cookie."""
    return _signer.dumps({"uid": usuario_id})


def obter_id_por_token(token):
    """Extrai e valida o usuario_id do token assinado. Retorna None se inválido."""
    if not token:
        return None
    try:
        dados = _signer.loads(token, max_age=86400 * 365)  # 1 ano
        return dados.get("uid")
    except Exception:
        return None


PRIVACY_NOTICE_VERSION = "2026-10-13-v1"
CONSENT_TEXT_VERSION = "2026-10-13-v3"

PARTICIPATION_CONSENT_TEXT = (
    "Concordo em participar da campanha e autorizo a unidade KNN responsável "
    "a entrar em contato comigo por WhatsApp ou e-mail, inclusive para enviar mensagens "
    "sobre a campanha, novidades, promoções e oportunidades relacionadas aos cursos da unidade. "
    "Se a pessoa participante tiver menos de 18 anos, declaro ser pai, mãe ou responsável legal "
    "e autorizo sua participação e esses contatos."
)
GUARDIAN_CONSENT_TEXT = (
    "Declaro ser pai, mãe ou responsável legal pela pessoa menor de 18 anos e "
    "autorizo sua participação na campanha e o contato por WhatsApp ou e-mail, "
    "incluindo mensagens relacionadas, novidades, promoções e oportunidades da unidade."
)


def validar_formulario(nome, whatsapp, email, idade):
    """Retorna (idade_int, None) se válido, ou (None, mensagem_de_erro)."""
    try:
        idade = int(idade)
        if not 3 <= idade <= 120:
            raise ValueError
    except ValueError:
        return None, "Informe uma idade válida."

    if len(nome) > 120 or len(whatsapp) > 32 or len(email) > 254:
        return None, "Revise os campos: um dos valores excede o limite permitido."

    digitos = normalizar_whatsapp(whatsapp)
    if len(digitos) not in (10, 11):
        return None, "Informe um WhatsApp válido com DDD."

    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return None, "Informe um e-mail válido."

    return idade, None


def registrar_consentimento(connection, usuario_id, tipo, texto, versao=None):
    connection.execute(
        """
        INSERT INTO registros_consentimento (usuario_id, tipo, versao, texto)
        VALUES (?, ?, ?, ?)
        """,
        (usuario_id, tipo, versao or CONSENT_TEXT_VERSION, texto),
    )


def _bloquear_gravacao(connection):
    # Serializa identificação + descoberta, inclusive entre workers do servidor.
    # O bloqueio termina no commit/rollback da transação de quem chama.
    if isinstance(connection, PostgreSQLConnection):
        connection.execute("SELECT pg_advisory_xact_lock(?)", (7193042107,))
    elif not connection.in_transaction:
        connection.execute("BEGIN IMMEDIATE")


def _ids_por_whatsapp(connection, whatsapp):
    # Reconhece também máscaras antigas, sem apagar cadastros, consentimentos
    # ou cookies existentes. Novas participações usam o cadastro mais antigo.
    expressao = (
        "regexp_replace(whatsapp, '[^0-9]', '', 'g')"
        if isinstance(connection, PostgreSQLConnection)
        else "normalizar_whatsapp(whatsapp)"
    )
    return [row["id"] for row in connection.execute(
        f"SELECT id FROM usuarios WHERE {expressao} = ? ORDER BY id",
        (normalizar_whatsapp(whatsapp),),
    ).fetchall()]


def _ids_do_participante(connection, usuario_id):
    usuario = connection.execute(
        "SELECT whatsapp FROM usuarios WHERE id = ?", (usuario_id,)
    ).fetchone()
    return _ids_por_whatsapp(connection, usuario["whatsapp"]) if usuario else [usuario_id]


def descoberta_ja_registrada(connection, usuario_id, qr_id):
    ids = _ids_do_participante(connection, usuario_id)
    placeholders = ",".join("?" for _ in ids)
    return connection.execute(
        f"SELECT id FROM descobertas WHERE usuario_id IN ({placeholders}) "
        "AND qr_code_id = ? LIMIT 1", (*ids, qr_id),
    ).fetchone() is not None


def salvar_participacao(connection, qr, nome, whatsapp, email, idade):
    """Cria/atualiza o usuário, registra a descoberta e os consentimentos.

    Não faz commit: quem chama controla a transação.
    """
    whatsapp = normalizar_whatsapp(whatsapp)
    if len(whatsapp) not in (10, 11):
        raise ValueError("Informe um WhatsApp válido com DDD.")
    _bloquear_gravacao(connection)
    ids = _ids_por_whatsapp(connection, whatsapp)

    if ids:
        usuario_id = ids[0]
        connection.execute(
            "UPDATE usuarios SET nome = ?, email = ?, idade = ?, whatsapp = ? WHERE id = ?",
            (nome, email, idade, whatsapp, usuario_id),
        )
    else:
        cursor = connection.execute(
            """
            INSERT INTO usuarios (nome, whatsapp, email, idade)
            VALUES (?, ?, ?, ?)
            RETURNING id
            """,
            (nome, whatsapp, email, idade),
        )
        usuario_id = cursor.fetchone()["id"]

    ja_encontrou = descoberta_ja_registrada(connection, usuario_id, qr["id"])

    novo_registro = False
    if not ja_encontrou:
        inserida = connection.execute(
            """
            INSERT INTO descobertas (usuario_id, campanha_id, local_id, qr_code_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (usuario_id, qr_code_id) DO NOTHING
            RETURNING id
            """,
            (usuario_id, qr["campanha_id"], qr["local_id"], qr["id"]),
        ).fetchone()
        novo_registro = inserida is not None

    registrar_consentimento(
        connection, usuario_id, "participacao_e_mensagens", PARTICIPATION_CONSENT_TEXT
    )
    if idade < 18:
        registrar_consentimento(
            connection, usuario_id, "responsavel_legal", GUARDIAN_CONSENT_TEXT
        )
    return usuario_id, novo_registro


def quantidade_descobertas(usuario_id):
    connection = get_connection()
    try:
        ids = _ids_do_participante(connection, usuario_id)
        placeholders = ",".join("?" for _ in ids)
        return connection.execute(
            "SELECT COUNT(DISTINCT qr_code_id) AS total FROM descobertas "
            f"WHERE usuario_id IN ({placeholders})", ids,
        ).fetchone()["total"]
    finally:
        connection.close()


def usuario_tem_pass(usuario_id):
    return quantidade_descobertas(usuario_id) >= ENGLISH_PASS_REQUIRED


def criar_pass_se_necessario(usuario_id):
    if not usuario_tem_pass(usuario_id):
        return

    connection = get_connection()
    try:
        _bloquear_gravacao(connection)
        ids = _ids_do_participante(connection, usuario_id)
        placeholders = ",".join("?" for _ in ids)
        existe = connection.execute(
            f"SELECT id FROM premios WHERE usuario_id IN ({placeholders})", ids,
        ).fetchone()
        if not existe:
            recompensa = connection.execute(
                "SELECT id FROM recompensas WHERE ativa = 1 ORDER BY id LIMIT 1"
            ).fetchone()
            if recompensa:
                connection.execute(
                    "INSERT INTO premios (usuario_id, recompensa_id) VALUES (?, ?) "
                    "ON CONFLICT (usuario_id) DO NOTHING",
                    (ids[0], recompensa["id"]),
                )
        connection.commit()
    finally:
        connection.close()
