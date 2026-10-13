# INGLÊS SECRETO — KNN

Aplicação Flask para campanhas, QR Codes, participantes, descobertas e recompensas.

## Banco de dados

- **Local:** se `DATABASE_URL` não estiver definida, usa `instance/knn.db` em SQLite, como antes.
- **Produção:** no Render, defina `DATABASE_URL` com a URL interna do PostgreSQL. O código mantém as chamadas `connection.execute(...)` já usadas pelo aplicativo e adapta placeholders `?`, IDs gerados e inicialização do esquema.
- **Importante:** o app cria as tabelas ao iniciar, mas não copia automaticamente os dados do SQLite para o PostgreSQL. Faça a migração antes de direcionar o tráfego real.

## Instalação local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Para usar SQLite localmente, não defina `DATABASE_URL`. Copie `.env.example` para `.env` se quiser personalizar as variáveis locais. Ajuste `BASE_URL` para o IP da rede local usado pelos celulares que leem os QR Codes.

## Preparar no Render

Configurações iniciais do Web Service:

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app`
- Configure `DATABASE_URL` usando a **Internal Database URL** do PostgreSQL do Render.
- Configure `SECRET_KEY` com um valor aleatório longo.
- Configure `ADMIN_USERNAME` e uma senha forte em `ADMIN_PASSWORD`.
- Configure `BASE_URL` para a URL pública final do serviço/domínio, sem barra no final.
- Mantenha o Web Service e o PostgreSQL na mesma região.

Não envie `.env`, `instance/`, banco SQLite, `.venv/` ou `.git/` para o repositório. O `.gitignore` desta versão exclui os dados locais. Se `instance/knn.db` ou `instance/qrcodes/` já foram adicionados ao Git, o `.gitignore` não os remove do rastreamento: remova-os do índice com `git rm --cached instance/knn.db` e `git rm --cached -r instance/qrcodes` (os arquivos locais permanecem no PC). Se já foram enviados ao GitHub, excluí-los num commit novo não apaga versões antigas do histórico.

## Migrar o banco SQLite para PostgreSQL

Execute a migração a partir da pasta do projeto original que contém o seu `instance/knn.db` atual. O ZIP completo preparado para deploy não inclui banco local, ambiente virtual, histórico `.git` nem QR PNGs gerados, para não duplicar nem divulgar dados locais. O ZIP de patch contém somente os arquivos a copiar para a pasta existente.

1. Faça backup do arquivo local `instance/knn.db`.
2. Crie o PostgreSQL no Render. Para conectar a partir do PC, use temporariamente a **External Database URL**; não compartilhe essa URL.
3. Instale as dependências e execute a migração a partir da raiz do projeto:

```powershell
$env:DATABASE_URL = "COLE_AQUI_A_URL_EXTERNA_DO_POSTGRESQL"
python migrate_sqlite_to_postgres.py
```

O script pede a confirmação literal `MIGRAR` e cancela se encontrar dados próprios no destino. Ele foi desenhado para um banco de destino vazio; teste e confira os totais antes de abrir o site ao público.

4. No painel do Render, configure a variável `DATABASE_URL` do Web Service com a **Internal Database URL** (não a externa) e publique a versão preparada.
5. Não apague nem altere o SQLite local até validar campanhas, QR Codes, participantes, descobertas, recompensas e login no site publicado.

## `pip freeze`

O arquivo `requirements-local-freeze.txt` registra as versões encontradas no ambiente virtual que veio no ZIP original. Para gerar o freeze diretamente no PC, com o ambiente virtual ativado, execute:

```powershell
python -m pip freeze > requirements-local-freeze.txt
```

O `requirements.txt` deste pacote inclui as dependências necessárias ao app e ao deploy (Gunicorn e driver PostgreSQL inclusive).
