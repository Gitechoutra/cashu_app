import os

from dotenv import load_dotenv

# In development, .env must win over values inherited from the reloader's parent process —
# otherwise editing .env (e.g. ADMIN_PIN) would not apply until a full manual restart.
# In PROD the real environment / secret manager stays authoritative.
load_dotenv(override=os.environ.get('APP_ENV', '').upper() not in ('PROD', 'TEST'))

from portal import InitApp, db  # noqa: E402

app = InitApp().app()


def _bootstrap():
    """Schema is owned by Flask-Migrate (`flask db upgrade`). AUTO_CREATE_TABLES=true
    is a development shortcut that creates missing tables only — it never alters or
    drops anything."""
    from sqlalchemy import inspect

    if os.getenv('AUTO_CREATE_TABLES', 'false').lower() == 'true' and app.config['APP_ENV'] != 'PROD':
        db.create_all()

    insp = inspect(db.engine)
    if not (insp.has_table('card_issuers') and insp.has_table('roles')):
        app.logger.warning('Tables not found — run:  flask db upgrade')
        return

    from portal.seeders import run_all_seeders
    try:
        run_all_seeders()
        app.logger.info('All seeders executed successfully.')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Seeder execution failed: {e}')


with app.app_context():
    try:
        _bootstrap()
    except Exception as e:   # DB down / not created yet — `flask db` commands must still work
        app.logger.warning(f'Database bootstrap skipped: {e.__class__.__name__}. '
                           'Is MySQL running and does the database exist?')


if __name__ == '__main__':
    # extra_files: editing .env (e.g. ADMIN_PIN / SUPPORT_PIN) also restarts the dev server,
    # which re-runs the seeders and applies the change to the database.
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', 5050)), debug=app.config['DEBUG'],
            extra_files=[env_file] if os.path.exists(env_file) else None)
