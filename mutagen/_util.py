from fnmatch import fnmatchcase

def dict_match(d, key, default=None):
    try:
        return d[key]
    except KeyError:
        for pattern, value in d.iteritems():
            if fnmatchcase(key, pattern):
                return value
    return default
