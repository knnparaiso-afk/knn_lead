"""QR avulso: geração autenticada e cadastro direto em banco isolado."""
import html
import io
import re
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import qrcode
from PIL import Image

import database
from config import BASE_URL
from inglessecreto import create_app
from inglessecreto.services.participants import DIRECT_REGISTRATION_CONSENT_TEXT
from inglessecreto.services.campaigns import periodo_campanha
from inglessecreto.utils import TZ_BRASIL


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

    def black_campaign(self, **changes):
        page = self.admin.get("/admin/campanhas/nova?categoria=black_november")
        data = {"csrf_token": self.csrf(page), "nome": "Black Novembro Teste",
                "categoria": "black_november", "ativa": "on"}
        data.update(changes)
        response = self.admin.post("/admin/campanhas/nova", data=data)
        self.assertEqual(response.status_code, 302)
        campaign = self.rows("SELECT * FROM campanhas ORDER BY id DESC")[0]
        qr = self.rows("SELECT * FROM qrs_avulsos WHERE campanha_id = ?", (campaign["id"],))[0]
        return campaign, qr

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

    def test_black_campaign_drives_landing_registration_and_metrics(self):
        campaign, qr = self.black_campaign(
            comunidade_url="https://chat.whatsapp.com/local-test",
            comunidade_nacional_url="https://chat.whatsapp.com/national-test",
            chamada="Uma nova possibilidade", descricao="Invista em educação.",
        )
        landing = self.visitor.get("/")
        body = landing.get_data(as_text=True)
        for text in ("Uma nova possibilidade", "Invista em educação.", "local-test", "national-test",
                     "black-november-knn.jpeg", f"/black-november/{campaign['codigo']}"):
            self.assertIn(text, body)
        self.assertNotIn("Halloween", body)
        self.assertNotIn("FRANQUEADO", body)
        form = self.visitor.get(f"/black-november/{campaign['codigo']}")
        self.assertEqual(form.status_code, 200)
        self.assertIn("no-store", form.headers["Cache-Control"])
        response = self.visitor.post(f"/black-november/{campaign['codigo']}", data={
            "csrf_token": self.csrf(form), "nome": "Cadastro pela landing", "whatsapp": "35999991111",
            "email": "black@example.com", "idade": "28", "participacao_confirmada": "on",
        })
        self.assertEqual(response.location, "/")
        self.assertEqual(self.events(qr["id"]), {"acesso": 1, "cadastro_concluido": 1})
        self.assertEqual(self.total("qr_codes"), 0)
        self.assertEqual(self.total("descobertas"), 0)
        self.assertEqual(self.total("premios"), 0)
        manager = self.admin.get(f"/admin/qr/{campaign['id']}")
        self.assertEqual(manager.status_code, 302)
        self.assertIn(f"campanha_id={campaign['id']}", manager.location)
        self.assertIn(qr["codigo"], self.admin.get(manager.location).get_data(as_text=True))
        for path in ("/admin/dashboard", "/admin/campanhas", "/admin/locais"):
            self.assertEqual(self.admin.get(path).status_code, 200)

    def test_landing_only_shows_countdown_for_configured_active_deadline(self):
        campaign, _ = self.black_campaign()
        body = self.visitor.get("/").get_data(as_text=True)
        self.assertNotIn("data-campaign-timing", body)
        self.assertIn("data-reveal", body)
        self.assertNotIn("is-pending", body)
        connection = database.get_connection()
        connection.execute("UPDATE campanhas SET data_fim = '2099-11-30' WHERE id = ?", (campaign["id"],))
        connection.commit()
        connection.close()
        body = self.visitor.get("/").get_data(as_text=True)
        self.assertIn('data-end="2099-12-01T00:00:00-03:00"', body)
        self.assertIn("30/11/2099", body)
        self.assertNotIn("data-campaign-progress", body)

    def test_campaign_progress_uses_inclusive_local_dates_and_clamps_at_boundaries(self):
        campaign = {"data_inicio": "2026-11-01", "data_fim": "2026-11-30"}
        middle = periodo_campanha(campaign, datetime(2026, 11, 16, tzinfo=TZ_BRASIL))
        self.assertEqual(middle["fim"], "2026-12-01T00:00:00-03:00")
        self.assertEqual(middle["percentual"], 50)
        self.assertEqual(periodo_campanha(campaign, datetime(2026, 10, 1, tzinfo=TZ_BRASIL))["percentual"], 0)
        self.assertEqual(periodo_campanha(campaign, datetime(2026, 12, 1, tzinfo=TZ_BRASIL))["percentual"], 100)

    def test_campaign_dates_and_status_gate_both_old_qr_url_and_landing_url(self):
        campaign, qr = self.black_campaign()
        connection = database.get_connection()
        try:
            for active, start, end in ((0, None, None), (1, "2999-01-01", None), (1, None, "2000-01-01")):
                connection.execute("UPDATE campanhas SET ativa = ?, data_inicio = ?, data_fim = ? WHERE id = ?",
                                   (active, start, end, campaign["id"]))
                connection.commit()
                self.assertNotIn(f"/black-november/{campaign['codigo']}", self.visitor.get("/").get_data(as_text=True))
                for path in (f"/black-november/{campaign['codigo']}", f"/cadastro-parceiro/{qr['codigo']}"):
                    self.assertEqual(self.visitor.get(path).status_code, 404)
                    self.assertEqual(self.visitor.head(path).status_code, 404)
        finally:
            connection.close()
        self.assertEqual(self.total("eventos_qr_avulso"), 0)

    def test_link_existing_qr_preserves_url_registrations_and_metrics(self):
        existing = self.generate()
        self.register(existing["codigo"])
        campaign, _ = self.black_campaign()
        page = self.admin.get(f"/admin/qr-avulso?campanha_id={campaign['id']}")
        response = self.admin.post("/admin/qr-avulso/vincular", data={
            "csrf_token": self.csrf(page), "campanha_id": campaign["id"], "qr_id": existing["id"],
        })
        self.assertEqual(response.status_code, 302)
        linked = self.rows("SELECT * FROM qrs_avulsos WHERE id = ?", (existing["id"],))[0]
        self.assertEqual(linked["codigo"], existing["codigo"])
        self.assertEqual(linked["campanha_id"], campaign["id"])
        self.assertEqual(self.total("cadastros_qr_avulso"), 1)
        self.assertEqual(self.events(existing["id"]), {"acesso": 1, "cadastro_concluido": 1})
        self.assertEqual(self.visitor.get(f"/cadastro-parceiro/{existing['codigo']}").status_code, 200)
        self.assertIn("Pessoa Black November", self.admin.get(
            f"/admin/cadastros-parceiros?campanha_id={campaign['id']}").get_data(as_text=True))

    def test_deleting_black_campaign_preserves_history_and_disables_its_qrs(self):
        campaign, qr = self.black_campaign()
        self.register(qr["codigo"])
        page = self.admin.get("/admin/campanhas")
        self.assertEqual(self.admin.post(f"/admin/campanhas/{campaign['id']}/excluir",
                                        data={"csrf_token": self.csrf(page)}).status_code, 302)
        saved = self.rows("SELECT * FROM qrs_avulsos WHERE id = ?", (qr["id"],))[0]
        self.assertEqual(saved["ativo"], 0)
        self.assertIsNone(saved["campanha_id"])
        self.assertEqual(self.total("cadastros_qr_avulso"), 1)
        self.assertEqual(self.events(qr["id"]), {"acesso": 1, "cadastro_concluido": 1})
        self.assertEqual(self.visitor.get(f"/cadastro-parceiro/{qr['codigo']}").status_code, 404)

    def test_black_campaign_edit_updates_links_and_rejects_unsafe_urls(self):
        campaign, _ = self.black_campaign()
        path = f"/admin/campanhas/{campaign['id']}/editar"
        token = self.csrf(self.admin.get(path))
        base = {"csrf_token": token, "nome": campaign["nome"], "categoria": "black_november", "ativa": "on"}
        for invalid in ("javascript:alert(1)", "http://chat.whatsapp.com/test", "https://user:secret@example.com", "https://example.com/ bad"):
            response = self.admin.post(path, data={**base, "comunidade_url": invalid})
            self.assertIn("Informe links válidos", response.get_data(as_text=True))
            self.assertEqual(self.rows("SELECT comunidade_url FROM campanhas")[0]["comunidade_url"], "")
        response = self.admin.post(path, data={**base, "comunidade_url": "https://chat.whatsapp.com/valid"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("https://chat.whatsapp.com/valid", self.visitor.get("/").get_data(as_text=True))

    def test_existing_challenge_campaigns_still_allow_changing_challenge_type(self):
        token = self.csrf(self.admin.get("/admin/campanhas/nova"))
        self.admin.post("/admin/campanhas/nova", data={
            "csrf_token": token, "nome": "Campanha anterior", "categoria": "frases",
        })
        campaign = self.rows("SELECT * FROM campanhas")[0]
        path = f"/admin/campanhas/{campaign['id']}/editar"
        form = self.admin.get(path)
        response = self.admin.post(path, data={
            "csrf_token": self.csrf(form), "nome": campaign["nome"], "categoria": "jogos",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.rows("SELECT categoria FROM campanhas")[0]["categoria"], "jogos")

    def test_black_poster_uses_supplied_art_and_does_not_change_qr_destination(self):
        qr = self.generate()
        with patch("inglessecreto.services.black_qr_art.qrcode.QRCode.add_data", autospec=True) as add_data:
            poster = self.admin.get(f"/admin/qr-avulso/{qr['id']}/imagem?arte=black")
            self.assertEqual(add_data.call_args.args[1], f"{BASE_URL}/cadastro-parceiro/{qr['codigo']}")
        self.assertEqual(poster.status_code, 200)
        bitmap = Image.open(io.BytesIO(poster.data))
        self.assertEqual(bitmap.size, (1254, 2150))
        with Image.open(Path(__file__).resolve().parents[1] / "static/img/black-november-knn.jpeg") as supplied:
            self.assertEqual(bitmap.crop((0, 0, 1254, 1254)).tobytes(), supplied.convert("RGB").tobytes())

    def test_black_migration_preserves_previous_schema_codes_contacts_and_events(self):
        path = Path(database.DATABASE_PATH).with_name(f"black-migration-{uuid.uuid4().hex}.db")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        old_schema = database.SCHEMA_SQLITE
        for field in ("chamada", "descricao", "comunidade_url", "comunidade_nacional_url"):
            old_schema = old_schema.replace(f"    {field} TEXT NOT NULL DEFAULT '',\n", "")
        old_schema = old_schema.replace(
            "    ativo INTEGER NOT NULL DEFAULT 1,\n    campanha_id INTEGER REFERENCES campanhas(id) ON DELETE SET NULL",
            "    ativo INTEGER NOT NULL DEFAULT 1",
        )
        with patch.object(database, "DATABASE_PATH", str(path)):
            connection = database.get_connection()
            connection.executescript(old_schema)
            user_id = connection.execute("INSERT INTO usuarios(nome,whatsapp) VALUES ('Antigo','35999992222') RETURNING id").fetchone()["id"]
            qr_id = connection.execute("INSERT INTO qrs_avulsos(codigo,parceiro) VALUES ('IMPRESSO','Anterior') RETURNING id").fetchone()["id"]
            connection.execute("INSERT INTO cadastros_qr_avulso(usuario_id,qr_avulso_id) VALUES (?,?)", (user_id, qr_id))
            connection.execute("INSERT INTO eventos_qr_avulso(qr_avulso_id,evento) VALUES (?,'acesso')", (qr_id,))
            connection.commit()
            connection.close()
            database.init_db()
            database.init_db()
            saved = self.rows("SELECT * FROM qrs_avulsos")[0]
            self.assertEqual((saved["id"], saved["codigo"], saved["ativo"]), (qr_id, "IMPRESSO", 1))
            self.assertIsNone(saved["campanha_id"])
            self.assertEqual(self.total("cadastros_qr_avulso"), 1)
            self.assertEqual(self.events(qr_id), {"acesso": 1})


if __name__ == "__main__":
    unittest.main()
