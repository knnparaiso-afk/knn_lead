from config import ENGLISH_PASS_REQUIRED
from database import get_connection

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

    digitos = "".join(c for c in whatsapp if c.isdigit())
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


def salvar_participacao(connection, qr, nome, whatsapp, email, idade):
    """Cria/atualiza o usuário, registra a descoberta e os consentimentos.

    Não faz commit: quem chama controla a transação.
    """
    usuario = connection.execute(
        "SELECT id FROM usuarios WHERE whatsapp = ?", (whatsapp,)
    ).fetchone()

    if usuario:
        usuario_id = usuario["id"]
        connection.execute(
            "UPDATE usuarios SET nome = ?, email = ?, idade = ? WHERE id = ?",
            (nome, email, idade, usuario_id),
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

    ja_encontrou = connection.execute(
        "SELECT id FROM descobertas WHERE usuario_id = ? AND campanha_id = ?",
        (usuario_id, qr["campanha_id"]),
    ).fetchone()

    if not ja_encontrou:
        connection.execute(
            """
            INSERT INTO descobertas (usuario_id, campanha_id, local_id, qr_code_id)
            VALUES (?, ?, ?, ?)
            """,
            (usuario_id, qr["campanha_id"], qr["local_id"], qr["id"]),
        )

    registrar_consentimento(
        connection, usuario_id, "participacao_e_mensagens", PARTICIPATION_CONSENT_TEXT
    )
    if idade < 18:
        registrar_consentimento(
            connection, usuario_id, "responsavel_legal", GUARDIAN_CONSENT_TEXT
        )
    return usuario_id


def quantidade_descobertas(usuario_id):
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT COUNT(*) AS total FROM descobertas WHERE usuario_id = ?",
            (usuario_id,),
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
        existe = connection.execute(
            "SELECT id FROM premios WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
        if not existe:
            recompensa = connection.execute(
                "SELECT id FROM recompensas WHERE ativa = 1 ORDER BY id LIMIT 1"
            ).fetchone()
            if recompensa:
                connection.execute(
                    "INSERT INTO premios (usuario_id, recompensa_id) VALUES (?, ?)",
                    (usuario_id, recompensa["id"]),
                )
        connection.commit()
    finally:
        connection.close()
