from .flags import retrieve_feature_flag_from_db


def feature_flags_cache_clear_middleware(get_response):
    """Clear retrieved feature-flag cache on per-request bases to avoid db spam.

    Given that the same feature flag might be invoked multiple times in the same
    request, we avoid db spam by clearing lru cache on flag retrieval.
    """

    def middleware(request):
        retrieve_feature_flag_from_db.cache_clear()
        return get_response(request)

    return middleware
