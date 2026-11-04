"""QR avulso: geração autenticada e cadastro direto em banco isolado."""
import html
import io
import re
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import qrcode
from PIL import Image

import database
from config import BASE_URL
from inglessecreto import create_app
from inglessecreto.services.participants import DIRECT_REGISTRATION_CONSENT_TEXT


class StandaloneQRTests(unittest.TestCase):
    def setUp(self):
        instance = Path(__file__).resolve().parents[1] / "instance"
        instance.mkdir(exist_ok=True)
        test_path = instance / f"standalone-test-{uuid.uuid4().hex}.db"
        self.addCleanup(lambda: test_path.unlink(missing_ok=True))
        self.enterContext(patch.object(database, "DATABASE_URL", None))
        self.enterContext(patch.object(database, "DATABASE_PATH", str(test_path)))
        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
        self.admin = self.app.test_client()
        with self.admin.session_transaction() as session:
            session["admin_logged"] = True
        self.visitor = self.app.test_client()

    def rows(self, sql, values=()):
        connection = database.get_connection()
        try:
            return connection.execute(sql, values).fetchall()
        finally:
            connection.close()

    def total(self, table):
        return self.rows(f"SELECT COUNT(*) AS total FROM {table}")[0]["total"]

    def events(self, qr_id):
        return {row["evento"]: row["total"] for row in self.rows(
            "SELECT evento, COUNT(*) AS total FROM eventos_qr_avulso "
            "WHERE qr_avulso_id = ? GROUP BY evento", (qr_id,),
        )}

    def csrf(self, response):
        match = re.search(r'<meta name="csrf-token" content="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match)
        return html.unescape(match[1])

    def generate(self):
        page = self.admin.get("/admin/qr-avulso")
        response = self.admin.post("/admin/qr-avulso", data={"csrf_token": self.csrf(page)})
        self.assertEqual(response.status_code, 302)
        return self.rows("SELECT * FROM qrs_avulsos ORDER BY id DESC")[0]

    def register(self, code, **changes):
        page = self.visitor.get(f"/cadastro-parceiro/{code}")
        data = {
            "csrf_token": self.csrf(page), "nome": "Pessoa Black November",
            "whatsapp": "(35) 98888-1111", "email": "pessoa@example.com", "idade": "30",
            "participacao_confirmada": "on",
        }
        data.update(changes)
        return self.visitor.post(f"/cadastro-parceiro/{code}", data=data)

    def test_generation_without_campaign_or_partner_and_png_destination(self):
        qr = self.generate()
        self.assertEqual(qr["parceiro"], "Black November")
        second = self.generate()
        self.assertNotEqual(qr["codigo"], second["codigo"])
        page = self.admin.get("/admin/qr-avulso")
        self.assertIn(f"/cadastro-parceiro/{qr['codigo']}", page.get_data(as_text=True))
        with patch("inglessecreto.blueprints.partner_qr.qrcode.make", wraps=qrcode.make) as make:
            png = self.admin.get(f"/admin/qr-avulso/{qr['id']}/imagem")
            make.assert_called_once_with(f"{BASE_URL}/cadastro-parceiro/{qr['codigo']}")
        self.assertEqual(png.mimetype, "image/png")
        self.assertIn("attachment;", png.headers["Content-Disposition"])
        Image.open(io.BytesIO(png.data)).verify()
        preview = self.admin.get(f"/admin/qr-avulso/{qr['id']}/imagem?preview=1")
        self.assertIn("inline;", preview.headers["Content-Disposition"])
        self.assertEqual(self.total("campanhas"), 0)
        self.assertEqual(self.total("qr_codes"), 0)

    def test_direct_form_persists_registration_then_redirects_to_landing(self):
        qr = self.generate()
        page = self.visitor.get(f"/cadastro-parceiro/{qr['codigo']}")
        body = page.get_data(as_text=True)
        for text in ("BLACK", "NOVEMBER", "material gratuito", "isenção da taxa de matrícula", "black-november.css"):
            self.assertIn(text, body)
        self.assertNotIn("public-lead", body)
        self.assertIn("no-store", page.headers["Cache-Control"])
        response = self.register(qr["codigo"])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/")
        self.assertEqual(self.visitor.get(response.location).status_code, 200)
        user = self.rows("SELECT * FROM usuarios")[0]
        self.assertEqual(user["whatsapp"], "35988881111")
        registration = self.rows("SELECT * FROM cadastros_qr_avulso")[0]
        self.assertEqual(registration["usuario_id"], user["id"])
        self.assertEqual(registration["qr_avulso_id"], qr["id"])
        self.assertEqual(self.rows("SELECT texto FROM registros_consentimento")[0]["texto"], DIRECT_REGISTRATION_CONSENT_TEXT)
        report = self.admin.get("/admin/cadastros-parceiros").get_data(as_text=True)
        for value in (user["nome"], user["whatsapp"], user["email"], qr["codigo"]):
            self.assertIn(value, report)
        self.assertIn("1 cadastro(s)", report)
        for table in ("campanhas", "qr_codes", "descobertas", "premios", "metricas_funil"):
            self.assertEqual(self.total(table), 0)

    def test_duplicates_do_not_count_twice_and_another_qr_keeps_its_origin(self):
        first = self.generate()
        self.register(first["codigo"])
        self.register(first["codigo"], whatsapp="35988881111")
        self.assertEqual(self.total("usuarios"), 1)
        self.assertEqual(self.total("cadastros_qr_avulso"), 1)
        second = self.generate()
        self.register(second["codigo"])
        self.assertEqual(self.total("usuarios"), 1)
        self.assertEqual(self.total("cadastros_qr_avulso"), 2)

    def test_invalid_form_preserves_fields_and_does_not_save(self):
        qr = self.generate()
        for changes in ({"whatsapp": "123"}, {"email": "invalido"}, {"idade": "2"}, {"participacao_confirmada": ""}):
            response = self.register(qr["codigo"], **changes)
            self.assertEqual(response.status_code, 400)
            self.assertIn('value="Pessoa Black November"', response.get_data(as_text=True))
        self.assertEqual(self.total("usuarios"), 0)
        self.assertEqual(self.total("cadastros_qr_avulso"), 0)

    def test_minor_records_guardian_authorization(self):
        qr = self.generate()
        self.assertEqual(self.register(qr["codigo"], idade="16").status_code, 302)
        types = {row["tipo"] for row in self.rows("SELECT tipo FROM registros_consentimento")}
        self.assertEqual(types, {"cadastro_parceiro", "responsavel_legal"})

    def test_auth_csrf_unknown_and_disabled_codes(self):
        qr = self.generate()
        for path in ("/admin/qr-avulso", "/admin/cadastros-parceiros",
                     f"/admin/qr-avulso/{qr['id']}/imagem", f"/admin/qr-avulso/{qr['id']}/metricas"):
            response = self.visitor.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin/login", response.location)
        self.assertEqual(self.admin.post("/admin/qr-avulso").status_code, 400)
        self.assertEqual(self.visitor.post(f"/cadastro-parceiro/{qr['codigo']}").status_code, 400)
        self.assertEqual(self.visitor.get("/cadastro-parceiro/inexistente").status_code, 404)
        connection = database.get_connection()
        connection.execute("UPDATE qrs_avulsos SET ativo = 0 WHERE id = ?", (qr["id"],))
        connection.commit()
        connection.close()
        self.assertEqual(self.visitor.get(f"/cadastro-parceiro/{qr['codigo']}").status_code, 404)
        self.assertEqual(self.total("cadastros_qr_avulso"), 0)
        self.assertEqual(self.total("eventos_qr_avulso"), 0)
        self.assertEqual(self.admin.get("/admin/qr-avulso/999999/metricas").status_code, 404)

    def test_metrics_are_exclusive_per_qr_with_conversion_and_no_campaign_events(self):
        first, second = self.generate(), self.generate()
        for _ in range(2):
            self.visitor.get(f"/cadastro-parceiro/{first['codigo']}")
        self.register(first["codigo"])
        self.register(first["codigo"])
        self.register(first["codigo"], whatsapp="123")
        self.register(second["codigo"])
        self.assertEqual(self.events(first["id"]), {
            "acesso": 5, "cadastro_concluido": 1, "cadastro_reenviado": 1, "erro_validacao": 1,
        })
        self.assertEqual(self.events(second["id"]), {"acesso": 1, "cadastro_concluido": 1})
        response = self.admin.get(f"/admin/qr-avulso/{first['id']}/metricas")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        for text in (first["codigo"], "20,0%", "Novo cadastro concluído", "Cadastro reenviado",
                     "Formulário com dados inválidos", "horário de Brasília"):
            self.assertIn(text, body)
        for text in (second["codigo"], "Pessoa Black November", "pessoa@example.com", "35988881111"):
            self.assertNotIn(text, body)
        self.assertIn("no-store", response.headers["Cache-Control"])
        listing = self.admin.get("/admin/qr-avulso").get_data(as_text=True)
        self.assertIn(f"/admin/qr-avulso/{first['id']}/metricas", listing)
        self.assertIn("5 acesso(s)", listing)
        self.assertEqual(self.total("metricas_funil"), 0)

    def test_head_previews_and_admin_pages_do_not_count_as_accesses(self):
        qr = self.generate()
        self.assertEqual(self.visitor.head(f"/cadastro-parceiro/{qr['codigo']}").status_code, 200)
        for path in (f"/admin/qr-avulso/{qr['id']}/imagem", f"/admin/qr-avulso/{qr['id']}/imagem?preview=1",
                     f"/admin/qr-avulso/{qr['id']}/metricas", "/admin/qr-avulso"):
            self.assertEqual(self.admin.get(path).status_code, 200)
        self.assertEqual(self.total("eventos_qr_avulso"), 0)
        body = self.admin.get(f"/admin/qr-avulso/{qr['id']}/metricas").get_data(as_text=True)
        self.assertIn("Nenhum evento registrado", body)
        self.assertNotIn("0,0%", body)

    def test_registration_and_success_metric_roll_back_together(self):
        qr = self.generate()
        with patch("inglessecreto.services.participants.registrar_consentimento", side_effect=RuntimeError("test rollback")):
            with self.assertRaisesRegex(RuntimeError, "test rollback"):
                self.register(qr["codigo"])
        self.assertEqual(self.total("usuarios"), 0)
        self.assertEqual(self.total("cadastros_qr_avulso"), 0)
        self.assertEqual(self.events(qr["id"]), {"acesso": 1})

    def test_existing_registrations_survive_metrics_table_creation(self):
        qr = self.generate()
        self.register(qr["codigo"])
        connection = database.get_connection()
        connection.execute("DROP TABLE eventos_qr_avulso")
        connection.commit()
        connection.close()
        database.init_db()
        database.init_db()
        self.assertEqual(self.total("usuarios"), 1)
        self.assertEqual(self.total("cadastros_qr_avulso"), 1)
        self.assertEqual(self.total("eventos_qr_avulso"), 0)
        body = self.admin.get(f"/admin/qr-avulso/{qr['id']}/metricas").get_data(as_text=True)
        self.assertIn("1 cadastro(s) salvo(s) neste QR", body)
        self.assertIn("Nenhum evento registrado", body)
        self.register(qr["codigo"])
        self.assertEqual(self.events(qr["id"]), {"acesso": 1, "cadastro_reenviado": 1})

    def test_log_shows_latest_100_events_but_totals_include_all(self):
        qr = self.generate()
        connection = database.get_connection()
        connection.executemany(
            "INSERT INTO eventos_qr_avulso (qr_avulso_id, evento) VALUES (?, ?)",
            [(qr["id"], "acesso")] * 105 + [(qr["id"], "erro_validacao")],
        )
        connection.commit()
        connection.close()
        body = self.admin.get(f"/admin/qr-avulso/{qr['id']}/metricas").get_data(as_text=True)
        self.assertEqual(body.count("<td>Acesso ao formulário</td>"), 99)
        self.assertEqual(body.count("<td>Formulário com dados inválidos</td>"), 1)
        self.assertIn("<strong>105</strong>", body)
        self.assertEqual(self.total("eventos_qr_avulso"), 106)


if __name__ == "__main__":
    unittest.main()
