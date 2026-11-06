# INGLÊS SECRETO — KNN

Aplicação Flask para campanhas, QR Codes, participantes, descobertas e recompensas.

## Página de links da unidade

`/bio` reúne o agendamento de aula grátis pelo WhatsApp, o convite da comunidade
de Paraisópolis e o site oficial. `/links`, `/links/` e `/bio/` redirecionam para
`/bio`; a página inicial e as campanhas mantêm seus endereços. O visual usa o logo
existente e as cores preto, roxo e laranja, com três botões simples. A arte oficial
Black November é usada na prévia de compartilhamento.

O botão no canto superior abre o compartilhamento com prévia da unidade, cópia do
link, redes sociais e e-mail, seguindo a organização do Linktree. Compartilha sempre
o endereço público definido por `BASE_URL` + `/bio`. O Messenger abre o compositor;
cole o link copiado para enviá-lo. A opção **Mais** aparece quando o navegador oferece
compartilhamento nativo. É possível fechar com Escape, pelo X ou clicando fora.

O convite fornecido pela unidade é o padrão de `BIO_COMUNIDADE_URL`; essa variável
pode substituí-lo no Render sem alterar o código. Se estiver vazia ou não for uma
URL HTTPS, o botão informa que o acesso deve ser pedido à equipe e abre o WhatsApp.
O agendamento abre uma conversa com mensagem pronta; a equipe confirma dia e horário.
A página não depende de campanha vigente. Configure `BASE_URL` com o domínio público
para o endereço canônico e a imagem de compartilhamento.

Na landing Black November, comunidades e benefícios têm chamadas de destaque na
abertura. Os convites local e nacional mantêm a mesma ênfase visual. Quando a
campanha não tem convite local, a landing e a confirmação usam o convite permanente
de `BIO_COMUNIDADE_URL`, também usado por `/bio`; o link específico da campanha tem
prioridade. Sem um convite HTTPS válido, o visitante pode pedir acesso à unidade.

Após um cadastro direto confirmado pelo servidor, o visitante chega a
`/cadastro-parceiro/concluido`, com confirmação, conversa pelo WhatsApp e acesso às
comunidades da campanha em que se cadastrou. Recarregar essa página não cria novos
cadastros nem eventos de conclusão. O cadastro inicia o atendimento; não confirma
matrícula nem reserva de vaga. O formulário permanece com os campos atuais e usa
o cabeçalho Black November. As demais experiências conservam sua identidade.

A landing e o cadastro usam a fonte variável Manrope, servida pelo próprio site.
O campo WhatsApp mantém o rótulo e a máscara de digitação, sem placeholder.
Um caminho SVG conecta as seções e se preenche conforme a rolagem avança; ao
voltar, o preenchimento recua. Em movimento reduzido, ele fica completo e estático.
As três fotos institucionais escolhidas no site oficial da rede usam WebP e
carregamento tardio. Origens dos arquivos e licença da fonte estão em
`docs/landing-assets.md`.

**Avaliações** apresenta três trechos reais do perfil da KNN Paraisópolis no
Google Maps, em cartões com estrelas e autoria. A nota média e o total aparecem
separados da seleção. A data da consulta fica registrada nos dados de origem em
`inglessecreto/reviews.py`; origem e critérios estão em `docs/avaliacoes-google.md`.

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

A landing mantém o tema definido no código e acrescenta parallax discreto em
camadas, revelações laterais, barra de leitura e menu fixo com indicação da seção
ativa. No celular, o menu desliza horizontalmente para manter o item atual visível;
o parallax usa amplitude reduzida. O fade acompanha a posição real dos blocos na
rolagem, inclusive ao voltar a uma seção, sem depender de IntersectionObserver ou
de uma animação que executa apenas uma vez. Com movimento reduzido, permanece
somente a transparência, sem deslocamento nem parallax. A primeira dobra tem uma
entrada leve. Em desktops largos e altos, o alinhamento entre seções
usa scroll snapping por proximidade, sem prender o conteúdo das campanhas longas.
As animações respeitam movimento reduzido. A barra de leitura acompanha a página;
a barra da campanha continua representando apenas o período cadastrado.

Para investigar diferenças de um aparelho, abra `/?debug-motion=1` e use
**Copiar diagnóstico**. O painel informa versão dos arquivos, motor de efeitos,
preferência de movimento e erros do navegador. Ele só aparece nesse link e não
envia informações ao servidor; o texto é copiado pelo próprio usuário.

## Campanhas de cadastro direto, origens e Black November

Use **Campanhas → + NOVA CAMPANHA**, escolha **Cadastro direto** e informe
nome (por exemplo, Black November), período, status, chamada e descrição.
Ao salvar, a campanha recebe um QR para impressão e uma origem exclusiva da
landing. A modalidade funciona independentemente do nome da ação.

Marque **Exibir faixa na landing** para escolher o destaque. A faixa usa os dados
da campanha e só aparece enquanto ela estiver ativa e vigente. Escolher outra
campanha remove o destaque anterior; desmarcar a opção não interrompe seus QR.
A temática, artes e demais textos da landing e do formulário continuam hardcoded,
para atualização pelo código. Os links das comunidades permanecem no formulário
da campanha. Configure `BASE_URL` antes de imprimir.

O botão **PARTICIPANTES** de cada campanha mostra as pessoas daquela ação,
com data de entrada e todas as origens (QR impresso ou landing). A visão geral
permite filtrar por campanha. Uma pessoa em dois QR da mesma campanha conta uma
vez como participante, mantendo os dois cadastros por origem. A exclusão de uma
pessoa nessa tela é da base inteira, como o botão e a confirmação informam.

**MÉTRICAS E LOG** na campanha consolida participantes, acessos, novos cadastros
por origem, reenvios, erros e os últimos 100 eventos, em horário de Brasília.
Cada origem também mantém seu relatório individual. Cadastros por origem e
participantes únicos são contagens diferentes. O histórico salvo antes das
métricas permanece disponível; acessos anteriores não são inventados.

### Adoção dos QR Black já distribuídos

Na primeira inicialização da versão, a migração
`direct_campaigns_adopt_black_qrs_v1` vincula os QR avulsos anteriores sem campanha
à Black November. Esta adoção corresponde à identificação desses QR como Black
pelo responsável pela aplicação. QR já vinculados conservam sua campanha.

Se existe uma única campanha de cadastro direto vigente, ela é reutilizada.
Caso contrário, a migração cria **Black November**, ativa e sem datas, para
preservar o acesso dos QR que funcionavam de forma independente. Ela pode ser
editada depois pelo painel. QR desativados continuam desativados.

A migração conserva IDs, códigos, endereços `/cadastro-parceiro/CODIGO`,
identificações, datas de cadastro, consentimentos e todos os eventos existentes.
Os cadastros antigos passam a aparecer na campanha por meio dos mesmos QR.
Ela executa uma vez, com bloqueio e transação: uma falha desfaz a adoção parcial.
Novos avulsos criados depois não são reatribuídos automaticamente ao reiniciar.

As categorias antigas `black_november` são convertidas para `cadastro_direto`.
Links públicos `/black-november/CODIGO` continuam aceitando GET e POST; os novos
links da landing usam `/cadastro/CODIGO`. Ambos resolvem a origem exclusiva da
landing. QR impressos continuam resolvendo a própria origem.

Depois da vinculação, status e período da campanha controlam seus acessos.
**Arquivar** encerra novos cadastros e preserva a campanha, o vínculo dos QR,
participantes e métricas. A operação anterior de excluir campanhas de cadastro
direto agora arquiva, sem apagar o histórico. Campanhas de desafios conservam
seus fluxos e regras anteriores.

Faça backup do banco antes de publicar. As migrações são executadas por
`init_db()` na inicialização. Os testes usam bancos temporários; a alteração do
código local não executa a migração no banco de produção.

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
