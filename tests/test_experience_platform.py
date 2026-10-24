"""Campanhas, sessões e atendimento em banco isolado; sem tocar em produção."""
import copy
import time
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor

from test_campaign_flow import CampaignFlowMixin, POSTGRES_URL
from inglessecreto.services import experiences as platform
from inglessecreto.platform_schema import init_platform


class PlatformMixin(CampaignFlowMixin):
    def setUp(self):
        super().setUp()
        self.camp = platform.campaign(self.connection, "black-friday")
        self.rev = platform.latest_revision(self.connection, self.camp["id"])

    def publish(self, target, enabled=True, revision_id=None, starts_at=None, ends_at=None):
        platform.publish(self.connection, self.camp["id"], revision_id or self.rev["id"], target,
                         enabled, starts_at or int(time.time()) - 1, ends_at, 10, "test")
        self.connection.commit()

    def enable(self):
        for target in platform.TARGETS:
            self.publish(target)

    def begin(self, client):
        page = client.get("/promocoes/black-friday?canal=instagram&lote=stories")
        self.assertEqual(page.status_code, 200)
        token = self.csrf(page)
        response = client.post("/jogar/black-friday/iniciar", data={"csrf_token": token})
        self.assertEqual(response.status_code, 302)
        run_id = response.location.rsplit("/", 1)[-1]
        return run_id, token

    def complete(self, client, wrong=True):
        run_id, token = self.begin(client)
        for position, question in enumerate(self.rev["data"]["questions"]):
            choice = (question["correct"] + 1) % 3 if wrong else question["correct"]
            response = client.post("/api/experiencias/" + run_id + "/respostas",
                                   json={"position": position, "choice": choice},
                                   headers={"X-CSRFToken": token})
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertTrue(response.json["state"]["completed"])
        return run_id, token

    def test_black_friday_starts_as_draft_and_migration_is_idempotent(self):
        client = self.app.test_client()
        self.assertEqual(client.get("/promocoes/black-friday").status_code, 404)
        count = self.scalar("SELECT COUNT(*) AS total FROM pl_revisions")
        init_platform()
        self.assertEqual(self.scalar("SELECT COUNT(*) AS total FROM pl_revisions"), count)

    def test_pause_game_does_not_hide_landing_or_promotion(self):
        self.enable()
        self.publish("game", False)
        client = self.app.test_client()
        self.assertIn(self.rev["data"]["landing_title"], client.get("/").get_data(as_text=True))
        page = client.get("/promocoes/black-friday")
        self.assertEqual(page.status_code, 200)
        self.assertIn("jogo não está disponível", page.get_data(as_text=True))

    def test_all_wrong_answers_unlock_one_lesson_and_retries_are_idempotent(self):
        self.enable()
        client = self.app.test_client()
        run_id, token = self.complete(client)
        last = self.rev["data"]["questions"][-1]
        for _ in range(3):
            response = client.post("/api/experiencias/" + run_id + "/respostas",
                                   json={"position": 6, "choice": (last["correct"] + 1) % 3},
                                   headers={"X-CSRFToken": token})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.scalar("SELECT COUNT(*) AS total FROM pl_benefits"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) AS total FROM pl_answers"), 7)
        self.assertEqual(self.scalar("SELECT SUM(total) AS total FROM pl_daily_metrics WHERE event='game_complete'"), 1)
        page = client.get("/experiencia/" + run_id + "/resultado")
        self.assertIn("acertou 0 de 7", page.get_data(as_text=True))
        self.assertIn("aula grátis", page.get_data(as_text=True))

    def test_registration_reuses_fields_and_needs_no_qr_or_score(self):
        self.enable()
        client = self.app.test_client()
        run_id, token = self.complete(client)
        path = "/experiencia/" + run_id + "/cadastro"
        form = client.get(path).get_data(as_text=True)
        for name in ("nome", "whatsapp", "idade", "email", "participacao_confirmada"):
            self.assertIn('name="' + name + '"', form)
        for _ in range(2):
            response = client.post(path, data=dict(csrf_token=token, nome="Pessoa Teste",
                whatsapp="35988881111", idade="25", email="test@example.com", participacao_confirmada="on"))
            self.assertEqual(response.status_code, 302, response.get_data(as_text=True))
        self.assertEqual(self.scalar("SELECT COUNT(*) AS total FROM usuarios"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) AS total FROM pl_opportunities"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) AS total FROM descobertas"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) AS total FROM premios"), 0)
        self.assertEqual(self.scalar("SELECT SUM(total) AS total FROM pl_daily_metrics WHERE event='form_complete'"), 1)
        response = client.post("/experiencia/" + run_id + "/whatsapp", data={"csrf_token": token})
        self.assertEqual(response.status_code, 303)
        self.assertIn("wa.me/", response.location)
        self.assertNotIn("test@example", response.location)

    def test_no_gabarito_and_no_unauthorized_session_access(self):
        self.enable()
        owner = self.app.test_client()
        run_id, token = self.begin(owner)
        state = owner.get("/api/experiencias/" + run_id)
        self.assertNotIn("correct", state.json["question"])
        self.assertNotIn("explanation", state.json["question"])
        other = self.app.test_client()
        self.assertEqual(other.get("/api/experiencias/" + run_id).status_code, 404)
        skipped = owner.post("/api/experiencias/" + run_id + "/respostas",
                             json={"position": 6, "choice": 0}, headers={"X-CSRFToken": token})
        self.assertEqual(skipped.status_code, 409)
        missing_csrf = owner.post("/api/experiencias/" + run_id + "/respostas", json={"position": 0, "choice": 0})
        self.assertEqual(missing_csrf.status_code, 400)

    def test_new_publication_keeps_old_session_revision(self):
        self.enable()
        client = self.app.test_client()
        run_id, token = self.begin(client)
        changed = copy.deepcopy(self.rev["data"])
        changed["questions"][0]["prompt"] = "Nova pergunta em revisão."
        new_id = platform.save_revision(self.connection, self.camp["id"], changed)
        self.connection.commit()
        self.publish("game", revision_id=new_id)
        state = client.get("/api/experiencias/" + run_id).json
        self.assertEqual(state["revision_id"], self.rev["id"])
        self.assertNotEqual(state["question"]["prompt"], changed["questions"][0]["prompt"])

    def test_future_publication_and_rollback(self):
        self.enable()
        now = int(time.time())
        self.publish("game", False, starts_at=now + 3600)
        self.assertIsNotNone(platform.publication(self.connection, self.camp["id"], "game", now))
        self.assertIsNone(platform.publication(self.connection, self.camp["id"], "game", now + 3601))
        self.publish("game", True, starts_at=now + 3602)
        self.assertIsNotNone(platform.publication(self.connection, self.camp["id"], "game", now + 3603))

    def test_preview_generates_no_sessions_metrics_or_benefits(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["admin_logged"] = True
        page = client.get("/admin/estudio/previa/" + str(self.rev["id"]))
        self.assertEqual(page.status_code, 200)
        self.assertIn("SEM REGISTROS", page.get_data(as_text=True))
        for table in ("pl_sessions", "pl_events", "pl_benefits", "pl_opportunities"):
            self.assertEqual(self.scalar("SELECT COUNT(*) AS total FROM " + table), 0)
        outsider = self.app.test_client()
        self.assertEqual(outsider.get("/admin/estudio/previa/" + str(self.rev["id"])).status_code, 302)

    def test_repeated_views_count_one_visit_and_source_is_not_lost(self):
        self.enable()
        client = self.app.test_client()
        for _ in range(3):
            client.get("/promocoes/black-friday?canal=whatsapp&lote=turmas")
        self.assertEqual(self.scalar("SELECT SUM(total) AS total FROM pl_daily_metrics WHERE event='promotion_view'"), 1)
        run_id, _ = self.begin(client)
        run = self.connection.execute("SELECT * FROM pl_sessions WHERE id=?", (run_id,)).fetchone()
        self.assertEqual(run["channel"], "instagram")
        self.assertEqual(run["batch"], "stories")

    def test_server_validates_seven_questions(self):
        broken = copy.deepcopy(self.rev["data"])
        broken["questions"].pop()
        with self.assertRaises(ValueError):
            platform.save_revision(self.connection, self.camp["id"], broken)

    def test_pausing_new_starts_preserves_an_existing_run(self):
        self.enable()
        client = self.app.test_client()
        run_id, token = self.begin(client)
        self.publish("game", False)
        response = client.post("/api/experiencias/" + run_id + "/respostas",
                               json={"position": 0, "choice": 0}, headers={"X-CSRFToken": token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["state"]["answered"], 1)

    def test_expired_run_cannot_unlock_lesson(self):
        self.enable()
        client = self.app.test_client()
        run_id, token = self.begin(client)
        self.connection.execute("UPDATE pl_sessions SET expires_at=? WHERE id=?", (int(time.time()) - 1, run_id))
        self.connection.commit()
        response = client.post("/api/experiencias/" + run_id + "/respostas",
                               json={"position": 0, "choice": 0}, headers={"X-CSRFToken": token})
        self.assertEqual(response.status_code, 410)
        self.assertEqual(self.scalar("SELECT COUNT(*) AS total FROM pl_benefits"), 0)

    def test_channel_batch_link_needs_no_location_or_new_qr_record(self):
        self.enable()
        self.connection.execute(
            "INSERT INTO pl_sources (token,campaign_id,channel,batch,created_at) VALUES (?,?,?,?,?)",
            ("material-livre", self.camp["id"], "cartaz", "novembro", int(time.time())),
        )
        self.connection.commit()
        count = self.scalar("SELECT COUNT(*) AS total FROM qr_codes")
        client = self.app.test_client()
        response = client.get("/r/material-livre", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        token = self.csrf(response)
        response = client.post("/jogar/black-friday/iniciar", data={"csrf_token": token})
        run_id = response.location.rsplit("/", 1)[-1]
        row = self.connection.execute("SELECT channel,batch FROM pl_sessions WHERE id=?", (run_id,)).fetchone()
        self.assertEqual((row["channel"], row["batch"]), ("cartaz", "novembro"))
        self.assertEqual(self.scalar("SELECT COUNT(*) AS total FROM qr_codes"), count)

    def test_concurrent_answer_retries_store_only_the_first_answer(self):
        self.enable()
        client = self.app.test_client()
        run_id, token = self.begin(client)
        cookie = client.get_cookie(self.app.config["SESSION_COOKIE_NAME"])
        clients = [self.app.test_client() for _ in range(4)]
        for other in clients:
            other.set_cookie(self.app.config["SESSION_COOKIE_NAME"], cookie.value)
        barrier = threading.Barrier(4)
        def send(other):
            barrier.wait(timeout=10)
            return other.post("/api/experiencias/" + run_id + "/respostas",
                              json={"position": 0, "choice": 0},
                              headers={"X-CSRFToken": token}).status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(send, clients)), [200] * 4)
        self.assertEqual(self.scalar("SELECT COUNT(*) AS total FROM pl_answers"), 1)

    def test_commercial_confirmation_records_appointment_attendance_and_enrollment(self):
        self.enable()
        client = self.app.test_client()
        run_id, token = self.complete(client)
        client.post("/experiencia/" + run_id + "/cadastro",
                    data=dict(csrf_token=token, nome="Pessoa Teste", whatsapp="35988881111",
                              idade="25", email="test@example.com", participacao_confirmada="on"))
        lead = self.connection.execute("SELECT id FROM pl_opportunities").fetchone()
        with client.session_transaction() as session:
            session["admin_logged"] = True
        path = "/admin/estudio/atendimento/" + str(lead["id"])
        page = client.get(path)
        token = self.csrf(page)
        response = client.post(path, data=dict(csrf_token=token, status="agendado",
                               appointment_at="2026-11-20T14:00", owner="Equipe"))
        self.assertEqual(response.status_code, 302)
        appointment = self.connection.execute("SELECT id FROM pl_appointments").fetchone()
        response = client.post(path, data=dict(csrf_token=token, status="compareceu", appointment_id=appointment["id"]))
        self.assertEqual(response.status_code, 302)
        for _ in range(2):
            response = client.post(path, data=dict(csrf_token=token, status="matriculado"))
            self.assertEqual(response.status_code, 302)
        for name in ("scheduled", "attended", "enrolled"):
            self.assertEqual(self.scalar("SELECT SUM(total) AS total FROM pl_daily_metrics WHERE event=?", (name,)), 1)


class SQLiteExperiencePlatformTests(PlatformMixin, unittest.TestCase):
    pass


@unittest.skipUnless(POSTGRES_URL, "Defina KNN_TEST_POSTGRES_URL para PostgreSQL local isolado")
class PostgreSQLExperiencePlatformTests(PlatformMixin, unittest.TestCase):
    postgres = True


def load_tests(loader, tests, pattern):
    # Reuse legacy fixtures, not their test methods (which already run once).
    names = [name for name in vars(PlatformMixin) if name.startswith("test_")]
    return unittest.TestSuite(cls(name) for cls in (SQLiteExperiencePlatformTests, PostgreSQLExperiencePlatformTests)
                              for name in names)
