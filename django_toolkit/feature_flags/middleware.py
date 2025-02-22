from .flags import db_get_or_create


def feature_flags_cache_clear_middleware(get_response):
    """Clear retrieved feature-flag cache on per-request bases to avoid db spam.

    Given that the same feature flag might be invoked multiple times in the same
    request, we avoid db spam by clearing lru cache on flag retrieval.
    """

    def middleware(request):
        db_get_or_create.cache_clear()
        return get_response(request)

    return middleware
