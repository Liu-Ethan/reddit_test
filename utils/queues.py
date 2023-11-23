__all__ = ["MessageQueue", "declare_queues"]

from utils import tup


class Queues(dict):
    """队列容器"""

    def __init__(self, queues):
        dict.__init__(self)
        self.__dict__ = self
        self.bindings = set()
        self.declare(queues)

    def __iter__(self):
        for name, queue in self.items():
            if name != "bindings":
                yield queue

    def declare(self, queues):
        for name, queue in queues.items():
            queue.name = name
            queue.bindings = self.bindings
            if queue.bind_to_self:
                queue._bind(name)
        self.update(queues)


class MessageQueue(object):
    """AMQP消息队列的表示

    该类仅用于上面的Queues类。

    """

    def __init__(self, durable=True, exclusive=False,
                 auto_delete=False, bind_to_self=False):
        self.durable = durable  # 持久的
        self.exclusive = exclusive  # 排他性
        self.auto_delete = auto_delete  # 自动删除
        self.bind_to_self = bind_to_self  # 绑定到自身

    def _bind(self, routing_key):
        # print(f"ssss, {self},{self.name}", self.bindings)
        self.bindings.add((self.name, routing_key))

    def __lshift__(self, routing_keys):
        """从路由键注册到该队列的绑定
        << 运算符实际上调用了__lshift__,方法，这个方法接受一个或多个路由键，并将它们添加到队列的绑定中，以便队列可以接收来自这些路由键的消息。
        """
        routing_keys = tup(routing_keys)
        print(routing_keys)
        for routing_key in routing_keys:
            self._bind(routing_key)


def declare_queues():
    queues = Queues({
        "vote_comment_q": MessageQueue(bind_to_self=True),
        "newcomments_q": MessageQueue()
    })

    # if g.shard_commentstree_queues:
    #     sharded_commentstree_queues = {"commentstree_%d_q" % i:
    #                                        MessageQueue(bind_to_self=True)
    #                                    for i in range(10)}
    #     queues.declare(sharded_commentstree_queues)

    # 然后通过 << 过载操作符将路由键注册到队列的绑定中
    # queues.vote_comment_q << ("vote_comment_q_test",)
    queues.vote_comment_q << "vote_comment_q_test"
    queues.newcomments_q << ("new_link", "link_text_edited")

    return queues


queues = declare_queues()
print(queues.bindings)
