# export 装饰器接受一个函数或类作为参数，并用于将这个函数或类的名称添加到模块的__all__变量中。这样做的目的是告诉Python模块的用户哪些内容应该被认为是公共的，可以从模块中导入。
#
# 在使用@export装饰器时，如果被装饰的函数或类的名称不在__all__变量中，它将被添加到__all__中。这确保了被装饰的函数或类在使用from module import *时可见。
# `from module import some_function, SomeClass` 和使用 `@export` 装饰器声明 `__all__` 的区别在于可见性和维护性。
#
# 1. **可见性**:
#    - `from module import some_function, SomeClass`：这种方式可以选择性地导入模块中的特定函数和类，但需要明确列出要导入的名称。只有被列出的名称才会被导入当前模块的命名空间，其他名称不可见。
#    - 使用 `@export` 装饰器和 `__all__`：这种方式在模块中明确指定哪些内容应该被导出，即哪些内容可以被其他模块导入。如果在 `__all__` 中列出了名称，这些名称可以通过 `from module import *` 导入，而不需要显式指定每个名称。这增加了模块级别的可见性，使代码更加整洁。
#
# 2. **维护性**:
#    - `from module import some_function, SomeClass`：如果模块中新增了函数或类，需要手动更新导入语句，以便导入新的内容。
#    - 使用 `@export` 装饰器和 `__all__`：如果模块中新增了函数或类，只需在模块内部使用 `@export` 装饰器来修饰新的函数或类，而不需要修改其他模块中的导入语句。这样提高了代码的可维护性，减少了出错的可能性。
#
# 总之，`@export` 装饰器和 `__all__` 变量的组合提供了一种更具可维护性和清晰性的方式来管理模块的导出内容。这使得代码更易读，更容易维护，并且在新增内容时能够更好地保持一致性。
"""
__all__ = []  # 初始化 __all__ 列表

@export
def some_function():
    return "Hello, World!"

@export
class SomeClass:
    def __init__(self, value):
        self.value = value

"""
###############################################################################

import sys

__all__ = ["export", "ExportError"]


class ExportError(Exception):
    def __init__(self, module):
        msg = "Missing __all__ declaration in module %s.  " \
              "@export cannot be used without declaring __all__ " \
              "in that module." % (module)
        Exception.__init__(self, msg)


def export(exported_entity):
    """Use a decorator to avoid retyping function/class names.
  
    * Based on an idea by Duncan Booth:
    http://groups.google.com/group/comp.lang.python/msg/11cbb03e09611b8a
    * Improved via a suggestion by Dave Angel:
    http://groups.google.com/group/comp.lang.python/msg/3d400fb22d8a42e1
    * Copied from Stack Overflow
    http://stackoverflow.com/questions/6206089/is-it-a-good-practice-to-add-names-to-all-using-a-decorator
    """
    all_var = sys.modules[exported_entity.__module__].__dict__.get('__all__')
    if all_var is None:
        raise ExportError(exported_entity.__module__)
    if exported_entity.__name__ not in all_var:  # Prevent duplicates if run from an IDE.
        all_var.append(exported_entity.__name__)
    return exported_entity


export(export)  # Emulate decorating ourself
