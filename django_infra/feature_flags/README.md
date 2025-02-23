# Database managed FeatureFlags

## App features:

### Registering flags:
In `settings.py` or any other non-db scoped file:
```
from django_infra.feature_flags.flags import flags, register_feature_flag
# default to be used if os.env does not specify var.
flags.MY_FLAG = register_feature_flag('MY_FLAG',default=True)
```
The string passed in registration is both the environment variable name to be loaded
and the pk of the flag to be loaded into the database.

`flags.MY_FLAG` is now the instance of the model when called, so ensure
database access is present.

### Examples of use:

`bool(flags.MY_FLAG) == flags.MY_FLAG.active`

```
# Conditional logic
if flags.MY_FLAG: # <- Initial use retrieves from db & caches until next request.
    print("active")

# Update active/inactivex
flags.MY_FLAG.update(active=False) # <- updates db & pops cache
assert not flags.MY_FLAG


# Optional QOL/ quick testing (don't rely on this pattern unless you know exactly why you need it).
if FeatureFlags.TEST_CUSTOM_PARSER:
    return parse_content(content,FeatureFlags.TEST_CUSTOM_PARSER.value_str)
```

```
# Curl feature-flags:
[
  {
    "id": "DEFAULT_FLAG",
    "active": true,
    "value": 0,
    "valueStr": "v1.0"
  }
]
```

## Integration:

To ensure proper operation & minimal database load on retrieving feature flags:

### Register application & CRUD.

**INSTALLED_APPS** [ required ]: `django_infra.feature_flags`

**MIDDLEWARE** [ required ]:
```django_infra.feature_flags.middleware.feature_flags_cache_clear_middleware```


**urls.py** [ optional ]: (for client-access of flags & admin management):

`path("feature-flags/", include("django_infra.feature_flags.urls")),`


**TESTING:** Add the following fixture to ensure cache is cleared per test:

**pytest:**
```
@pytest.fixture(scope="function", autouse=True)
def clear_lru_caches():
    retrieve_feature_flag_from_db.cache_clear()
```

**other:** Not supported, just make sure cache is cleared on a per-test basis.
