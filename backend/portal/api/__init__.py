from flask import Blueprint
from flask_restx import Api

api = Api(
    version='1.0',
    title='CardVault API',
    description='Backend API for CardVault — credit card management, bills and payments',
    doc='/doc/',
    catch_all_404s=True,
)


def init_app(app):
    v1 = Blueprint('api', __name__, url_prefix='/v1')
    api.init_app(v1)

    # Namespaces register themselves via api.namespace(...) when
    # portal.routes.init_app() imports each module.
    app.register_blueprint(v1)
    app.logger.info('Initialized API namespaces')
