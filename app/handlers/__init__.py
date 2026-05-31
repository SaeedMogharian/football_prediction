from app.handlers.admin import build_admin_handlers
from app.handlers.common import build_unknown_handler
from app.handlers.user import build_user_handlers


def build_handlers(cursor, connection, admins, is_open):
    common_handlers = build_unknown_handler()
    user_handlers = build_user_handlers(cursor, connection, is_open)
    admin_handlers = build_admin_handlers(cursor, connection, admins, common_handlers["unknown"])

    return {
        **user_handlers,
        **admin_handlers,
        **common_handlers,
    }
