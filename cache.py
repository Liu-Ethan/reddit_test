from utils._utils import prefix_keys
class CacheUtils(object):
    # Caches that never expire entries should set this to true, so that
    # CacheChain can properly count hits and misses.
    permanent = False

    def incr_multi(self, keys, delta=1, prefix=''):
        for k in keys:
            try:
                self.incr(prefix + k, delta)
            except ValueError:
                pass

    def add_multi(self, keys, prefix='', time=0):
        for k,v in keys.iteritems():
            self.add(prefix+str(k), v, time = time)

    def get_multi(self, keys, prefix='', **kw):
        return prefix_keys(keys, prefix, lambda k: self.simple_get_multi(k, **kw))



class HardCache(CacheUtils):
    backend = None
    permanent = True

    def __init__(self, gc):
        self.backend = HardCacheBackend(gc)

    def _split_key(self, key):
        tokens = key.split("-", 1)
        if len(tokens) != 2:
            raise ValueError("key %s has no dash" % key)

        category, ids = tokens
        return category, ids

    def set(self, key, val, time=0):
        if val == NoneResult:
            # NoneResult caching is for other parts of the chain
            return

        category, ids = self._split_key(key)
        self.backend.set(category, ids, val, time)

    def simple_get_multi(self, keys):
        results = {}
        category_bundles = {}
        for key in keys:
            category, ids = self._split_key(key)
            category_bundles.setdefault(category, []).append(ids)

        for category in category_bundles:
            idses = category_bundles[category]
            chunks = in_chunks(idses, size=50)
            for chunk in chunks:
                new_results = self.backend.get_multi(category, chunk)
                results.update(new_results)

        return results

    def set_multi(self, keys, prefix='', time=0):
        for k,v in keys.iteritems():
            if v != NoneResult:
                self.set(prefix+str(k), v, time=time)

    def get(self, key, default=None):
        category, ids = self._split_key(key)
        r = self.backend.get(category, ids)
        if r is None: return default
        return r

    def delete(self, key, time=0):
        # Potential optimization: When on a negative-result caching chain,
        # shove NoneResult throughout the chain when a key is deleted.
        category, ids = self._split_key(key)
        self.backend.delete(category, ids)

    def add(self, key, value, time=0):
        category, ids = self._split_key(key)
        return self.backend.add(category, ids, value, time=time)

    def incr(self, key, delta=1, time=0):
        category, ids = self._split_key(key)
        return self.backend.incr(category, ids, delta=delta, time=time)



class LocalCache(dict, CacheUtils):
    def __init__(self, *a, **kw):
        return dict.__init__(self, *a, **kw)

    def _check_key(self, key):
        if not isinstance(key, str):
            raise TypeError('Key is not a string: %r' % (key,))

    def get(self, key, default=None):
        r = dict.get(self, key)
        if r is None: return default
        return r

    def simple_get_multi(self, keys):
        out = {}
        for k in keys:
            try:
                out[k] = self[k]
            except KeyError:
                pass
        print("out",out)
        return out

    def set(self, key, val, time = 0):
        # time is ignored on localcache
        self._check_key(key)
        self[key] = val

    def set_multi(self, keys, prefix='', time=0):
        for k,v in keys.iteritems():
            self.set(prefix+str(k), v, time=time)

    def add(self, key, val, time = 0):
        self._check_key(key)
        was = key in self
        self.setdefault(key, val)
        return not was

    def delete(self, key):
        if key in self:
            del self[key]

    def delete_multi(self, keys):
        for key in keys:
            if key in self:
                del self[key]

    def incr(self, key, delta=1, time=0):
        if key in self:
            self[key] = int(self[key]) + delta

    def decr(self, key, amt=1):
        if key in self:
            self[key] = int(self[key]) - amt

    def append(self, key, val, time = 0):
        if key in self:
            self[key] = str(self[key]) + val

    def prepend(self, key, val, time = 0):
        if key in self:
            self[key] = val + str(self[key])

    def replace(self, key, val, time = 0):
        if key in self:
            self[key] = val

    def flush_all(self):
        self.clear()

    def reset(self):
        self.clear()

    def __repr__(self):
        return "<LocalCache(%d)>" % (len(self),)


# 示例1：定义一个映射函数map_fn
def map_fn(key):
    return f"mapped_{key}"

# 示例2：定义一个处理函数call_fn
def call_fn(keys):
    return {key: key * 2 for key in keys}

# 示例3：定义一个键的列表
keys = [1, 2, 3, 4]

# 示例4：调用prefix_keys函数
result = prefix_keys(keys, "prefix_", call_fn)

print(call_fn(keys))
# 示例5：输出结果
print(result)
local_cache = LocalCache()
local_cache.update(a=12)
local_cache.update(b=13)
local_cache.incr("a")
local_cache.prepend("a", 14)
print(local_cache.simple_get_multi(("a", "b")))
print(local_cache["c"])

