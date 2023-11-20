import pickle
import socket
import time
import uuid
from queue import Queue
from threading import local, Thread

import pika
import pika.exceptions

from utils.queues import declare_queues


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


class Worker:
    def __init__(self):
        self.q = Queue()
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


class ConnectionManager(local):
    """应该只有两个线程与 AMQP 通信：工作线程和前台线程（无论是使用队列项还是 shell）。 这个类只是一个包装器，以确保它们获得单独的连接"""

    def __init__(self):
        self.connection = None
        self.channel = None
        self.have_init = False
        # self.queues = queues

    def get_connection(self):
        while not self.connection:
            try:
                self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
                # self.connection.channel().basic_publish()
            except (socket.error, IOError) as e:
                print('error connecting to amqp %s @ %s (%r)' %
                      (cfg.amqp_user, cfg.amqp_host, e))
                time.sleep(1)

        if not self.have_init:
            self.init_queue()
            self.have_init = True

        return self.connection

    def get_channel(self, reconnect=False):
        # Periodic (and increasing with uptime) errors appearing when
        # connection object is still present, but appears to have been
        # closed.  This checks that the the connection is still open.
        # if self.connection and self.connection.channels is None:
        #     print("Error: amqp.py, connection object with no available channels.")
        #     self.connection = None

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


DELIVERY_TRANSIENT = 1
DELIVERY_DURABLE = 2


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

    def on_return(*args, **kwargs):
        print("Message1111 returned!", args, kwargs)

    # 设置回调函数
    chan.add_on_return_callback(on_return)
    # 启用生产者确认模式
    chan.confirm_delivery()
    try:
        chan.basic_publish(exchange=exchange,
                           routing_key=routing_key,
                           body=body, properties=properties, mandatory=True)
    except pika.exceptions.UnroutableError:
        # 开启用生产者确认模式：chan.confirm_delivery()
        # 设置：mandatory=True ，设置为 True，
        # 当无法将消息路由到队列时，会触发pika.exceptions.UnroutableError异常
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
    # 是一个阻塞调用，它会持续从队列中接收消息并调用指定的回调函数进行处理，直到程序手动停止或出现错误
    chan.start_consuming()


def empty_queue(queue):
    """清空指定队列中的所有消息"""
    chan = connection_manager.get_channel()
    chan.queue_purge(queue)


def black_hole(queue):
    """将一个队列中的消息不断地清空"""

    def _ignore(msg):
        print('Ignoring msg: %r' % msg.body)

    consume_items(queue, _ignore)


def add_kw(routing_key, **kw):
    """允许您以结构化的方式传递数据"""
    add_item(routing_key, pickle.dumps(kw))


def dedup_queue(queue, rk=None, limit=100 * 1000,
                delivery_mode=DELIVERY_DURABLE):
    """尝试通过删除队列中的重复消息来减小队列的大小
    rk:  重新投递到队列的名称
    delivery_mode: 交付模式，默认为 DELIVERY_DURABLE。
    """
    chan = connection_manager.get_channel()

    if rk is None:
        rk = queue

    bodies = set()

    while True:
        method, properties, body = chan.basic_get(queue)
        if body is None:
            break

        if body not in bodies:
            bodies.add(body)
        limit -= 1
        if limit <= 0:
            break
        elif limit % 1000 == 0:
            print(limit)

    print("Grabbed %d unique bodies" % (len(bodies),))

    if bodies:
        for body in bodies:
            _add_item(rk, body, delivery_mode=delivery_mode)

        worker.join()

        chan.basic_ack(0, multiple=True)


config_data = {
    'amqp_host': 'localhost:5672',
    'amqp_user': 'reddit',
    'amqp_pass': 'reddit',
    'amqp_virtual_host': ' /',
    'amqp_logging': 'false',
    'shard_commentstree_queues': 'false',
    'queues': declare_queues()
}

worker = Worker()
cfg = Config(config_data)
connection_manager = ConnectionManager()

# connection_manager.get_connection()

# worker.join()  # 阻塞当前线程

for i in range(10):
    add_item('vote_comment_q', f"message_000{i}", message_id=str(uuid.uuid4()))


#
# for i in range(100):
#     add_item('vote_comment_q', f"message_000{i}")


def _run_changed(*args, **kwargs):
    print("_run_changed:", args, kwargs)
    pass


#
#
queue = 'vote_comment_q'
# # # 单个消费
consume_items(queue, _run_changed)

# 批量消费
# handle_items(queue, _run_changed, min_size=2,
#              limit=10, drain=False, sleep_time=2)

# empty_queue(queue)

# dedup_queue(queue)
