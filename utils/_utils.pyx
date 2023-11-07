# 定义函数keymap，用于在get_multi之前对一组键进行映射，并将结果以原始未映射的键形式存储为字典
cpdef dict keymap(keys, callfn, mapfn = None, str prefix=''):
    cdef dict km = {}  # 存储键的映射字典
    cdef dict res  # 从callfn获取的结果字典
    cdef dict ret = {}  # 返回值字典

    km = map_keys(keys, mapfn, prefix)  # 对键进行映射操作
    res = callfn(km.keys())  # 调用callfn函数获取结果字典
    ret = unmap_keys(res, km)  # 对结果字典进行反映射操作
    print(km, res, ret)

    return ret

# 定义函数map_keys，用于对键进行映射操作，并返回映射后的键的字典
cdef map_keys(keys, mapfn, str prefix):
    if (mapfn and prefix) or (not mapfn and not prefix):
        raise ValueError("只能设置mapfn或prefix中的一个")

    cdef dict km = {}  # 存储键的映射字典
    print("xxxx", mapfn, prefix)
    if mapfn:
        for key in keys:
            km[mapfn(key)] = key
    else:
        for key in keys:
            km[prefix + str(key)] = key
    return km

# 定义函数unmap_keys，用于对映射后的键进行反映射操作，并返回反映射后的键值对字典
cdef unmap_keys(mapped_keys, km):
    cdef dict ret = {}  # 存储反映射后的键值对字典
    for key, value in mapped_keys.iteritems():
        ret[km[key]] = value
    return ret

# 定义函数prefix_keys，用于对键进行前缀操作，并调用keymap函数进行处理
def prefix_keys(keys, str prefix, callfn):
    if len(prefix):
        return keymap(keys, callfn, prefix=prefix)
    else:
        return callfn(keys)