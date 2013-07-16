import collections

# Is this needed - can dict be used?
class DictProxy(collections.MutableMapping):
    def __init__(self, *args, **kwargs):
        self.__dict = {}
        super(DictProxy, self).__init__(*args, **kwargs)

    def __getitem__(self, key):
        return self.__dict[key]

    def __setitem__(self, key, value):
        self.__dict[key] = value

    def __delitem__(self, key):
        del(self.__dict[key])

    def __iter__(self):
        return self.__dict.__iter__()

    def __len__(self):
        return self.__dict.__len__()

    def keys(self):
        return self.__dict.keys()
