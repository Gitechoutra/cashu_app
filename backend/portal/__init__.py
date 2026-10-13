import os
import logging
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

APP = None

db = SQLAlchemy()


def _init_logger(app):
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger('cardvault')
    logger.setLevel(logging.DEBUG if app.debug else logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh = RotatingFileHandler(os.path.join(log_dir, 'app.log'), maxBytes=10 * 1024 * 1024, backupCount=5)
        fh.setFormatter(fmt)
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)
    app.logger = logger


def _init_security_headers(app):
    @app.after_request
    def _headers(resp):
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('X-Frame-Options', 'DENY')
        resp.headers.setdefault('Referrer-Policy', 'no-referrer')
        resp.headers.setdefault('Cache-Control', 'no-store')
        if app.config['APP_ENV'] == 'PROD':
            resp.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return resp


def _init_error_handlers(app):
    # Never leak stack traces, SQL or secrets to the client.
    @app.errorhandler(429)
    def _rate_limited(e):
        return jsonify(bool=False, status=429, response={
            'message': 'Too many requests. Please slow down and try again shortly.',
            'code': 'RATE_LIMITED'}), 429

    @app.errorhandler(500)
    def _server_error(e):
        app.logger.exception('Unhandled server error')
        return jsonify(bool=False, status=500, response={
            'message': 'Something went wrong. Please try again.', 'code': 'SERVER_ERROR'}), 500


class InitApp:
    def app(self, config_name=None):
        global APP
        if APP is not None:
            return APP

        load_dotenv(override=os.environ.get('APP_ENV', '').upper() not in ('PROD', 'TEST'))
        from config.config import get_config, validate_config

        app = Flask(__name__)
        app.config.from_object(get_config(config_name))
        app.debug = app.config['DEBUG']
        validate_config(app)
        _init_logger(app)

        db.init_app(app)

        from .extensions import limiter, migrate
        migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'migrations')
        migrate.init_app(app, db, directory=migrations_dir)
        limiter.init_app(app)

        CORS(app, resources={r'/v1/*': {'origins': app.config['CORS_ORIGINS']}},
             supports_credentials=True)

        try:
            from . import api, routes, models
            from portal.helpers.jwt import Token

            models.init_app(app)
            routes.init_app()
            api.init_app(app)
            Token(app)
            _init_security_headers(app)
            _init_error_handlers(app)
        except Exception as e:
            app.logger.error('An error occurred while initializing app components: %s', e)
            raise

        app.logger.info(f"{app.config['APP_NAME']} initialised — environment: {app.config['APP_ENV']}")
        APP = app
        return app
