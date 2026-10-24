# Implementação local da primeira campanha

## Entregue

- Estúdio em /admin/estudio; Black Friday é criada como rascunho.
- Promoção, landing e jogo têm publicações independentes, com horário de Brasília,
  histórico, agendamento e reversão por seleção de revisão anterior.
- Rascunhos não alteram publicações. Sessões fixam sua revisão por até 24 horas.
- Prévia administrativa não cria sessão de jogo, respostas, lead ou métricas.
- Aventura Babylon.js com dois ambientes, dois personagens, sete desafios e
  continuidade HTML. Textos, alternativas e explicações editáveis.
- Cadastro compartilha o mesmo partial de campos do legado.
- Aula desbloqueada na conclusão, mesmo com zero acertos; prazo configurável.
- Origem por link/lote e QR PNG; nenhuma dependência de local/descoberta.
- Atendimento com responsável, próxima ação, histórico e vários agendamentos.
- Métricas deduplicadas por visita, sessão ou oportunidade, agregadas por dia.
- Sem publicação no Render, alteração de banco remoto, push ou credenciais novas.

## Preparação

Os bundles e os modelos selecionados são arquivos estáticos para versionar no
Git. Assim, o Build Command Python atual do Render pode ser mantido.
Para reconstruir localmente, com Node e pnpm disponíveis:

    pnpm install --frozen-lockfile --ignore-scripts
    pnpm run build:game

Para repetir a aquisição gratuita dos recursos oficiais (acesso à internet):

    python scripts/prepare_experience_assets.py
    pnpm run build:game

Não distribua os ZIPs completos: somente 15 GLBs selecionados, suas texturas,
licenças e arquivos comprimidos são usados. A origem e SHA-256 estão em
RECURSOS.json. Não sobrescreva uma biblioteca v1 já publicada: crie v2.

## Demonstração segura

    .venv\Scripts\python.exe scripts\preview_platform.py

Abre somente 127.0.0.1:5081 e usa SQLite temporário, com credenciais de processo.
O terminal mostra a página pública e um endereço aleatório para o estúdio.
O script publica os três destinos apenas nesse banco descartável.
Nenhuma variável DATABASE_URL ou senha real é usada.

## Verificações

    .venv\Scripts\python.exe scripts\check_platform.py

Os testes usam bancos isolados. PostgreSQL exige KNN_TEST_POSTGRES_URL apontando
para localhost; cada teste cria seu próprio schema. DATABASE_URL nunca escolhe
o banco de teste. Sem PostgreSQL local, esses casos são ignorados explicitamente.
Verificações de navegador em desktop/celular simulados não comprovam desempenho
em aparelhos físicos ou capacidade dos planos Render.

## Antes da divulgação

Revisar os sete desafios e os textos da oferta com a escola. O prazo inicial de
14 dias é configuração de rascunho, não uma condição comercial presumida.
Conferir BASE_URL, canal de privacidade, datas, disponibilidade e atendimento.
Aplicar as migrações aditivas primeiro em cópia/ambiente apropriado de PostgreSQL.
Não houve medição de carga no serviço público.

## Versões e reversão

O estúdio reverte conteúdo/publicações, preservando cadastros e histórico.
O módulo daily-adventure@1 e sua pasta de release devem ser congelados após
publicação. Mudanças incompatíveis de runtime, conteúdo ou recursos exigem
novo módulo/release, mantendo os arquivos anteriores durante sessões e reversões.
O editor é específico aos sete desafios e interações suportadas; não executa
scripts arbitrários enviados como conteúdo.

## Métricas e retenção

Visitas de landing/promoção são deduplicadas por visita de navegador de 30 min.
Início, conclusão, resultado e abertura de formulário são únicos por sessão.
Cadastro, primeiro agendamento, comparecimento e matrícula são únicos por
oportunidade; todos os compromissos ficam no histórico. Não são pessoas únicas
entre dispositivos e não equivalem a uma análise por coorte.
Filtros de data do painel usam o dia do evento. Cliques no WhatsApp não
comprovam conversa. Origem do lead fica associada à sessão que criou a oportunidade.

Executar periodicamente, em horário operacional apropriado:

    flask --app app platform-maintenance --days 90

Remove sessões anônimas expiradas há 90 dias e seus detalhes. Mantém dados
necessários ao atendimento e agregados. A unidade deve definir a política
de retenção e os procedimentos para contatos e histórico comercial.

## Limites conhecidos

Sem agenda externa, disparos automáticos de WhatsApp, certificação, reconhecimento
de fala, multiplayer ou editor genérico. O reconhecimento por telefone/cookie
preserva o comportamento atual e não é autenticação forte de identidade.
O formulário mantém a declaração existente; esta entrega não certifica sua
adequação jurídica nem substitui a revisão de privacidade pela unidade.
