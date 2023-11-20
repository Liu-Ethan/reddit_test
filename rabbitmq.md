### `MessageQueue`

定义了代表AMQP消息队列的类。它有一些属性（如持久性、排他性等)

```python
def tup(item, ret_is_single=False):
    """根据输入的类型，将其转换为元组形式。"""
    if hasattr(item, '__iter__'):
        return (item, False) if ret_is_single else item
    else:
        return ((item,), True) if ret_is_single else (item,)


class MessageQueue(object):
    """AMQP消息队列的表示"""

    def __init__(self, durable=True, exclusive=False,
                 auto_delete=False, bind_to_self=False):
        self.durable = durable  # 持久的
        self.exclusive = exclusive  # 排他性
        self.auto_delete = auto_delete  # 自动删除
        self.bind_to_self = bind_to_self  # 设置：路由key与当前消息队列的名称一样

    def _bind(self, routing_key):
        # bindings属性，通过Queues的declare方式定义，使所有的消息队列的bindings属性都指向同一块内存
        self.bindings.add((self.name, routing_key))

    def __lshift__(self, routing_keys):
        """通过<<，实现将路由键绑定到该队列"""
        routing_keys = tup(routing_keys)
        for routing_key in routing_keys:
            self._bind(routing_key)

```

- `tup(item, ret_is_single=False)`:
  这个函数的作用是根据输入的类型，将其转换为元组形式。如果输入是可迭代对象但不是字符串，则将其转换为元组；如果输入不是可迭代对象，则将其封装成单元素元组。第二个参数ret_is_single用来指示是否返回单元素元组。这个函数可以处理单个元素和多个元素的情况。
- `__lshift__`: 方法定义了类的实例对象,在被 `<<`
  运算符调用时的行为。用于向队列对象添加绑定的路由键,这个方法接受一个或多个路由键，并将它们添加到队列的绑定中，以便队列可以接收来自这些路由键的消息。

### `Queues`

继承自字典，定义一个队列容器，用于管理队列。

```python
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
            queue.bindings = self.bindings  # 所有消息队列的bindings都指向同一个内存
            if queue.bind_to_self:
                queue._bind(name)
        self.update(queues)
```

- `declare`: 方法用来声明队列，将队列加入到队列容器中。

### `declare_queues()`

创建了Queues对象并声明了一些队列。它使用MessageQueue类创建了一些特定的队列，然后将一些路由键注册到这些队列的绑定中。

```python
def declare_queues():
    queues = Queues({
        "vote_comment_q": MessageQueue(bind_to_self=True),
        "newcomments_q": MessageQueue()
    })

    # 然后通过 << 过载操作符将路由键注册到队列的绑定中
    queues.vote_comment_q << ("vote_comment_q_test",)
    queues.newcomments_q << ("new_link", "link_text_edited")

    return queues
```

```shell
queues = declare_queues()
print(queues)
# 自绑定的结果：('vote_comment_q', 'vote_comment_q')
{'bindings': {('newcomments_q', 'new_link'), ('vote_comment_q', 'vote_comment_q_test'), 
('vote_comment_q', 'vote_comment_q'), ('newcomments_q', 'link_text_edited')}, 
'vote_comment_q': <__main__.MessageQueue object at 0x000002DEA12F8BE0>, 
'newcomments_q': <__main__.MessageQueue object at 0x000002DEA15AE2E0>}

```

### `Worker`

这个类创建了一个工作线程，该线程通过一个队列接收任务并执行。使用 `do` 方法可以向队列中添加任务，而 `join`
方法则可以阻塞主线程，直到队列中的任务都被执行完毕。这种设计可以用于异步执行任务，将需要在后台处理的工作放入队列，然后由单独的线程来执行。

```python
from queue import Queue


class Worker:
    def __init__(self):
        self.q = Queue()  # 初始化了一个队列 
        self.t = Thread(target=self._handle)
        # self.t.setDaemon(True) # 设置为守护线程后，当主线程退出时，守护线程也会立即结束，不管是否执行完成
        self.t.start()

    def _handle(self):
        while True:
            fn = self.q.get()
            try:
                fn()
                self.q.task_done()
            except Exception as e:
                import traceback
                traceback.format_exc()
                raise e

    def do(self, fn, *a, **kw):
        fn1 = lambda: fn(*a, **kw)
        self.q.put(fn1)

    def join(self):
        self.q.join()
```

1. `__init__(self)`: 初始化了一个队列 `self.q` 和一个线程 `self.t`
   ，并且通过调用 `self.t.start()` 启动了一个线程，这个线程执行 `_handle` 方法。

2. `_handle(self)`: 这是一个私有方法，是线程实际执行的内容。它是一个无限循环，不断从队列 `self.q`
   中获取函数并执行，直到程序被终止或队列停止接收任务。每次获取一个函数，执行该函数，然后标记队列中的任务为已完成。

3. `do(self, fn, *a, **kw)`: 这个方法用于向队列中添加任务。它接受一个函数 `fn`
   和该函数所需的参数和关键字参数。在内部，它创建一个新的函数 `fn1`，这个函数在被调用时会执行传入的函数 `fn`
   ，并将传入的参数和关键字参数传递给它。然后，它将这个新的函数 `fn1` 放入队列 `self.q` 中等待执行。

4. `join(self)`: 这个方法用于等待队列中的所有任务执行完毕。它调用队列的 `join()` 方法，将会阻塞直到队列中所有的任务都被处理完。

### `Config`

一个简单的配置类，用于`ConnectionManager `类的配置信息来建立与 AMQP 的连接并初始化队列。

```python
class Config(object):
    def __init__(self, g):
        self.amqp_host = g['amqp_host']
        self.amqp_user = g['amqp_user']
        self.amqp_pass = g['amqp_pass']
        self.amqp_exchange = 'reddit_exchange'
        # self.log = g.log
        self.amqp_virtual_host = g['amqp_virtual_host']
        self.amqp_logging = g['amqp_logging']
        # self.stats = g.stats
        self.queues = g["queues"]

```

### `ConnectionManager `

它继承自 `local`, 用于创建线程本地数据，使每个线程都有其自己的数据副本，避免多线程环境中的数据混乱问题。`ConnectionManager`
类的作用是管理与 AMQP（高级消息队列协议）的连接和通信。

```python
from threading import local


class ConnectionManager(local):
    """应该只有两个线程与 AMQP 通信：工作线程和前台线程（无论是使用队列项还是 shell）。 这个类只是一个包装器，以确保它们获得单独的连接"""

    def __init__(self):
        self.connection = None
        self.channel = None
        self.have_init = False

    def get_connection(self):
        while not self.connection:
            try:
                self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
            except (socket.error, IOError) as e:
                print('error connecting to amqp %s @ %s (%r)' %
                      (cfg.amqp_user, cfg.amqp_host, e))
                time.sleep(1)

        if not self.have_init:
            self.init_queue()
            self.have_init = True

        return self.connection

    def get_channel(self, reconnect=False):
        if self.connection and self.connection.channels is None:
            print("Error: amqp.py, connection object with no available channels.")
            self.connection = None

        if not self.connection or reconnect:
            self.connection = None
            self.channel = None
            self.get_connection()

        if not self.channel:
            self.channel = self.connection.channel()

        return self.channel

    def init_queue(self):
        chan = self.get_channel()
        # 声明交换机
        chan.exchange_declare(exchange="reddit_exchange",
                              exchange_type="direct",
                              durable=True,
                              auto_delete=False)
        # 声明队列
        for queue in cfg.queues:
            chan.queue_declare(queue=queue.name,
                               durable=queue.durable,
                               exclusive=queue.exclusive,
                               auto_delete=queue.auto_delete)

        # 队列与交换机,通过binding进行绑定
        for queue, key in cfg.queues.bindings:
            chan.queue_bind(routing_key=key,
                            queue=queue,
                            exchange="reddit_exchange")

```

1. `__init__(self)`: 初始化方法，设置了连接和通道等属性。`connection` 和 `channel` 分别表示 AMQP 的连接和通道。`have_init`
   用来标记是否已经初始化过队列。

2. `get_connection(self)`: 获取与 AMQP 的连接。该方法使用 `pika.BlockingConnection` 建立与 AMQP
   服务器的连接。如果连接失败，它会间隔一秒钟重试，直到连接成功。一旦连接成功，它会调用 `init_queue()`
   方法初始化队列，并标记 `have_init` 为 True，表示已经初始化过队列。

3. `get_channel(self, reconnect=False)`: 获取 AMQP 的通道。如果 `reconnect(重新连接)` 被设置为
   True，或者当前没有连接或通道，它会重新获取连接并创建新的通道。如果连接存在但通道不存在，它会创建新的通道并返回。

4. `init_queue(self)`: 初始化 AMQP 的队列。该方法使用已获取的通道进行交换机、队列和绑定的声明。它使用配置文件中的信息来声明交换机、队列，并使用绑定将队列与交换机进行关联。

### `add_item`

用于发布消息到 AMQP 中，在一个异步的环境下执行。它们允许设置消息的一些属性，并最终将消息发布到指定的交换机和路由键上。

```python
DELIVERY_TRANSIENT = 1
DELIVERY_DURABLE = 2
import pika.exceptions


def _add_item(routing_key, body, message_id=None,
              delivery_mode=DELIVERY_DURABLE, headers=None,
              exchange=None, send_stats=True):
    if not exchange:
        exchange = cfg.amqp_exchange

    chan = connection_manager.get_channel()

    properties = pika.BasicProperties(  # 设置消息的基本属性, 。这些属性包括消息的持久性、消息的优先级、消息的时间戳、消息的类型和其他元数据。
        message_id=message_id,
        # 设置消息的有效期为 10 秒
        # expiration='10000'
    )
    print(body)

    # def on_return(*args, **kwargs):
    #     print("Message returned!", args, kwargs)
    # 设置回调函数, 此方式
    # chan.add_on_return_callback(on_return)
    # 启用生产者确认模式
    chan.confirm_delivery()

    try:
        chan.basic_publish(exchange=exchange,
                           routing_key=routing_key,  # invalid_routing_key
                           body=body, properties=properties, mandatory=True)
    except pika.exceptions.UnroutableError:
        # 开启用生产者确认模式：chan.confirm_delivery()
        # 设置：mandatory=True ，设置为 True，
        # 当无法将消息路由到队列时（设置无效的路由key），会触发pika.exceptions.UnroutableError异常
        print('Message was returned')


def add_item(routing_key, body, message_id=None,
             delivery_mode=DELIVERY_DURABLE, headers=None,
             exchange=None, send_stats=True):
    """发布消息"""

    if exchange is None:  # 交换机
        exchange = cfg.amqp_exchange

    worker.do(_add_item, routing_key, body, message_id=message_id,
              delivery_mode=delivery_mode, headers=headers, exchange=exchange,
              send_stats=send_stats)

```

- `add_item`: 这个函数是一个对外的接口函数，用于发布消息。它调用了 `_add_item` 函数，但使用了一个名为 `worker`
  的对象的 `do` 方法。这里可能是一个异步的设计，`worker.do()` 可能是将 `_add_item`
  函数异步地放入队列中执行。它接受与 `_add_item` 函数相同的参数，并传递给 `worker.do()` 方法。
-
- `_add_item`: 这个函数实际上是执行发布消息的核心功能。它接受一些参数，包括 `routing_key`（路由键）、`body`
  （消息体）、`message_id`（消息ID）、`delivery_mode`（传送模式）、`headers`（消息头部信息）、`exchange`
  （交换机）等。在函数内部，它首先检查传入的 `exchange` 是否为 None，如果是的话，则使用全局配置 `cfg.amqp_exchange`
  的值。然后，它获取一个通道（channel）`chan`，然后使用 `pika` 库的 `chan.basic_publish` 方法发布消息到指定的交换机和路由键上。

- `pika.exceptions.UnroutableError`: 开启用生产者确认模式：`chan.confirm_delivery()`,
  并设置：`basic_publish(..., mandatory=True)`
  ,当无法将消息路由到队列时（设置无效的路由key），会触发`pika.exceptions.UnroutableError`异常

### `consume_items`: 消费消息

```python
def consume_items(queue, callback, verbose=True):
    """
    消费者函数，用于消费队列中的消息
    :param queue: 要消费的队列的名称
    :param callback: 处理每条消息的回调函数
    """
    chan = connection_manager.get_channel()

    # configure the amount of data rabbit will send down to our buffer before
    # we're ready for it (to reduce network latency). by default, it will send
    # as much as our buffers will allow.
    chan.basic_qos(
        # 预取窗口的大小，通常设置为0表示不限制消息的大小
        prefetch_size=0,
        # 最大预取消息数量，表示一次从队列中获取的消息数量。
        prefetch_count=1000,
        # 一个布尔值，表示是否将配置应用于所有通道，通常为 False，只应用于当前通道。
        global_qos=False
    )

    def _callback(ch, method, properties, body):
        print('_callback:', body, method, properties.__dict__, )

        ret = callback(body)
        if body.decode('utf-8') == 'message_0005':
            # 手动拒绝消息
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=True)
            """
            delivery_tag: 表示要拒绝的消息的唯一标识符
            requeue=True: 表示是否将拒绝的消息重新放回队列, 如果设置为 False，消息将被丢弃, 如果设置为 True，拒绝的消息将重新进入队列，可以被其他消费者重新处理；
            """
        else:
            # 手动确认消息
            ch.basic_ack(delivery_tag=method.delivery_tag)
        return ret

    # 轮询队列以获取新消息
    chan.basic_consume(queue=queue, on_message_callback=_callback, auto_ack=False)
    # chan.basic_consume(queue=queue, on_message_callback=_callback, auto_ack=True) # 自动确认
    # 是一个阻塞调用，它会持续从队列中接收消息并调用指定的回调函数进行处理，直到程序手动停止或出现错误
    chan.start_consuming()


def _run_changed(*args, **kwargs):
    print("_run_changed:", args, kwargs)
    pass


queue = 'vote_comment_q'
# 单个消费
consume_items(queue, _run_changed)
```

### `handle_items`

```python
def handle_items(queue, callback, ack=True, limit=1, min_size=0,
                 drain=False, sleep_time=1):
    """对特定队列中的每个项目调用callback()。
     handle_items 函数：处理队列中的消息，与 consume_items 不同，它可以一次处理多个消息。可以设置处理的消息数量、最小大小、是否要在处理之后确认消息等"""
    if limit < min_size:
        raise ValueError("min_size must be less than limit")

    chan = connection_manager.get_channel()

    while True:

        msg = chan.basic_get(queue)  # 允许消费者主动从队列中获取一条消息
        if not msg and drain:
            return
        elif not msg:
            time.sleep(sleep_time)
            continue

        items = [msg]

        while len(items) < limit:
            msg = chan.basic_get(queue)
            if msg is None:
                if len(items) < min_size:
                    time.sleep(sleep_time)
                else:
                    break
            else:
                items.append(msg)
        print('handle_items', len(items), items)
        try:
            callback(items, chan)

            if ack:
                # ack *all* outstanding messages
                chan.basic_ack(0, multiple=True)
                """
                用于确认消息的接收
                delivery_tag：表示要确认的消息的交付标签（delivery tag），交付标签是由 RabbitMQ 分配的唯一标识，它标识了要确认的消息。
                multiple：一个布尔值，用于指定是确认单个消息还是多个消息
                如果 multiple 为 False，那么只确认指定交付标签（delivery_tag）的消息。
                如果 multiple 为 True，并且 delivery_tag 为 0，则表示确认所有已接收但未确认的消息。
                如果 multiple 为 True，并且 delivery_tag 不为 0，则表示确认包括 delivery_tag 在内的所有消息，从 0 到 delivery_tag 之间的所有消息都会被确认。
                """
        except:
            for msg in items:
                # explicitly reject the items that we've not processed
                chan.basic_reject(msg[1].delivery_tag, requeue=True)
                """拒绝消息的接收
                requeue：一个布尔值，用于指定是否将消息重新放入队列。
                """
            raise
```