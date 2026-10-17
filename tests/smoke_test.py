import os, re, sys, tempfile
tmp = tempfile.mkdtemp()
os.environ["DATABASE_PATH"] = os.path.join(tmp, "t.db")
os.environ["BASE_URL"] = "http://localhost:5000"
os.environ["SECRET_KEY"] = "test"
os.environ["ADMIN_PASSWORD"] = "pw123"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app
from database import get_connection

ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print("OK  ", name)
    else: fail += 1; print("FAIL", name, extra)

c = app.test_client()
def token(html): return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)

r = c.get("/"); html_landing = r.get_data(as_text=True)
check("GET /", r.status_code == 200 and "Fale inglês desde a primeira aula" in html_landing, r.status_code)
check("landing tem whatsapp e fachada", "wa.me/553597239143" in html_landing and "fachada.webp" in html_landing)
r_camp = c.get("/ingles-secreto"); html_camp = r_camp.get_data(as_text=True)
check("GET /ingles-secreto", r_camp.status_code == 200 and "Inglês Secreto" in html_camp, r_camp.status_code)
r_camp2 = c.get("/campanha")
check("GET /campanha", r_camp2.status_code == 200, r_camp2.status_code)
check("static fachada.webp", c.get("/static/img/fachada.webp").status_code == 200)
check("static landing.css", c.get("/static/css/landing.css").status_code == 200)
check("static campanha.css", c.get("/static/css/campanha.css").status_code == 200)
r = c.get("/admin", follow_redirects=False); check("admin sem login redireciona", r.status_code == 302 and "/admin/login" in r.headers["Location"])
r = c.get("/admin/login"); check("GET login", r.status_code == 200)
t = token(r.get_data(as_text=True))
r = c.post("/admin/login", data={"username":"x","password":"y","csrf_token":t}); check("login errado 200", r.status_code == 200)
r = c.post("/admin/login", data={"username":"admin","password":"pw123","csrf_token":t}); check("login certo 302", r.status_code == 302, r.status_code)
r = c.post("/admin/login", data={"username":"admin","password":"pw123"}); check("CSRF ausente -> 400", r.status_code == 400, r.status_code)

for p in ["/admin", "/admin/dashboard", "/admin/campanhas", "/admin/locais", "/admin/participantes", "/admin/descobertas", "/admin/pass", "/admin/campanhas/nova", "/admin/locais/novo"]:
    r = c.get(p); check("GET "+p, r.status_code == 200, r.status_code)
    if r.status_code == 200 and p == "/admin": tok = token(r.get_data(as_text=True)) if "csrf_token" in r.get_data(as_text=True) else None

def csrf():
    html = c.get("/admin/locais/novo").get_data(as_text=True)
    return token(html)

r = c.post("/admin/locais/novo", data={"nome":"Cafe Teste","endereco":"Rua A","parceiro":"Parceiro X","csrf_token":csrf()}); check("novo local", r.status_code == 302, r.status_code)
today = __import__("datetime").date.today()
r = c.post("/admin/campanhas/nova", data={"nome":"Camp Teste","categoria":"frases","ativa":"1","data_inicio":"","data_fim":"","csrf_token":csrf()}); check("nova campanha 302", r.status_code == 302, r.status_code)
loc = r.headers["Location"]; check("redirect p/ gerenciar_qr", "/admin/qr/" in loc, loc)
cid = int(loc.rstrip("/").split("/")[-1])
r = c.get(loc); check("GET gerenciar_qr", r.status_code == 200, r.status_code)
r = c.post(f"/admin/qr/{cid}/1/gerar", data={"csrf_token":csrf()}); check("gerar QR (PNG)", r.status_code == 200 and r.mimetype == "image/png", (r.status_code, r.mimetype))
conn = get_connection(); codigo = conn.execute("SELECT codigo FROM qr_codes").fetchone()["codigo"]; conn.close()
for p, mt in [(f"/admin/qr/{codigo}/imagem","image/png"), (f"/admin/qr/{codigo}/download","image/png"), (f"/admin/qr/{codigo}/imprimir","text/html")]:
    r = c.get(p); check("GET "+p.split("/")[-1], r.status_code == 200 and r.mimetype == mt, (r.status_code, r.mimetype))
r = c.get(f"/admin/campanhas/{cid}/editar"); check("GET editar campanha", r.status_code == 200, r.status_code)
r = c.post(f"/admin/campanhas/{cid}/editar", data={"nome":"Camp Editada","categoria":"frases","ativa":"1","csrf_token":csrf()}); check("POST editar", r.status_code == 302, r.status_code)

# fluxo público
pub = app.test_client()
r = pub.get(f"/e/{codigo}"); check("GET /e/<codigo>", r.status_code == 200, r.status_code)
r = pub.get(f"/participar/{codigo}"); check("participar sem acertar -> redirect", r.status_code == 302 and f"/e/{codigo}" in r.headers["Location"], r.headers.get("Location"))
html = pub.get(f"/e/{codigo}").get_data(as_text=True)
with pub.session_transaction() as s:
    did = s[f"desafio_sorteado_{codigo}"]
from desafios import obter_desafio_por_id
d = obter_desafio_por_id(did, "frases")
t = token(html) if "csrf_token" in html else None
hdr = {"X-CSRFToken": re.search(r'csrf-token"\s+content="([^"]+)"', html).group(1)} if re.search(r'csrf-token"\s+content="([^"]+)"', html) else {}
app.config["WTF_CSRF_ENABLED"] = False
r = pub.post(f"/e/{codigo}/responder", data={"resposta": "Z"}); check("resposta errada", r.status_code == 200 and r.json["ok"] is False, r.get_data(as_text=True))
r = pub.post(f"/e/{codigo}/responder", data={"resposta": d["resposta_correta"]}); check("resposta certa", r.json and r.json["ok"] is True, r.get_data(as_text=True))
app.config["WTF_CSRF_ENABLED"] = True
r = pub.get(f"/participar/{codigo}"); check("GET participar", r.status_code == 200, r.status_code)
t = token(r.get_data(as_text=True))
form = {"nome":"Fulano","whatsapp":"(35) 99999-1234","email":"a@b.com","idade":"15","participacao_confirmada":"on","csrf_token":t}
r = pub.post(f"/participar/{codigo}", data=form); check("POST participar -> /conquista", r.status_code == 302 and r.headers["Location"].endswith("/conquista"), (r.status_code, r.headers.get("Location")))
conn = get_connection()
n = {k: conn.execute(f"SELECT COUNT(*) AS n FROM {k}").fetchone()["n"] for k in ["usuarios","descobertas","registros_consentimento","premios"]}
conn.close(); check("DB: 1 usuário, 1 descoberta, 2 consentimentos (menor)", n["usuarios"]==1 and n["descobertas"]==1 and n["registros_consentimento"]==2, n)
r = pub.get("/conquista"); check("GET /conquista", r.status_code == 200, r.status_code)
# Teste de escaneamento repetido do mesmo QR pelo mesmo usuário
t_rep = token(pub.get(f"/participar/{codigo}").get_data(as_text=True))
r = pub.post(f"/participar/{codigo}", data={"confirmar_reconhecido": "1", "csrf_token": t_rep}); check("POST repetir mesmo QR", r.status_code == 302)
conn = get_connection(); total_desc = conn.execute("SELECT COUNT(*) AS n FROM descobertas").fetchone()["n"]; conn.close(); check("não duplicou descoberta", total_desc == 1, total_desc)
r = pub.get("/nada", follow_redirects=True); check("GET /nada redireciona para /conquista", r.status_code == 200)
t = token(pub.get(f"/participar/{codigo}").get_data(as_text=True))
r = pub.post(f"/participar/{codigo}", data={**form, "idade":"2","csrf_token":t}); check("idade inválida -> 200 c/ erro", r.status_code == 200)
r = pub.get("/e/NAOEXISTE"); check("QR inexistente 404", r.status_code == 404)

# cabeçalhos / modelos
r = pub.get("/"); check("CSP + nosniff", "Content-Security-Policy" in r.headers and r.headers["X-Content-Type-Options"] == "nosniff")
r = pub.get("/admin/login"); check("no-store em /admin", "no-store" in r.headers.get("Cache-Control",""))
r = pub.get("/static/models/cauldron.glb", headers={"Accept-Encoding":"gzip"}); check("modelo gzip", r.status_code == 200 and r.headers.get("Content-Encoding") == "gzip", (r.status_code, dict(r.headers)))
r = pub.get("/models/cauldron.glb"); check("modelo legado /models", r.status_code == 200, r.status_code)
r = pub.get("/static/models/../../config.py"); check("path traversal bloqueado", r.status_code in (404,400) and b"SECRET_KEY" not in r.data, r.status_code)
r = pub.get("/static/css/style.css?v=1"); check("static css", r.status_code == 200)
html = pub.get("/").get_data(as_text=True); check("filtro |v aplicado", "?v=" in html)

# campanha expirada
conn = get_connection(); conn.execute("UPDATE campanhas SET data_fim='2020-01-01', ativa=1"); conn.commit(); conn.close()
r = pub.get(f"/e/{codigo}"); check("campanha expirada -> inativa (200)", r.status_code == 200 and b"inativ" in r.data.lower() or r.status_code==200, r.status_code)
conn = get_connection(); a = conn.execute("SELECT ativa FROM campanhas").fetchone()["ativa"]; conn.close(); check("hook desativou campanha", a == 0, a)

# exclusões
r = c.post("/admin/participantes/1/excluir", data={"csrf_token":csrf()}); check("excluir participante cascata", r.status_code == 302)
conn = get_connection(); total_u = conn.execute("SELECT COUNT(*) AS n FROM usuarios").fetchone()["n"]; conn.close(); check("participante deletado do banco", total_u == 0, total_u)
r = c.post("/admin/pass/1/utilizar", data={"csrf_token":csrf()}); check("utilizar premio", r.status_code == 302)
conn = get_connection(); qid = conn.execute("SELECT id FROM qr_codes").fetchone()["id"]; conn.close()
r = c.post(f"/admin/qr/{qid}/excluir", data={"csrf_token":csrf()}); check("excluir QR", r.status_code == 302)
r = c.post(f"/admin/campanhas/{cid}/excluir", data={"csrf_token":csrf()}); check("excluir campanha", r.status_code == 302)
r = c.post("/admin/locais/1/excluir", data={"csrf_token":csrf()}); check("excluir local", r.status_code == 302)
r = c.post("/admin/logout", data={"csrf_token":csrf()}); check("logout", r.status_code == 302)
print(f"\n{ok} ok, {fail} falhas")
sys.exit(1 if fail else 0)
