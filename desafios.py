import random

CATEGORIAS = {
    "frases": "Frases em Inglês",
    "jogos": "Jogos Interativos"
}

DESAFIOS = {
    "frases": [
        {
            "id": "ghost",
            "tema": "Ghost",
            "emoji": "👻",
            "frase": "Boo! Did I scare you?",
            "cor_bg": "#1e1b4b",
            "cor_accent": "#7c3aed",
            "descricao_visual": "Fantasmas flutuando, fundo roxo escuro, névoa",
            "opcoes": [
                {"letra": "A", "texto": "Buu! Você me assustou?"},
                {"letra": "B", "texto": "Buu! Eu te assustei?"},
                {"letra": "C", "texto": "Ei! Você está com medo de mim?"},
                {"letra": "D", "texto": "Buu! Eu estou assustado com você?"}
            ],
            "resposta_correta": "B"
        },
        {
            "id": "witch",
            "tema": "Witch",
            "emoji": "🧙",
            "frase": "What's the witch's spell?",
            "cor_bg": "#064e3b",
            "cor_accent": "#10b981",
            "descricao_visual": "Bruxa perto de um caldeirão soltando fumaça verde, partículas mágicas",
            "opcoes": [
                {"letra": "A", "texto": "Onde está a vassoura da bruxa?"},
                {"letra": "B", "texto": "Qual é o feitiço da bruxa?"},
                {"letra": "C", "texto": "Qual é o segredo da bruxa?"},
                {"letra": "D", "texto": "O que a bruxa está vendendo?"}
            ],
            "resposta_correta": "B"
        },
        {
            "id": "bats",
            "tema": "Bats",
            "emoji": "🦇",
            "frase": "Watch out for the bats!",
            "cor_bg": "#1c1917",
            "cor_accent": "#f97316",
            "descricao_visual": "Morcegos atravessando a tela em animação, lua ao fundo",
            "opcoes": [
                {"letra": "A", "texto": "Observe os morcegos!"},
                {"letra": "B", "texto": "Cuidado com os gatos!"},
                {"letra": "C", "texto": "Cuidado com os morcegos!"},
                {"letra": "D", "texto": "Afaste os morcegos daqui!"}
            ],
            "resposta_correta": "C"
        },
        {
            "id": "trick_or_treat",
            "tema": "Trick or Treat",
            "emoji": "🍬",
            "frase": "Trick or treat?",
            "cor_bg": "#431407",
            "cor_accent": "#fb923c",
            "descricao_visual": "Sacola de doces, balas flutuando e uma porta decorada com abóboras",
            "opcoes": [
                {"letra": "A", "texto": "Brincadeira ou susto?"},
                {"letra": "B", "texto": "Travessura ou presente?"},
                {"letra": "C", "texto": "Doces ou presentes?"},
                {"letra": "D", "texto": "Doces ou travessuras?"}
            ],
            "resposta_correta": "D"
        },
        {
            "id": "black_cat",
            "tema": "Black Cat",
            "emoji": "🐈‍⬛",
            "frase": "A black cat crossed my path!",
            "cor_bg": "#18181b",
            "cor_accent": "#a855f7",
            "descricao_visual": "Gato preto com olhos brilhantes, sombras misteriosas",
            "opcoes": [
                {"letra": "A", "texto": "Um gato preto cruzou meu caminho!"},
                {"letra": "B", "texto": "Um gato preto entrou na minha casa!"},
                {"letra": "C", "texto": "Um gato preto seguiu meus passos!"},
                {"letra": "D", "texto": "Um gato preto bloqueou minha passagem!"}
            ],
            "resposta_correta": "A"
        },
        {
            "id": "haunted_house",
            "tema": "Haunted House",
            "emoji": "🏚️",
            "frase": "Welcome to the haunted house!",
            "cor_bg": "#1a1a2e",
            "cor_accent": "#e94560",
            "descricao_visual": "Casa mal-assombrada, janelas iluminadas, névoa rasteira",
            "opcoes": [
                {"letra": "A", "texto": "Cuidado com a casa abandonada!"},
                {"letra": "B", "texto": "Bem-vindo à casa mal-assombrada!"},
                {"letra": "C", "texto": "Bem-vindo à casa assustadora!"},
                {"letra": "D", "texto": "Entre na casa assombrada!"}
            ],
            "resposta_correta": "B"
        },
        {
            "id": "skeleton",
            "tema": "Skeleton",
            "emoji": "💀",
            "frase": "Shake your bones!",
            "cor_bg": "#1f2937",
            "cor_accent": "#f9fafb",
            "descricao_visual": "Esqueleto dançando, ossos com animação",
            "opcoes": [
                {"letra": "A", "texto": "Quebre seus ossos!"},
                {"letra": "B", "texto": "Balance seus braços!"},
                {"letra": "C", "texto": "Mexa seus ossos!"},
                {"letra": "D", "texto": "Junte seus ossos!"}
            ],
            "resposta_correta": "C"
        },
        {
            "id": "spider",
            "tema": "Spider",
            "emoji": "🕷️",
            "frase": "There's a spider on your shoulder!",
            "cor_bg": "#0c0a09",
            "cor_accent": "#84cc16",
            "descricao_visual": "Teias nos cantos, uma aranha descendo por um fio",
            "opcoes": [
                {"letra": "A", "texto": "Tem uma aranha no seu ombro!"},
                {"letra": "B", "texto": "Tem uma aranha atrás de você!"},
                {"letra": "C", "texto": "Tem uma aranha na sua cabeça!"},
                {"letra": "D", "texto": "Tem uma aranha perto do seu braço!"}
            ],
            "resposta_correta": "A"
        },
        {
            "id": "zombie",
            "tema": "Zombie",
            "emoji": "🧟",
            "frase": "Run for your life!",
            "cor_bg": "#1a2e05",
            "cor_accent": "#65a30d",
            "descricao_visual": "Cemitério escuro, mãos de zumbis saindo do chão",
            "opcoes": [
                {"letra": "A", "texto": "Corra para encontrar sua vida!"},
                {"letra": "B", "texto": "Corra para salvar sua vida!"},
                {"letra": "C", "texto": "Corra para salvar outra pessoa!"},
                {"letra": "D", "texto": "Corra para longe da vida!"}
            ],
            "resposta_correta": "B"
        },
        {
            "id": "full_moon",
            "tema": "Full Moon",
            "emoji": "🌕",
            "frase": "The werewolves are coming!",
            "cor_bg": "#0f172a",
            "cor_accent": "#38bdf8",
            "descricao_visual": "Lua cheia enorme, floresta sombria e silhueta de lobisomem",
            "opcoes": [
                {"letra": "A", "texto": "Os lobisomens já foram embora!"},
                {"letra": "B", "texto": "Os lobos estão dormindo!"},
                {"letra": "C", "texto": "Os lobisomens estão chegando!"},
                {"letra": "D", "texto": "Os lobisomens estão nos procurando!"}
            ],
            "resposta_correta": "C"
        },
        {
            "id": "pumpkin",
            "tema": "Pumpkin",
            "emoji": "🎃",
            "frase": "Let's carve a pumpkin!",
            "cor_bg": "#431407",
            "cor_accent": "#fb923c",
            "descricao_visual": "Abóbora esculpida com sorriso iluminado e brilho laranja",
            "opcoes": [
                {"letra": "A", "texto": "Vamos esculpir uma abóbora!"},
                {"letra": "B", "texto": "Vamos comprar uma abóbora!"},
                {"letra": "C", "texto": "Vamos pintar uma abóbora!"},
                {"letra": "D", "texto": "Vamos cozinhar uma abóbora!"}
            ],
            "resposta_correta": "A"
        },
        {
            "id": "vampire",
            "tema": "Vampire",
            "emoji": "🧛",
            "frase": "The vampire is afraid of sunlight!",
            "cor_bg": "#450a0a",
            "cor_accent": "#f87171",
            "descricao_visual": "Vampiro escondido em sombras vermelhas longe da luz do sol",
            "opcoes": [
                {"letra": "A", "texto": "O vampiro está procurando a luz do sol!"},
                {"letra": "B", "texto": "O vampiro tem medo da luz do sol!"},
                {"letra": "C", "texto": "O vampiro gosta da luz do sol!"},
                {"letra": "D", "texto": "O vampiro está dormindo ao sol!"}
            ],
            "resposta_correta": "B"
        },
        {
            "id": "candle",
            "tema": "Candle",
            "emoji": "🕯️",
            "frase": "Light the candle before it gets dark!",
            "cor_bg": "#451a03",
            "cor_accent": "#fbbf24",
            "descricao_visual": "Vela acesa com chama dourada iluminando a escuridão",
            "opcoes": [
                {"letra": "A", "texto": "Apague a vela antes de escurecer!"},
                {"letra": "B", "texto": "Acenda a vela depois de escurecer!"},
                {"letra": "C", "texto": "Acenda a vela antes de escurecer!"},
                {"letra": "D", "texto": "Esconda a vela antes de escurecer!"}
            ],
            "resposta_correta": "C"
        },
        {
            "id": "magic_potion",
            "tema": "Magic Potion",
            "emoji": "🧪",
            "frase": "Don't drink the magic potion!",
            "cor_bg": "#052e16",
            "cor_accent": "#4ade80",
            "descricao_visual": "Frasco de poção verde brilhante soltando bolhas mágicas",
            "opcoes": [
                {"letra": "A", "texto": "Não derrame a poção mágica!"},
                {"letra": "B", "texto": "Não prepare a poção mágica!"},
                {"letra": "C", "texto": "Não toque na poção mágica!"},
                {"letra": "D", "texto": "Não beba a poção mágica!"}
            ],
            "resposta_correta": "D"
        },
        {
            "id": "owl",
            "tema": "Owl",
            "emoji": "🦉",
            "frase": "Can you hear the owl?",
            "cor_bg": "#292524",
            "cor_accent": "#fcd34d",
            "descricao_visual": "Coruja de olhos dourados em um galho na floresta noturna",
            "opcoes": [
                {"letra": "A", "texto": "Você consegue ouvir a coruja?"},
                {"letra": "B", "texto": "Você consegue ver a coruja?"},
                {"letra": "C", "texto": "Você consegue encontrar a coruja?"},
                {"letra": "D", "texto": "Você consegue alimentar a coruja?"}
            ],
            "resposta_correta": "A"
        },
        {
            "id": "spider_web",
            "tema": "Spider Web",
            "emoji": "🕸️",
            "frase": "The door is covered in spider webs!",
            "cor_bg": "#1e293b",
            "cor_accent": "#cbd5e1",
            "descricao_visual": "Porta antiga coberta por teias prateadas",
            "opcoes": [
                {"letra": "A", "texto": "A janela está coberta de teias de aranha!"},
                {"letra": "B", "texto": "A porta está coberta de teias de aranha!"},
                {"letra": "C", "texto": "A porta está coberta de folhas secas!"},
                {"letra": "D", "texto": "O chão está coberto de teias de aranha!"}
            ],
            "resposta_correta": "B"
        },
        {
            "id": "magic_broom",
            "tema": "Magic Broom",
            "emoji": "🧹",
            "frase": "The witch is flying on her broom!",
            "cor_bg": "#2e1065",
            "cor_accent": "#c084fc",
            "descricao_visual": "Vassoura mágica cruzando um céu roxo com rastros brilhantes",
            "opcoes": [
                {"letra": "A", "texto": "A bruxa está limpando sua vassoura!"},
                {"letra": "B", "texto": "A bruxa está procurando sua vassoura!"},
                {"letra": "C", "texto": "A bruxa está voando em sua vassoura!"},
                {"letra": "D", "texto": "A bruxa está escondendo sua vassoura!"}
            ],
            "resposta_correta": "C"
        },
        {
            "id": "coffin",
            "tema": "Coffin",
            "emoji": "⚰️",
            "frase": "Something is moving inside the coffin!",
            "cor_bg": "#292019",
            "cor_accent": "#d6a876",
            "descricao_visual": "Caixão de madeira com tampa entreaberta e sombras misteriosas",
            "opcoes": [
                {"letra": "A", "texto": "Algo está brilhando dentro do caixão!"},
                {"letra": "B", "texto": "Algo está se movendo atrás do caixão!"},
                {"letra": "C", "texto": "Algo está caindo sobre o caixão!"},
                {"letra": "D", "texto": "Algo está se movendo dentro do caixão!"}
            ],
            "resposta_correta": "D"
        },
        {
            "id": "crystal_ball",
            "tema": "Crystal Ball",
            "emoji": "🔮",
            "frase": "Look into the crystal ball!",
            "cor_bg": "#3b0764",
            "cor_accent": "#e879f9",
            "descricao_visual": "Bola de cristal com névoa violeta e reflexos mágicos",
            "opcoes": [
                {"letra": "A", "texto": "Olhe dentro da bola de cristal!"},
                {"letra": "B", "texto": "Olhe atrás da bola de cristal!"},
                {"letra": "C", "texto": "Esconda a bola de cristal!"},
                {"letra": "D", "texto": "Quebre a bola de cristal!"}
            ],
            "resposta_correta": "A"
        },
        {
            "id": "werewolf",
            "tema": "Werewolf",
            "emoji": "🐺",
            "frase": "The werewolf is howling at the moon!",
            "cor_bg": "#172554",
            "cor_accent": "#93c5fd",
            "descricao_visual": "Lobisomem uivando sob a luz azulada da lua",
            "opcoes": [
                {"letra": "A", "texto": "O lobisomem está correndo sob a lua!"},
                {"letra": "B", "texto": "O lobisomem está uivando para a lua!"},
                {"letra": "C", "texto": "O lobisomem está se escondendo da lua!"},
                {"letra": "D", "texto": "O lobisomem está dormindo sob a lua!"}
            ],
            "resposta_correta": "B"
        },
        {
            "id": "autumn_leaves",
            "tema": "Autumn Leaves",
            "emoji": "🍂",
            "frase": "Dry leaves are falling from the trees!",
            "cor_bg": "#431407",
            "cor_accent": "#fdba74",
            "descricao_visual": "Folhas secas alaranjadas caindo em um caminho escuro",
            "opcoes": [
                {"letra": "A", "texto": "Folhas verdes estão caindo das árvores!"},
                {"letra": "B", "texto": "Galhos secos estão caindo das árvores!"},
                {"letra": "C", "texto": "Folhas secas estão caindo das árvores!"},
                {"letra": "D", "texto": "Folhas secas estão cobrindo as janelas!"}
            ],
            "resposta_correta": "C"
        },
        {
            "id": "midnight",
            "tema": "Midnight",
            "emoji": "🕛",
            "frase": "The clock strikes midnight!",
            "cor_bg": "#1e1b4b",
            "cor_accent": "#a5b4fc",
            "descricao_visual": "Relógio antigo marcando meia-noite sob um brilho azulado",
            "opcoes": [
                {"letra": "A", "texto": "O relógio está atrasado!"},
                {"letra": "B", "texto": "O relógio marca meio-dia!"},
                {"letra": "C", "texto": "O relógio parou de funcionar!"},
                {"letra": "D", "texto": "O relógio bate meia-noite!"}
            ],
            "resposta_correta": "D"
        },
        {
            "id": "costume",
            "tema": "Costume",
            "emoji": "🎭",
            "frase": "What a scary costume!",
            "cor_bg": "#4a044e",
            "cor_accent": "#f0abfc",
            "descricao_visual": "Máscaras de Halloween e uma fantasia envolta em luz magenta",
            "opcoes": [
                {"letra": "A", "texto": "Que fantasia assustadora!"},
                {"letra": "B", "texto": "Que festa assustadora!"},
                {"letra": "C", "texto": "Que fantasia engraçada!"},
                {"letra": "D", "texto": "Que história assustadora!"}
            ],
            "resposta_correta": "A"
        },
        {
            "id": "magic_book",
            "tema": "Magic Book",
            "emoji": "📖",
            "frase": "Open the book of spells!",
            "cor_bg": "#312e81",
            "cor_accent": "#c4b5fd",
            "descricao_visual": "Livro antigo aberto com letras mágicas em luz lilás",
            "opcoes": [
                {"letra": "A", "texto": "Feche o livro de feitiços!"},
                {"letra": "B", "texto": "Abra o livro de feitiços!"},
                {"letra": "C", "texto": "Esconda o livro de histórias!"},
                {"letra": "D", "texto": "Abra o livro de receitas!"}
            ],
            "resposta_correta": "B"
        },
        {
            "id": "enchanted_forest",
            "tema": "Enchanted Forest",
            "emoji": "🌲",
            "frase": "We are lost in the enchanted forest!",
            "cor_bg": "#022c22",
            "cor_accent": "#6ee7b7",
            "descricao_visual": "Floresta de árvores altas com névoa verde e caminhos misteriosos",
            "opcoes": [
                {"letra": "A", "texto": "Estamos sozinhos na casa encantada!"},
                {"letra": "B", "texto": "Estamos chegando à floresta encantada!"},
                {"letra": "C", "texto": "Estamos perdidos na floresta encantada!"},
                {"letra": "D", "texto": "Estamos saindo da floresta encantada!"}
            ],
            "resposta_correta": "C"
        },
        {
            "id": "chocolate",
            "tema": "Chocolate",
            "emoji": "🍫",
            "frase": "Save some chocolate for me!",
            "cor_bg": "#2c1810",
            "cor_accent": "#e8b88a",
            "descricao_visual": "Barras de chocolate entre doces de Halloween em tons de cacau",
            "opcoes": [
                {"letra": "A", "texto": "Compre um pouco de chocolate para mim!"},
                {"letra": "B", "texto": "Derreta um pouco de chocolate para mim!"},
                {"letra": "C", "texto": "Esconda todo o chocolate de mim!"},
                {"letra": "D", "texto": "Guarde um pouco de chocolate para mim!"}
            ],
            "resposta_correta": "D"
        },
        {
            "id": "magic_key",
            "tema": "Magic Key",
            "emoji": "🗝️",
            "frase": "This key opens the secret door!",
            "cor_bg": "#422006",
            "cor_accent": "#facc15",
            "descricao_visual": "Chave antiga dourada diante de uma porta secreta",
            "opcoes": [
                {"letra": "A", "texto": "Esta chave abre a porta secreta!"},
                {"letra": "B", "texto": "Esta chave fecha o baú secreto!"},
                {"letra": "C", "texto": "Esta chave abre a janela secreta!"},
                {"letra": "D", "texto": "Esta chave esconde a porta secreta!"}
            ],
            "resposta_correta": "A"
        },
        {
            "id": "fog",
            "tema": "Fog",
            "emoji": "🌫️",
            "frase": "I can't see through the fog!",
            "cor_bg": "#1f2937",
            "cor_accent": "#d1d5db",
            "descricao_visual": "Névoa prateada cobrindo uma rua escura e silenciosa",
            "opcoes": [
                {"letra": "A", "texto": "Não consigo caminhar pela floresta!"},
                {"letra": "B", "texto": "Não consigo enxergar através da neblina!"},
                {"letra": "C", "texto": "Não consigo ouvir através da porta!"},
                {"letra": "D", "texto": "Não consigo sair da casa!"}
            ],
            "resposta_correta": "B"
        },
        {
            "id": "monster",
            "tema": "Monster",
            "emoji": "👾",
            "frase": "There is a monster under my bed!",
            "cor_bg": "#2e1065",
            "cor_accent": "#a78bfa",
            "descricao_visual": "Monstrinho roxo espiando debaixo de uma cama",
            "opcoes": [
                {"letra": "A", "texto": "Tem um monstro atrás da minha porta!"},
                {"letra": "B", "texto": "Tem um monstro em cima da minha cama!"},
                {"letra": "C", "texto": "Tem um monstro debaixo da minha cama!"},
                {"letra": "D", "texto": "Tem um monstro dentro do meu armário!"}
            ],
            "resposta_correta": "C"
        },
        {
            "id": "storm",
            "tema": "Storm",
            "emoji": "⛈️",
            "frase": "A storm is coming tonight!",
            "cor_bg": "#0c1a33",
            "cor_accent": "#7dd3fc",
            "descricao_visual": "Nuvens escuras com relâmpagos azulados sobre a cidade",
            "opcoes": [
                {"letra": "A", "texto": "Uma tempestade passou ontem à noite!"},
                {"letra": "B", "texto": "Uma tempestade está chegando amanhã cedo!"},
                {"letra": "C", "texto": "Uma tempestade está acabando esta noite!"},
                {"letra": "D", "texto": "Uma tempestade está chegando esta noite!"}
            ],
            "resposta_correta": "D"
        }
    ],
    "jogos": [
        {
            "id": "witchs_potion",
            "tema": "Witch's Potion",
            "emoji": "🧙",
            "tipo": "jogo",
            "template": "jogo_witchs_potion.html",
            "frase": "Help me prepare my magic potion!",
            "cor_bg": "#1a0a2e",
            "cor_accent": "#39ff14",
            "descricao_visual": "Bruxa preparando poção mágica com caldeirão borbulhante e ingredientes mágicos",
            "opcoes": [],
            "resposta_correta": "GAME_COMPLETE"
        }
    ]
}


def sortear_desafio(categoria="frases", excluir_ids=()):
    """Sorteia entre os desafios ainda não vistos; reinicia ao esgotar a lista."""
    lista = DESAFIOS.get(categoria, DESAFIOS["frases"])
    excluir_ids = tuple(excluir_ids)
    excluidos = set(excluir_ids)
    disponiveis = [d for d in lista if d["id"] not in excluidos]
    if not disponiveis:
        # No início de outro ciclo, evita repetir imediatamente o último desafio.
        ultimo_id = next(reversed(excluir_ids), None) if excluir_ids else None
        disponiveis = [d for d in lista if d["id"] != ultimo_id] or lista
    return random.choice(disponiveis)


def obter_desafio_por_id(desafio_id, categoria="frases"):
    """Retorna um desafio específico pelo ID."""
    lista = DESAFIOS.get(categoria, DESAFIOS["frases"])
    for d in lista:
        if d["id"] == desafio_id:
            return d
    return None
