# -*- coding: utf-8 -*-
# @Time    : 2023/11/21 10:24
# @Comment :
def tup(item, ret_is_single=False):
    """将item强制转换为元组（用于列表）或生成单元素元组（用于其他类型）"""
    # 返回可迭代对象，但排除字符串（字符串是我们想要的）
    if isinstance(item, str):  # 处理字符串情况
        return (item,)
    if hasattr(item, '__iter__'):
        return (item, False) if ret_is_single else item
    else:
        return ((item,), True) if ret_is_single else (item,)
