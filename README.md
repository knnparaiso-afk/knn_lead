# INGLÊS SECRETO — KNN

Aplicação Flask para campanhas, QR Codes, participantes, descobertas e recompensas.

Uma campanha marcada como ativa só aparece ao público entre as datas de início e
término informadas (inclusive). Fora desse período, respostas e cadastros pelo QR
são bloqueados. As datas são verificadas nas consultas; visitas ao site não alteram
automaticamente o campo `ativa` no banco. No painel, campanhas futuras aparecem
como **AGENDADA** e campanhas vencidas como **ENCERRADA**. O formulário rejeita
datas inválidas ou término anterior ao início.

## Cache dos arquivos e páginas

Arquivos estáticos com `?v=<hash do arquivo>` usam cache por um ano. O hash muda
quando o arquivo é alterado, inclusive nos modelos 3D dos ingredientes. Arquivos
sem hash válido, como as imagens carregadas pelo CSS da landing, usam cache de
cinco minutos. Essas duas imagens receberam uma nova URL para descartar cópias
antigas que tinham cache de um ano. O HTML público é revalidado a cada visita;
páginas de cadastro,
conquista, desafio e administração não são armazenadas em cache.

No jogo 3D, a abertura espera apenas a bruxa, o caldeirão e os três ingredientes
do primeiro passo. Os três itens seguintes são carregados em segundo plano; um
passo só começa quando todos os seus modelos estão prontos. Se um download falhar
ou não responder em 30 segundos, o jogador pode tentar novamente. Ao vencer, o
botão do prêmio espera a confirmação do servidor e oferece nova tentativa se a
conexão falhar.

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

Para usar SQLite localmente, não defina `DATABASE_URL`. Copie `.env.example` para `.env` e troque `ADMIN_USERNAME` e `ADMIN_PASSWORD` por credenciais locais suas antes de iniciar. O arquivo `.env` é ignorado pelo Git. Ajuste `BASE_URL` para o IP da rede local usado pelos celulares que leem os QR Codes.

## Preparar no Render

Configurações iniciais do Web Service:

- **Build Command:** `pip install -r requirements.txt`
- **Start Command documentado:** `gunicorn app:app` continua funcionando sem mudanças no Render.
- **Start Command opcional após medir:** `gunicorn -c gunicorn_render.py app:app`.
- Configure `DATABASE_URL` usando a **Internal Database URL** do PostgreSQL do Render.
- Configure `SECRET_KEY` com um valor aleatório longo.
- Configure `ADMIN_USERNAME` e `ADMIN_PASSWORD` como variáveis de ambiente. A aplicação agora falha ao iniciar se qualquer uma estiver ausente; não há mais usuário/senha padrão.
- Prefira armazenar `ADMIN_PASSWORD` como hash do Werkzeug (`pbkdf2:`, `scrypt:` ou `argon2:`), formato que o login já valida. Gere o valor localmente com `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Nova senha: ')))"` e salve apenas o resultado como variável de ambiente.
- Configure `BASE_URL` para a URL pública final do serviço/domínio, sem barra no final.
- Configure `PRIVACY_CONTROLLER_NAME`, `PRIVACY_CONTROLLER_CNPJ` e `PRIVACY_CONTACT_EMAIL` com os dados reais da empresa responsável.
- Mantenha o Web Service e o PostgreSQL na mesma região.

## Medir tráfego e capacidade

O arquivo `gunicorn_render.py` fica inativo com `gunicorn app:app`. Quando
ele for selecionado, começará com **um worker e quatro threads**. Assim, haverá
até quatro requisições em execução por processo, sem multiplicar a memória
por vários workers. Ajuste somente depois de medir o serviço real. As variáveis
`WEB_CONCURRENCY` e `GUNICORN_THREADS` permitem alterar esses valores. Durante
uma medição, `GUNICORN_ACCESS_LOG=1` registra status, bytes e duração em
microssegundos; remova a variável depois para reduzir volume de logs.

O medidor `scripts/traffic_probe.py` faz somente GET, não cria dados nem bancos.
Ele conta recursos encontrados no HTML/CSS de uma visita nova e da repetida,
simulando o reaproveitamento de recursos com cache fresco. Modelos 3D carregados
pelo JavaScript ficam fora dessa contagem. Para medir carga, cada usuário virtual
faz uma requisição por vez e espera um segundo entre elas:

```powershell
python scripts/traffic_probe.py visit http://127.0.0.1:5000/
python scripts/traffic_probe.py load http://127.0.0.1:5000/ --users 20 --duration 60
python scripts/traffic_probe.py load http://127.0.0.1:5000/ --users 50 --duration 15
```

Para medir o desafio, substitua `/` por `/e/CODIGO` de um QR existente. Caso
exista um serviço **de teste** no Render, use a URL dele com `--allow-remote` e
`--test-environment` nas cargas. O pico de 20/50 usuários não deve ser executado
no serviço publicado.

Como atualmente há somente o serviço público, não é necessário contratar outro
agora. Depois do deploy, faça apenas uma visita de leitura à URL pública com
`python scripts/traffic_probe.py visit https://SEU-SITE.onrender.com/ --allow-remote`
e acompanhe CPU, RAM e banda no painel do Render
durante o uso normal, especialmente no primeiro dia de campanha. Monitore
também as conexões do PostgreSQL; se houver acesso SQL, consulte
`SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();`.
Os logs de acesso opcionais permitem analisar duração e erros das requisições
reais. Isso mostra o comportamento em produção, mas não comprova capacidade de
20 ou 50 usuários simultâneos. Se a demanda crescer ou o p95/erros piorarem,
prepare um serviço de teste temporário antes de aumentar a carga.

Medição local de 18/10/2026, com Flask threaded e o SQLite existente, sem POST:

| Rota | Visita nova | Repetida | 20 usuários: p50 / p95 | 50 usuários: p50 / p95 | Erros |
| --- | --- | --- | --- | --- | --- |
| `/` | 7 GET, 530,5 KiB | 1 GET, 6,6 KiB | 4 / 498 ms | 7 / 1.254 ms | 0 |
| `/e/CODIGO` de jogo | 6 GET, 780,9 KiB | 1 GET, 9,6 KiB | 9 / 535 ms | 15 / 1.371 ms | 0 |

As cargas locais duraram 15 segundos com 20 usuários e 10 segundos com 50.
Esses números **não** medem Gunicorn, PostgreSQL, CPU/RAM ou a rede do Render;
portanto, ainda não comprovam a capacidade do plano. Os cinco modelos 3D
necessários para o primeiro passo somam de 324 a 418 KiB pré-comprimidos,
conforme os ingredientes sorteados; os 22 modelos somam 591 KiB. Esses bytes
se acrescentam à visita nova do jogo, e os modelos seguintes entram em segundo
plano. A validação de 20/50 usuários no Render fica pendente até existir um
ambiente de teste; não use o serviço público para essa carga sintética.

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


## Proteções de segurança adicionadas

- Proteção CSRF para formulários POST e chamadas AJAX; logout e geração de QR Code usam POST.
- Cookies de sessão `HttpOnly`, `SameSite=Lax`, `Secure` em produção e sessão administrativa com duração limitada.
- Cabeçalhos contra clickjacking, sniffing de conteúdo, vazamento de referrer e cache de páginas administrativas.
- Limites persistentes de tentativas por IP/intervalo no PostgreSQL/SQLite e limites de tamanho dos campos.
- Novos códigos de campanhas/QR Codes gerados com `secrets` e 12 caracteres; códigos antigos permanecem válidos para não inutilizar artes já impressas.
- Códigos QR não exibem campanhas inativas ou locais desativados.
- Registro versionado das declarações de privacidade, contato comercial e declaração de responsável, quando aplicável. O opt-in de marketing na experiência principal é opcional.
- Página `/privacidade` e links nos formulários/rodapé.

### Configurações que precisam ser conferidas no Render antes da divulgação

Defina `PRIVACY_CONTROLLER_NAME`, `PRIVACY_CONTROLLER_CNPJ` e `PRIVACY_CONTACT_EMAIL` com os dados reais da empresa/franqueada responsável. A página de privacidade sinaliza quando os valores ainda não foram preenchidos. A minuta deve ser revisada pela pessoa responsável pela privacidade/jurídico da unidade, especialmente as regras de crianças e adolescentes, bases legais, retenção e verificação do responsável. A declaração no formulário não verifica, sozinha, a identidade do responsável legal.

Verifique também `SECRET_KEY`, `ADMIN_USERNAME` e `ADMIN_PASSWORD` no Render. Use uma chave aleatória e uma senha administrativa longa, exclusiva e armazenada como hash. Não compartilhe credenciais no GitHub, em mensagens ou em capturas de tela. Para execução local, defina essas mesmas variáveis no ambiente ou em um arquivo `.env` ignorado pelo Git.

### Testes de segurança recomendados após o deploy

1. Confirme que `/admin/logout` não aceita GET e que o botão **Sair** funciona.
2. Confirme que excluir registros e gerar QR Code funcionam normalmente a partir do painel (o navegador precisa enviar CSRF token).
3. Abra um QR associado a campanha inativa: deve mostrar “Mensagem não encontrada”.
4. Envie várias tentativas de login/cadastro em sequência e confira a resposta HTTP 429 quando o limite for ultrapassado. Os limites compartilham o mesmo IP público; em eventos com muitos participantes na mesma rede, ajuste os limites de forma consciente.
5. Abra `/privacidade` e preencha todos os dados da unidade antes de divulgar.
6. Confira no navegador os cabeçalhos de segurança e o atributo `Secure` do cookie em HTTPS.

As novas tabelas `registros_consentimento` e `rate_limit_buckets` são criadas automaticamente ao iniciar a aplicação; não apagam nem reescrevem as tabelas existentes. Faça backup do PostgreSQL antes de publicar qualquer atualização.

## Estrutura do código

- `app.py`: ponto de entrada (`gunicorn app:app` continua válido).
- `inglessecreto/__init__.py`: `create_app()` (configuração, CSRF, ProxyFix, blueprints).
- `inglessecreto/security.py`: rate limit, limites de campo, cabeçalhos de segurança.
- `inglessecreto/blueprints/`: `public`, `auth`, `reports`, `campaigns`, `locations`, `qr`, `models`.
- `inglessecreto/services/`: regras de negócio (participantes/consentimentos, campanhas, arte do QR).

Nos templates, endpoints têm o prefixo do blueprint (ex.: `url_for('qr.gerar_qr', ...)`).
