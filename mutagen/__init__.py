

version = (1, 21)
version_string = u".".join(str(v) for v in version)

class Metadata(object):
    def __init__(self, *args, **kwargs):
        if args or kwargs:
            self.load(*args, **kwargs)

    def load(self, *args, **kwargs):
        raise NotImplementedError

    def save(self, filename = None):
        raise NotImplementedError

    def delete(self, filename = None):
        raise NotImplementedError
