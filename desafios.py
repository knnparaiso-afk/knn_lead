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


def sortear_desafio(categoria="frases"):
    """Retorna um desafio aleatório da categoria especificada."""
    lista = DESAFIOS.get(categoria, DESAFIOS["frases"])
    return random.choice(lista)


def obter_desafio_por_id(desafio_id, categoria="frases"):
    """Retorna um desafio específico pelo ID."""
    lista = DESAFIOS.get(categoria, DESAFIOS["frases"])
    for d in lista:
        if d["id"] == desafio_id:
            return d
    return None
