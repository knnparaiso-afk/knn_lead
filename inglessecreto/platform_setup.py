"""Filtros e manutenção explícita; nenhum job contínuo adicional."""
import time
from datetime import datetime

import click

from .utils import TZ_BRASIL


def register_platform(app):
    @app.template_filter("experience_date")
    def experience_date(value):
        return datetime.fromtimestamp(int(value), TZ_BRASIL).strftime("%d/%m/%Y às %H:%M")

    @app.cli.command("platform-maintenance")
    @click.option("--days", default=90, type=click.IntRange(30, 365))
    def maintenance(days):
        """Remove sessões anônimas antigas; preserva leads e agregados."""
        from .services.experiences import connection
        cutoff = int(time.time()) - days * 86400
        with connection(write=True) as db:
            # Linked sessions retain their evidence and idempotency keys.
            db.execute(
                "DELETE FROM pl_events WHERE created_at < ? AND "
                "(session_id IS NULL OR session_id IN "
                "(SELECT id FROM pl_sessions WHERE participant_id IS NULL AND expires_at < ?))",
                (cutoff, cutoff),
            )
            db.execute("DELETE FROM pl_benefits WHERE session_id IN "
                       "(SELECT id FROM pl_sessions WHERE participant_id IS NULL AND expires_at < ?)", (cutoff,))
            db.execute("DELETE FROM pl_sessions WHERE participant_id IS NULL AND expires_at < ?", (cutoff,))
        click.echo("Sessões anônimas antigas removidas; leads e métricas agregadas preservados.")
