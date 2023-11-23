# The contents of this file are subject to the Common Public Attribution
# License Version 1.0. (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://code.reddit.com/LICENSE. The License is based on the Mozilla Public
# License Version 1.1, but Sections 14 and 15 have been added to cover use of
# software over a computer network and provide for limited attribution for the
# Original Developer. In addition, Exhibit A has been modified to be consistent
# with Exhibit B.
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
# the specific language governing rights and limitations under the License.
#
# The Original Code is reddit.
#
# The Original Developer is the Initial Developer.  The Initial Developer of
# the Original Code is reddit Inc.
#
# All portions of the code written by reddit are Copyright (c) 2006-2015 reddit
# Inc. All Rights Reserved.
###############################################################################
"""A very simple system for event hooks for plugins etc.

In general, you will probably want to use a ``HookRegistrar`` to manage your
hooks.  The file that contains the code you want to hook into will look
something like this::

    from r2.lib import hooks
    
    def foo(spam):
        # Do a little bit of this and a little bit of that.
        eggs = this(spam)
        baked_beans = that(eggs)
    
        hooks.get_hook('foo').call(ingredient=baked_beans)

Then, any place you want to hook into it, just throw on a decorator::

    from r2.lib.hooks import HookRegistrar
    hooks = HookRegistrar()
    
    @hooks.on('foo')
    def bar(ingredient):
        print ingredient

    hooks.register_all()


    这段代码看起来是一个简单的钩子（Hook）和钩子注册器（HookRegistrar）系统的实现。它的作用是提供一种机制，让代码中的特定事件可以被监听（hooked），并允许在特定事件发生时执行一些事先注册好的处理器（handlers）。

让我来分析这个代码的主要部分：

- `_HOOKS` 是一个全局变量，用于存储所有已注册的 hooks。
- `all_hooks()` 函数返回所有已注册的 hooks。
- `Hook` 类代表一个单独的 hook，它包含了一系列处理器（handlers）。
- `register_handler()` 方法用于向 hook 注册一个处理器。
- `call()` 方法用于调用所有已注册的处理器，并返回它们的结果。
- `call_until_return()` 方法与 `call()` 类似，但不同之处在于只要有一个处理器返回非空值就会立即返回。
- `get_hook(name)` 函数用于获取一个名为 `name` 的 hook，如果不存在则创建一个新的。
- `HookRegistrar` 类用于延迟模块级别的 hook 注册。它提供了 `on()` 方法作为装饰器，用于将函数注册为处理器。`register_all()` 方法用于完成所有延迟注册的处理器。

这段代码的设计目的是让开发者能够轻松地注册和调用钩子。通过 `HookRegistrar` 类提供的 `on()` 方法，可以在代码中指定特定事件的处理函数。稍后调用 `register_all()` 方法时，所有已注册的处理函数会被挂钩并与相应的 hook 关联起来，从而实现钩子的功能。
"""

_HOOKS = {}


def all_hooks():
    """Return all registered hooks."""
    return _HOOKS


class Hook(object):
    """A single hook that can be listened for."""

    def __init__(self):
        self.handlers = []

    def register_handler(self, handler):
        """Register a handler to call from this hook."""
        self.handlers.append(handler)

    def call(self, **kwargs):
        """Call handlers and return their results.

        Handlers will be called in the same order they were registered and
        their results will be returned in the same order as well.

        """
        return [handler(**kwargs) for handler in self.handlers]

    def call_until_return(self, **kwargs):
        """Call handlers until one returns a non-None value.

        As with call, handlers are called in the same order they are
        registered.  Only the return value of the first non-None handler is
        returned.

        """
        for handler in self.handlers:
            ret = handler(**kwargs)
            if ret is not None:
                return ret


def get_hook(name):
    """Return the named hook `name` creating it if necessary."""
    # this should be atomic as long as `name`'s __hash__ isn't python code
    # or for all types after the fixes in python#13521 are merged into 2.7.
    return _HOOKS.setdefault(name, Hook())


class HookRegistrar(object):
    """A registry for deferring module-scope hook registrations.

    This registry allows us to use module-level decorators but not actually
    register with global hooks unless we're told to.

    """

    def __init__(self):
        self.registered = False
        self.connections = []

    def on(self, name):
        """Return a decorator that registers the wrapped function."""

        hook = get_hook(name)

        def hook_decorator(fn):
            if self.registered:
                hook.register_handler(fn)
            else:
                self.connections.append((hook, fn))
            return fn

        return hook_decorator

    def register_all(self):
        """Complete all deferred registrations."""
        for hook, handler in self.connections:
            hook.register_handler(handler)
        self.registered = True


if __name__ == '__main__':
    # 创建一个钩子注册器实例
    hook_registrar = HookRegistrar()


    # 使用装饰器注册一个钩子（on_login），并定义处理函数
    @hook_registrar.on('on_login')
    def on_user_login(username):
        print(f"User {username} logged in.")


    # 在适当的地方，注册所有的延迟处理函数
    hook_registrar.register_all()

    print(all_hooks())


    # 模拟用户登录
    def simulate_login(username):
        hook = get_hook('on_login')
        hook.call(username=username)


    # 模拟用户登录
    simulate_login('Alice')
    simulate_login('Bob')
