# Análise de campanhas, participantes e origens

> Proposta inicial, anterior ao ajuste de escopo. A implementação mantém a temática da landing hardcoded, usa a modalidade genérica Cadastro direto e adota os QR avulsos atuais como Black, conforme esclarecido pelo usuário. Consulte o README para o comportamento implementado.

Análise do código local em 05/11/2026. Escopo: arquitetura e comportamento de campanhas, cadastros, QR Codes, relatórios, apresentação e recompensas. Não houve alteração no código da aplicação nem acesso ao banco de produção.

## Diagnóstico

A aplicação já possui uma base aproveitável: Flask com application factory, blueprints, serviços, cadastro central de pessoas, controle de vigência e testes dos fluxos. O problema principal está na modelagem do domínio. A identidade de uma ação comercial, a experiência de participação e o tema visual estão misturados em `campanhas.categoria`.

Hoje `frases` e `jogos` representam experiências; `black_november` representa uma campanha sazonal e implica cadastro direto. Essa diferença se espalhou por rotas, consultas, templates e criação de QR Codes. Uma próxima ação com cadastro direto exigiria novas exceções semelhantes às da Black.

Os cadastros das duas jornadas já usam `usuarios`. O que falta é um vínculo comum e explícito entre a pessoa e cada campanha, independente de desafio ou formulário direto.

## Evidências e efeitos

| Prioridade | Constatação | Evidência no código | Consequência |
| --- | --- | --- | --- |
| Alta | Tipo de experiência e identidade sazonal ocupam o mesmo campo | `inglessecreto/blueprints/campaigns.py:14`, `:125`; `inglessecreto/blueprints/qr.py:69`; `inglessecreto/blueprints/public.py:367` | O funcionamento depende de testar se a campanha é Black. |
| Alta | Participantes não têm uma visão comum por campanha | `inglessecreto/blueprints/reports.py:88`; `templates/admin/participantes.html:88`; `inglessecreto/blueprints/partner_qr.py:159` | A pessoa da Black aparece na lista geral, mas com progresso dos desafios e sem identificação da campanha. A data exibida é a criação da pessoa, não sua adesão à Black. |
| Alta | Contagens de interações são apresentadas como leads | `inglessecreto/blueprints/reports.py:33`; `inglessecreto/blueprints/campaigns.py:77`; `templates/admin/dashboard.html:38` | A mesma pessoa cadastrada em dois QR Codes da Black conta duas vezes; descobertas também podem contar várias vezes a mesma pessoa. |
| Alta | Exclusão desfaz a atribuição histórica | `inglessecreto/blueprints/campaigns.py:187`; `database.py:67`, `:103` | Na Black os registros sobrevivem, mas o vínculo com a campanha vira nulo. Nos desafios a exclusão elimina QR Codes e descobertas em cascata. |
| Alta | Progresso e prêmios têm escopo global | `inglessecreto/services/participants.py:182`, `:199`; `database.py:126` | Descobertas de campanhas distintas se somam; há um prêmio por usuário, sem vínculo com campanha ou programa. Isso impede autonomia entre futuras ações. |
| Média | A landing escolhe a Black por regra fixa | `inglessecreto/blueprints/public.py:86`; `templates/landing_base.html:6`; `templates/landing.html:16` | A Black tem prioridade automática; título, arte e textos permanecem Black mesmo sem campanha Black vigente. |
| Média | QR, cadastros e métricas têm dois modelos paralelos | `database.py:50`, `:61`, `:70`, `:83`, `:153`; `inglessecreto/blueprints/reports.py:59` | O relatório geral de métricas lê o funil de desafios; os eventos da Black são consultados em outra área. |
| Média | Identificação e atualização da pessoa foram duplicadas | `inglessecreto/services/participants.py:128`; `inglessecreto/blueprints/public.py:406` | O cadastro direto faz SQL e importa funções privadas do serviço de participantes; alterações precisam ser repetidas. |
| Média | Consentimento não registra o contexto da participação | `inglessecreto/services/participants.py:41`, `:72`; `database.py:130` | O texto do cadastro direto menciona Black para todos os QR avulsos; o registro não identifica campanha, QR ou participação. |
| Média | Convite e métricas podem perder o contexto original | `inglessecreto/blueprints/public.py:52`, `:557` | O convite amigável resolve a campanha mais recente da modalidade. Métricas usam o último contexto salvo na sessão, compartilhada entre abas. |

Os efeitos relacionados a convites e múltiplas abas foram inferidos do código; não houve reprodução no navegador. As demais evidências acima também não constituem auditoria dos dados reais da operação.

## Reprodução isolada

Utilizando a infraestrutura existente de testes e um banco SQLite temporário:

1. Criar uma campanha Black com dois QR Codes.
2. Cadastrar o mesmo WhatsApp nos dois códigos.
3. Resultado: uma pessoa, dois registros por QR, zero descobertas. A lista geral exibe progresso `0/3`.
4. Excluir a campanha Black.
5. Resultado: os dois cadastros permanecem e os dois QR Codes ficam sem `campanha_id`. O histórico preservado já não permite recuperar a campanha pela relação original.

O cadastro em dois QR Codes é válido como registro de duas origens. O erro está em usar essa quantidade como número de pessoas da campanha.

## Modelo proposto

Manter o monólito Flask e organizar um núcleo comum de campanhas, pessoas, participações, origens e métricas. Os nomes abaixo são propostas de domínio, não migrações já implementadas.

| Conceito | Responsabilidade |
| --- | --- |
| Pessoa (`usuarios`) | Identidade e dados de contato compartilhados entre as ações. |
| Campanha | Nome, código/slug, período, ativação, arquivamento, conteúdo e escolha de destaque no site. |
| Experiência | Mecânica: `cadastro_direto`, `quiz` ou `jogo`. Comportamento implementado por serviços próprios e um registro explícito de tipos disponíveis. |
| Tema | Templates, estilos e artes: Black, Halloween ou padrão. Não determina como participantes são gravados. |
| Participação | Associação da pessoa à campanha, com data de entrada e estado; unicidade de `(usuario_id, campanha_id)`. |
| Origem/captura | QR ou canal usado naquela participação, com data. Permite várias origens para a mesma participação e identifica a primeira entrada. |
| Evento | Ocorrência com campanha e origem explícitas; participação opcional quando já identificada. Payload mínimo e sem copiar dados de contato para logs. |
| Programa de recompensa | Regras e concessões com escopo explícito. Uma campanha pode ter seu programa; o legado pode compartilhar um programa quando necessário. |

Uma pessoa pode participar de Halloween e Black sem duplicar sua identidade. Uma participação pode ter duas origens sem duplicar o total de participantes da campanha. Visitas anônimas não criam pessoas nem participações.

Começar com uma experiência por campanha atende ao formato atual. Se uma mesma campanha comercial precisar reunir quiz e jogo, permitir experiências filhas da campanha; os dois tipos passam a compartilhar a participação e, quando configurado, o programa de recompensa. Não agrupar campanhas antigas automaticamente por nome ou data.

Exemplo de configuração:

| Nome da campanha | Experiência | Tema | Recompensa |
| --- | --- | --- | --- |
| Black November 2026 | Cadastro direto | Black November | Benefícios definidos para a ação |
| Halloween 2026 — Quiz | Quiz | Halloween | Programa legado compartilhado, se aplicável |
| Matrículas 2027 | Cadastro direto | Padrão | Sem progressão por descobertas |

Black November deve ser um modelo inicial que preenche esses valores. O serviço de cadastro depende de `cadastro_direto`, e o serviço de apresentação resolve o tema por uma lista permitida. O nome Black permanece nos conteúdos e artes pertinentes.

## Como o painel deve funcionar

O menu geral oferece Campanhas, Participantes, QR Codes e Métricas. Na página de uma campanha, as ações são Participantes, QR Codes, Métricas, Editar e Arquivar. Todas carregam `campanha_id` explicitamente.

O botão Participantes da Black abre, por exemplo, `/admin/campanhas/42/participantes`. A consulta parte do vínculo de participação, e a tela mostra pessoa, data de entrada nessa campanha, primeira origem, demais origens e estado daquela participação. Pessoas vindas de Halloween não aparecem nesse filtro, a menos que também tenham aderido à Black.

Na visão geral, a mesma pessoa pode mostrar ambas as campanhas. Remover uma participação e excluir a pessoa da base inteira precisam ser operações distintas, com efeitos claros.

Estados de negócio variam conforme a experiência: cadastro direto pode mostrar “Cadastro recebido”; quiz/jogo pode mostrar progresso. English Pass aparece no contexto das campanhas/programas que o utilizam.

Contadores têm definições separadas: pessoas únicas na base; participantes únicos por campanha; capturas por origem; acessos; conclusões de desafio; concessões de recompensa. O total geral de pessoas não deve ser a soma dos participantes de todas as campanhas.

Para o site, uma configuração explícita escolhe a campanha em destaque entre as vigentes. Cada campanha conserva sua URL própria. Sem destaque vigente, o site usa apresentação institucional. Temas não podem vazar de uma campanha para outra.

## Ordem de refatoração

1. **Fixar o comportamento de referência.** Resolver a divergência dos dois testes de prévia de recompensa. O código atual mostra a primeira recompensa antes da identificação; os testes esperam progresso do participante reconhecido. Comentários no código indicam uma decisão de comportamento que precisa ser refletida coerentemente nos testes.
2. **Entregar participantes e contadores por campanha.** Criar uma leitura comum das participações existentes com base em `descobertas` e `cadastros_qr_avulso`, mantendo os dois formatos de origem. Disponibilizar filtro geral e botão contextual, com contagens distintas de pessoas. Essa primeira entrega já resolve o sintoma descrito sem migrar todos os QR Codes.
3. **Introduzir a participação persistida e o serviço comum de cadastro.** Adicionar a tabela, preencher a partir das relações comprovadas e criar/atualizar pessoa, participação, origem, consentimento e evento na mesma transação. Restrições de unicidade e testes de concorrência devem assegurar idempotência. Duplicidades antigas de pessoas exigem mapeamento auditável, preservando referências e cookies.
4. **Separar experiência, tema e conteúdo.** Adicionar os novos campos/configurações, migrar `black_november` para cadastro direto + tema Black e converter frases/jogos para experiências próprias. Criar modelos iniciais para agilizar a operação. Reduzir os condicionais sazonais no núcleo.
5. **Consolidar QR Codes e métricas pela interface de serviço.** Primeiro unificar resolução e consultas; depois avaliar a união física das tabelas. IDs das duas tabelas podem coincidir: usar mapeamento por tabela de origem e ID, preservando códigos e URLs. Eventos antigos agregados e eventos detalhados precisam continuar distinguíveis e reconciliáveis.
6. **Isolar recompensas e apresentação.** Tornar o programa explícito, preservar o progresso compartilhado legado quando comprovado e impedir a soma automática entre futuras campanhas independentes. Separar a landing institucional dos temas de campanha.
7. **Substituir exclusão operacional por arquivamento.** Manter campanha, participações e atribuição de origem consultáveis; bloquear novas adesões após encerramento conforme a política da campanha. Exclusão definitiva fica como operação separada. Migrar alterações de esquema com versões e execução controlada, em vez de ampliar reparos sazonais no startup.

Cada etapa deve ter uma versão utilizável e verificável. Na transição, não criar novas participações antigas por suposição: QR ainda independente fica identificado como “origem legada sem campanha” até existir atribuição comprovada. Vincular um QR antigo exige uma política explícita para seus cadastros anteriores; o vínculo atual não comprova sozinho qual campanha originou cada evento passado.

As rotas `/e/<codigo>`, `/cadastro-parceiro/<codigo>` e `/black-november/<codigo>` devem continuar resolvendo os códigos já divulgados, como entradas de compatibilidade para os novos serviços. Não depender de redirecionamento para preservar POST e CSRF. A nova URL pública pode ser genérica, por campanha, sem invalidar as anteriores.

## Critérios de conclusão

- Criar uma campanha de cadastro direto com outro nome e tema funciona sem adicionar condicionais para esse nome no backend.
- A mesma pessoa em Halloween e Black aparece em ambas as campanhas, com datas e estados próprios.
- Dois QR Codes da mesma campanha geram uma participação e duas origens, sem duplicar pessoas no contador.
- Encerrar ou arquivar uma campanha não altera o histórico nem interrompe outra.
- URLs impressas, consentimentos anteriores, prêmios utilizados e eventos históricos permanecem íntegros.
- Recompensas de novas campanhas respeitam o escopo configurado; o legado mantém as concessões e o progresso previstos.
- Atribuição de métricas utiliza contexto validado da campanha/origem, incluindo acessos em abas distintas.
- Migrações são idempotentes e validadas com os mesmos cenários em SQLite e PostgreSQL antes de publicar.

## Validação realizada

Suite Python existente: **67 testes descobertos; 47 passaram, 2 falharam e 18 foram ignorados**. Os ignorados correspondem à classe opcional PostgreSQL; nenhuma instância PostgreSQL foi configurada nesta análise.

Falhas preexistentes nesta execução, sem alteração do código: `test_reward_preview_preserves_known_progress_and_duplicate_qr` e `test_known_participant_automatically_gets_reward_and_form_for_current_status`, ambos em `tests/test_campaign_flow.py`. Esperavam “Aula gratuita com certificado”, mas a prévia retornou “Combo KNN”.

Suite JavaScript existente: **7 testes passaram**. A reprodução de contagem e perda de vínculo descrita acima também foi executada em SQLite temporário. Não foi feita validação visual nem auditoria de produção.
