def init_app():
    from .authentication import routes  # noqa: F401
    from .security import routes        # noqa: F401
    from .account import routes         # noqa: F401
    from .notifications import routes   # noqa: F401
    from .cards import routes           # noqa: F401
    from .bills import routes           # noqa: F401
    from .scan import routes            # noqa: F401
    from .tickets import routes         # noqa: F401
    from .support import routes         # noqa: F401
    from .admin import routes           # noqa: F401
    from .platform import routes        # noqa: F401
