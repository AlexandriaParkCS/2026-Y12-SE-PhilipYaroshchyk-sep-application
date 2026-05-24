import sqlite3
from datetime import datetime

import click
from flask import current_app, g
from flask.cli import with_appcontext

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

@click.command('init-db')
@with_appcontext
def init_db_command():
    init_db()

def init_app(app):

    """Register teardown and CLI command on the Flask app instance."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

sqlite3.register_converter(
    "timestamp", lambda v: datetime.fromisoformat(v.decode())
)