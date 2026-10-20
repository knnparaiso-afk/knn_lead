import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import database
from config import QR_LOCAL_GENERICO
from inglessecreto import create_app
from inglessecreto.services.participants import (
    quantidade_descobertas,
    salvar_participacao,
)


class QRLocationMigrationTests(unittest.TestCase):
    def setUp(self):
        instance_dir = Path(__file__).resolve().parents[1] / "instance"
        self.database_path = str(instance_dir / f"migration-test-{uuid.uuid4().hex}.db")
        self.database_url_patch = patch.object(database, "DATABASE_URL", None)
        self.database_path_patch = patch.object(
            database, "DATABASE_PATH", self.database_path
        )
        self.database_url_patch.start()
        self.database_path_patch.start()

        self.connection = database.get_connection()
        self.connection.executescript(database.SCHEMA_SQLITE)
        self._create_previous_data()

    def tearDown(self):
        self.connection.close()
        self.database_path_patch.stop()
        self.database_url_patch.stop()
        Path(self.database_path).unlink(missing_ok=True)

    def _create_previous_data(self):
        self.connection.executemany(
            "INSERT INTO locais (nome, endereco, parceiro, ativo) VALUES (?, ?, ?, 1)",
            [
                ("Local antigo 1", "Rua A", "Parceiro A"),
                ("Local antigo 2", "Rua B", "Parceiro B"),
            ],
        )
        self.old_local_ids = [
            row["id"]
            for row in self.connection.execute(
                "SELECT id FROM locais ORDER BY id"
            ).fetchall()
        ]

        self.game_campaign_id = self._insert_campaign(
            "game-campaign", "jogos"
        )
        self.phrase_campaign_id = self._insert_campaign(
            "phrase-campaign", "frases"
        )

        self.game_qr_ids = [
            self._insert_qr("GAME-001", self.game_campaign_id, self.old_local_ids[0]),
            self._insert_qr("GAME-002", self.game_campaign_id, self.old_local_ids[1]),
        ]
        self.phrase_qr_id = self._insert_qr(
            "PHRASE-001", self.phrase_campaign_id, self.old_local_ids[0]
        )

        cursor = self.connection.execute(
            "INSERT INTO usuarios (nome, whatsapp, email, idade) VALUES (?, ?, ?, ?)",
            ("Pessoa de teste", "35999990000", "teste@example.com", 30),
        )
        self.user_id = cursor.lastrowid
        self.connection.execute(
            """
            INSERT INTO descobertas
                (usuario_id, campanha_id, local_id, qr_code_id, data_hora)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                self.user_id,
                self.game_campaign_id,
                self.old_local_ids[0],
                self.game_qr_ids[0],
                "2026-10-01 12:34:56",
            ),
        )
        self.connection.commit()

    def _insert_campaign(self, code, category):
        cursor = self.connection.execute(
            """
            INSERT INTO campanhas
                (codigo, nome, semana, frase, traducao, categoria, ativa)
            VALUES (?, ?, 1, ?, ?, ?, 1)
            """,
            (code, code, "A test phrase", "A test translation", category),
        )
        return cursor.lastrowid

    def _insert_qr(self, code, campaign_id, local_id):
        cursor = self.connection.execute(
            "INSERT INTO qr_codes (codigo, campanha_id, local_id) VALUES (?, ?, ?)",
            (code, campaign_id, local_id),
        )
        return cursor.lastrowid

    def test_migration_preserves_every_qr_campaign_and_discovery(self):
        qr_before = [
            tuple(row)
            for row in self.connection.execute(
                "SELECT id, codigo, campanha_id FROM qr_codes ORDER BY id"
            ).fetchall()
        ]
        discovery_before = tuple(
            self.connection.execute(
                "SELECT id, usuario_id, campanha_id, qr_code_id, data_hora "
                "FROM descobertas"
            ).fetchone()
        )

        database._migrate_qr_location_tracking(self.connection)

        generic = self.connection.execute(
            "SELECT id FROM locais WHERE nome = ? AND ativo = 1",
            (QR_LOCAL_GENERICO,),
        ).fetchone()
        self.assertIsNotNone(generic)
        generic_id = generic["id"]

        qr_after = [
            tuple(row)
            for row in self.connection.execute(
                "SELECT id, codigo, campanha_id FROM qr_codes ORDER BY id"
            ).fetchall()
        ]
        self.assertEqual(qr_after, qr_before)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM qr_codes"
            ).fetchone()[0],
            3,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(DISTINCT campanha_id) FROM qr_codes"
            ).fetchone()[0],
            2,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM qr_codes WHERE local_id <> ?",
                (generic_id,),
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            tuple(
                self.connection.execute(
                    "SELECT id, usuario_id, campanha_id, qr_code_id, data_hora "
                    "FROM descobertas"
                ).fetchone()
            ),
            discovery_before,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT local_id FROM descobertas"
            ).fetchone()["local_id"],
            generic_id,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM locais WHERE ativo = 1"
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM locais WHERE id <> ? AND ativo = 0",
                (generic_id,),
            ).fetchone()[0],
            2,
        )

        database._migrate_qr_location_tracking(self.connection)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM locais WHERE nome = ?",
                (QR_LOCAL_GENERICO,),
            ).fetchone()[0],
            1,
        )

    def test_game_and_phrase_qrs_count_separately_but_duplicates_do_not(self):
        database._migrate_qr_location_tracking(self.connection)
        generic_id = self.connection.execute(
            "SELECT id FROM locais WHERE nome = ? AND ativo = 1",
            (QR_LOCAL_GENERICO,),
        ).fetchone()["id"]
        phrase_qr = self.connection.execute(
            "SELECT id, campanha_id, local_id FROM qr_codes WHERE id = ?",
            (self.phrase_qr_id,),
        ).fetchone()
        game_qr = self.connection.execute(
            "SELECT id, campanha_id, local_id FROM qr_codes WHERE id = ?",
            (self.game_qr_ids[0],),
        ).fetchone()
        another_game_qr = self.connection.execute(
            "SELECT id, campanha_id, local_id FROM qr_codes WHERE id = ?",
            (self.game_qr_ids[1],),
        ).fetchone()
        self.assertEqual(phrase_qr["local_id"], generic_id)
        self.assertEqual(game_qr["local_id"], generic_id)

        user_id, phrase_is_new = salvar_participacao(
            self.connection,
            phrase_qr,
            "Pessoa de teste",
            "35999990000",
            "teste@example.com",
            30,
        )
        same_user_id, phrase_duplicate_is_new = salvar_participacao(
            self.connection,
            phrase_qr,
            "Pessoa de teste",
            "35999990000",
            "teste@example.com",
            30,
        )
        _, game_duplicate_is_new = salvar_participacao(
            self.connection,
            game_qr,
            "Pessoa de teste",
            "35999990000",
            "teste@example.com",
            30,
        )
        _, another_game_is_new = salvar_participacao(
            self.connection,
            another_game_qr,
            "Pessoa de teste",
            "35999990000",
            "teste@example.com",
            30,
        )
        self.connection.commit()

        self.assertEqual(user_id, self.user_id)
        self.assertEqual(same_user_id, self.user_id)
        self.assertTrue(phrase_is_new)
        self.assertFalse(phrase_duplicate_is_new)
        self.assertFalse(game_duplicate_is_new)
        self.assertTrue(another_game_is_new)
        self.assertEqual(quantidade_descobertas(self.user_id), 3)

    def test_admin_can_generate_multiple_distinct_qrs_for_one_campaign(self):
        app = create_app()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        client = app.test_client()
        with client.session_transaction() as session:
            session["admin_logged"] = True

        generic = self.connection.execute(
            "SELECT id FROM locais WHERE nome = ? AND ativo = 1",
            (QR_LOCAL_GENERICO,),
        ).fetchone()
        self.assertIsNotNone(generic)

        page = client.get(f"/admin/qr/{self.game_campaign_id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("GERAR NOVO QR E ESCOLHER ARTE".encode("utf-8"), page.data)

        responses = [
            client.post(
                f"/admin/qr/{self.game_campaign_id}/{generic['id']}/gerar"
            )
            for _ in range(2)
        ]
        self.assertTrue(all(response.status_code == 302 for response in responses))

        generated = self.connection.execute(
            "SELECT codigo FROM qr_codes WHERE campanha_id = ? ORDER BY id DESC LIMIT 2",
            (self.game_campaign_id,),
        ).fetchall()
        self.assertEqual(len(generated), 2)
        self.assertNotEqual(generated[0]["codigo"], generated[1]["codigo"])

    def test_fourth_discovery_shows_completed_message(self):
        app = create_app()
        client = app.test_client()
        with client.session_transaction() as session:
            session["contato_autorizado"] = True
            session["descobertas_usuario"] = 4
            session["nome_usuario"] = "Pessoa"
            session["novo_registro"] = True

        response = client.get("/conquista")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Você já encontrou todos os QR Codes".encode("utf-8"),
            response.data,
        )
        self.assertIn("Venha retirar o prêmio em nossa escola".encode("utf-8"), response.data)


if __name__ == "__main__":
    unittest.main()
