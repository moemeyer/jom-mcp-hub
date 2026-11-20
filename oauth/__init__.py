def __getattr__(name: str):
    if name == "OAuthProvider":
        from .oauth_provider import OAuthProvider

        return OAuthProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["OAuthProvider"]