from app.handlers.user.games import build_games_handlers
from app.handlers.user.predict import build_predict_handlers
from app.handlers.user.start import build_start_handler
from app.handlers.user.stats import build_stats_handlers


#
# User handlers composition
#
def build_user_handlers(service, is_open_signup):
    start_handlers = build_start_handler(service, is_open_signup)
    games_handlers = build_games_handlers(service)
    predict_handlers = build_predict_handlers(service)
    stats_handlers = build_stats_handlers(service)

    return {
        **start_handlers,
        **games_handlers,
        **predict_handlers,
        **stats_handlers,
    }
