# Base de implementação aprovada na conversa

## Produto

Captar interessados e encaminhá-los à aula grátis e à matrícula na KNN
Paraisópolis. Distribuição livre de links e QR Codes por canal/lote, sem caça
a locais. A promoção da landing não depende da ativação de um jogo.

## Etapa 1 — validada

Experiência "Um dia em inglês", aproximadamente três minutos (meta a medir),
dois ambientes (café e recepção de encontro), dois personagens principais.
Sete desafios: cumprimento, pedido, informação, diálogo, mensagem,
mudança de plano e convite. Sem timer avaliativo, vidas ou bloqueio por erro.
Primeira resposta produz uma indicação simples; explicação permite avançar.
Aula desbloqueada pela conclusão, incluindo quem erra tudo.
Resultado visível antes do cadastro. Preservar nome, celular, idade,
e-mail e confirmação já existentes. Agendamento pelo WhatsApp, confirmado
pela equipe. Convite de amigos é secundário.

## Etapa 2 — aprovada

3D estilizado, cenários compactos, gestos reutilizáveis, sem avatar do jogador,
sem exploração livre, dublagem ou sincronização labial. Seleção por toque e
diálogos HTML. Buscar recursos gratuitos (autorização explícita do usuário).
Kenney: candidatos de personagens, móveis e alimentos; conferir arquivo/licença.
Modelos de Halloween não são pressupostos da nova experiência.
Alternativa mais simples: reduzir objetos interativos e manter conversação.

## Etapa 3 — aceita para iniciar implementação

Babylon.js, com interface HTML e Flask existente. Conhecimento humano prévio
não é critério de escolha; a produção é feita por IA. Organizar recursos por
cena e carregar progressivamente. O 3D roda no cliente; PostgreSQL não recebe
frames ou movimentos. Dependências e assets locais versionados, sem CDN
de demonstração do motor em produção. Qualidade e capacidade devem ser medidas.

## Regras de arquitetura mantidas

Monólito modular. Publicações independentes para promoção, landing e jogo.
Revisões imutáveis, prévia administrativa isolada e reversão de conteúdo sem
restaurar o banco. Sessões ficam presas à revisão iniciada.
Métricas com deduplicação, agregados e retenção. Origem por canal/lote;
clique no WhatsApp não significa conversa ou agendamento.
Agendamento, presença e matrícula precisam de registro comercial.
Preservar identidade/consentimentos existentes; não criar outro formulário.
Sem serviços adicionais de infraestrutura sem evidência de necessidade.

## Limites e operação

Referência de compute informada pelo usuário: Flask 512 MB / 0,5 CPU e
PostgreSQL 256 MB / 0,1 CPU no Render. Não são garantias de capacidade.
Metas iniciais: primeira cena até 3 MB transferidos; jogo até 10 MB;
aproximadamente 30 FPS no aparelho de referência. Exigem medição.
Prévia não deve gerar lead, benefício ou métricas oficiais.
Primeira campanha deve nascer como rascunho; não presumir datas ou publicar.
