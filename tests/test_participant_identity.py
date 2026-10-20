import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

import database
from inglessecreto import create_app
from inglessecreto.services.participants import (
    criar_pass_se_necessario,
    descoberta_ja_registrada,
    gerar_token_participante,
    quantidade_descobertas,
    salvar_participacao,
)
import test_qr_location_migration as migration_tests


class ParticipantIdentityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = migration_tests.QRLocationMigrationTests()
        self.fixture.setUp()
        self.connection = self.fixture.connection

    def tearDown(self):
        self.fixture.tearDown()

    def qr(self, qr_id):
        return self.connection.execute(
            "SELECT * FROM qr_codes WHERE id = ?", (qr_id,)
        ).fetchone()

    def save(self, qr, phone, connection=None):
        return salvar_participacao(
            connection or self.connection, qr, "Pessoa de teste", phone,
            "teste@example.com", 30,
        )

    def test_legacy_mask_and_new_formats_reuse_identity_and_discovery(self):
        self.connection.execute(
            "UPDATE usuarios SET whatsapp = ? WHERE id = ?",
            ("(35) 99999-0000", self.fixture.user_id),
        )
        self.connection.commit()
        qr = self.qr(self.fixture.game_qr_ids[0])
        for phone in ("35999990000", "(35) 99999-0000", "35 99999 0000", "35.99999.0000"):
            with self.subTest(phone=phone):
                user_id, new = self.save(qr, phone)
                self.connection.commit()
                self.assertEqual(user_id, self.fixture.user_id)
                self.assertFalse(new)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0], 1)
        self.assertEqual(quantidade_descobertas(self.fixture.user_id), 1)
        self.assertEqual(self.connection.execute("SELECT whatsapp FROM usuarios").fetchone()[0], "35999990000")

    def add_legacy_duplicate(self):
        cursor = self.connection.execute(
            "INSERT INTO usuarios (nome, whatsapp, email, idade) VALUES (?, ?, ?, ?)",
            ("Pessoa de teste", "(35) 99999-0000", "teste@example.com", 30),
        )
        duplicate_id = cursor.lastrowid
        for qr_id in (self.fixture.game_qr_ids[0], self.fixture.phrase_qr_id):
            qr = self.qr(qr_id)
            self.connection.execute(
                "INSERT INTO descobertas (usuario_id, campanha_id, local_id, qr_code_id) "
                "VALUES (?, ?, ?, ?)",
                (duplicate_id, qr["campanha_id"], qr["local_id"], qr_id),
            )
        self.connection.commit()
        return duplicate_id

    def test_existing_duplicates_share_distinct_progress_and_old_cookie_still_works(self):
        duplicate_id = self.add_legacy_duplicate()
        self.assertEqual(quantidade_descobertas(self.fixture.user_id), 2)
        self.assertEqual(quantidade_descobertas(duplicate_id), 2)
        qr = self.qr(self.fixture.phrase_qr_id)
        self.assertTrue(descoberta_ja_registrada(self.connection, self.fixture.user_id, qr["id"]))

        app = create_app()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        client = app.test_client()
        client.set_cookie("knn_lead_token", gerar_token_participante(duplicate_id))
        with client.session_transaction() as session:
            session[f"desafio_acertado_{qr['codigo']}"] = True
        page = client.get(f"/participar/{qr['codigo']}")
        self.assertIn("Este QR Code já foi contabilizado.".encode(), page.data)
        response = client.post(f"/participar/{qr['codigo']}", data={"confirmar_reconhecido": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(quantidade_descobertas(duplicate_id), 2)
        # Nenhum cadastro ou histórico antigo é apagado para corrigir a identidade.
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0], 2)

    def test_simultaneous_formatted_registrations_only_count_once(self):
        qr = dict(self.qr(self.fixture.phrase_qr_id))
        barrier = threading.Barrier(4)

        def register(phone):
            connection = database.get_connection()
            try:
                barrier.wait(timeout=5)
                result = self.save(qr, phone, connection)
                connection.commit()
                return result
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(register, ["31988887777", "(31) 98888-7777"] * 2))
        self.assertEqual(len({uid for uid, _ in results}), 1)
        self.assertEqual(sum(new for _, new in results), 1)
        self.assertEqual(quantidade_descobertas(results[0][0]), 1)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0], 2)

    def test_legacy_redeemed_prize_is_not_granted_again(self):
        duplicate_id = self.add_legacy_duplicate()
        database.init_db()
        self.save(self.qr(self.fixture.game_qr_ids[1]), "35999990000")
        reward_id = self.connection.execute("SELECT id FROM recompensas ORDER BY id LIMIT 1").fetchone()[0]
        self.connection.execute(
            "INSERT INTO premios (usuario_id, recompensa_id, status) VALUES (?, ?, 'utilizado')",
            (duplicate_id, reward_id),
        )
        self.connection.commit()
        criar_pass_se_necessario(self.fixture.user_id)
        criar_pass_se_necessario(duplicate_id)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM premios").fetchone()[0], 1)
        self.assertEqual(self.connection.execute("SELECT status FROM premios").fetchone()[0], "utilizado")

    def test_fourth_distinct_qr_keeps_count_and_single_maximum_prize(self):
        database.init_db()
        fourth_id = self.fixture._insert_qr(
            "GAME-004", self.fixture.game_campaign_id,
            self.qr(self.fixture.game_qr_ids[0])["local_id"],
        )
        self.connection.commit()
        for qr_id in (self.fixture.phrase_qr_id, self.fixture.game_qr_ids[1], fourth_id):
            _, new = self.save(self.qr(qr_id), "(35) 99999-0000")
            self.assertTrue(new)
            self.connection.commit()
            criar_pass_se_necessario(self.fixture.user_id)
        self.assertEqual(quantidade_descobertas(self.fixture.user_id), 4)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM premios").fetchone()[0], 1)

    def test_maximum_prize_message_for_later_and_repeated_qrs(self):
        client = create_app().test_client()
        for total, new in ((4, True), (25, True), (3, False), (4, False)):
            with self.subTest(total=total, new=new):
                with client.session_transaction() as session:
                    session["descobertas_usuario"] = total
                    session["novo_registro"] = new
                page = client.get("/conquista")
                self.assertEqual(page.status_code, 200)
                self.assertIn("Você já desbloqueou o prêmio máximo".encode(), page.data)
                self.assertIn(b"English Pass", page.data)
                self.assertNotIn("encontrou todos os QR Codes".encode(), page.data)
                self.assertNotIn("Encontre outros QR Codes para avançar".encode(), page.data)
