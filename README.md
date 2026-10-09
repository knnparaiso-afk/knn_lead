# INGLÊS SECRETO — KNN

Sistema de gamificação para campanha de marketing da KNN.

## Tecnologia

- Python
- Flask
- SQLite
- HTML
- CSS
- QR Code

## Instalação

Crie um ambiente virtual:

python -m venv venv

Ative:

Windows:

venv\Scripts\activate

Instale:

pip install -r requirements.txt

Execute:

python app.py

Abra:

http://127.0.0.1:5000

## Painel administrativo

Acesse:

http://127.0.0.1:5000/admin/login

Usuário padrão:

admin

Senha padrão:

knn123

IMPORTANTE:

Altere a senha antes de colocar o sistema em produção.

## Estrutura

app.py
    Aplicação Flask e rotas.

database.py
    Banco SQLite e criação das tabelas.

config.py
    Configurações do sistema.

instance/knn.db
    Banco de dados.

static/
    CSS e imagens.

templates/
    Páginas HTML.

## Fluxo

1. Administrador cria uma campanha.
2. Administrador cadastra locais.
3. Administrador gera QR Codes.
4. QR Code é colocado na cidade.
5. Participante escaneia.
6. Participante vê a mensagem.
7. Participante informa nome e WhatsApp.
8. Descoberta é registrada.
9. Após 3 descobertas, o English Pass é desbloqueado.

## Link público

Durante o desenvolvimento:

http://127.0.0.1:5000/e/CODIGO

No futuro:

https://inglessecreto.exemplo.com/e/CODIGO

O endereço público pode ser alterado pela variável BASE_URL.
