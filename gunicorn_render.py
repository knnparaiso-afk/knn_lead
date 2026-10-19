"""Configuração inicial conservadora para o Web Service pequeno do Render.

Um worker evita multiplicar memória; quatro threads limitam o número de
consultas simultâneas que podem abrir conexões PostgreSQL. Ajuste após observar
o painel Render e medir com scripts/traffic_probe.py em ambiente de teste.
"""

import os


workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_class = "gthread"
bind = "0.0.0.0:" + os.getenv("PORT", "10000")

# Ative somente durante a medição para ver status, bytes e duração (microssegundos).
accesslog = "-" if os.getenv("GUNICORN_ACCESS_LOG") == "1" else None
access_log_format = '%(t)s %(m)s %(U)s %(s)s %(B)s %(D)s'
