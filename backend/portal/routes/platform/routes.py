"""Public platform settings (maintenance banner, support hours). No auth:
only rows flagged is_public are ever returned."""

from flask_restx import Resource

from portal.helpers.responses import ok
from portal.helpers.settings import cast
from portal.models.admin_settings import AdminSettings

from . import ns


@ns.route('/settings')
class PublicSettings(Resource):
    def get(self):
        rows = AdminSettings.query.filter_by(is_public=True).all()
        return ok({r.key: cast(r.value, r.value_type) for r in rows})
