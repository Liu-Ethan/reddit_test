# -*- coding: utf-8 -*-
# @Time    : 2023/11/20 13:54
# @Comment :
import collections
import functools
import os
import random
import socket
import threading
import time


class TimingStatBuffer:
    """Dictionary of keys to cumulative time+count values.

    This provides thread-safe accumulation of pairs of values. Iterating over
    instances of this class yields (key, (total_time, count)) tuples.
    """

    Timing = collections.namedtuple('Timing', ['key', 'start', 'end'])

    def __init__(self):
        # Store data internally as a map of keys to complex values. The real
        # part of the complex value is the total time (in seconds), and the
        # imaginary part is the total count.
        self.data = collections.defaultdict(complex)
        self.log = threading.local()

    def record(self, key, start, end, publish=True):
        if publish:
            # Add to the total time and total count with a single complex value,
            # so as to avoid inconsistency from a poorly timed context switch.
            self.data[key] += (end - start) + 1j

        if getattr(self.log, 'timings', None) is not None:
            self.log.timings.append(self.Timing(key, start, end))

    def flush(self):
        """Yields accumulated timing and counter data and resets the buffer."""
        data, self.data = self.data, collections.defaultdict(complex)
        while True:
            try:
                k, v = data.popitem()
            except KeyError:
                break

            total_time, count = v.real, v.imag
            divisor = count or 1
            mean = total_time / divisor
            yield k, str(mean * 1000) + '|ms'

    def start_logging(self):
        self.log.timings = []

    def end_logging(self):
        timings = getattr(self.log, 'timings', None)
        self.log.timings = None
        return timings


class Timer:
    _time = time.time
    """用于测量经过的时间间隔，并将其记录在 TimingStatBuffer 中。"""

    def __init__(self, client, name, publish=True):
        self.client = client
        self.name = name
        self.publish = publish
        self._start = None
        self._last = None
        self._stop = None
        self._timings = []

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, tb):
        self.stop()

    def flush(self):
        for timing in self._timings:
            self.send(*timing)
        self._timings = []

    def elapsed_seconds(self):
        if self._start is None:
            raise AssertionError("timer hasn't been started")
        if self._stop is None:
            raise AssertionError("timer hasn't been stopped")
        return self._stop - self._start

    def send(self, subname, start, end):
        name = _get_stat_name(self.name, subname)
        self.client.timing_stats.record(name, start, end,
                                        publish=self.publish)

    def start(self):
        self._last = self._start = self._time()

    def intermediate(self, subname):
        print("intermediate")
        if self._last is None:
            raise AssertionError("timer hasn't been started")
        if self._stop is not None:
            raise AssertionError("timer is stopped")
        last, self._last = self._last, self._time()
        self._timings.append((subname, last, self._last))

    def stop(self, subname='total'):
        if self._start is None:
            raise AssertionError("timer hasn't been started")
        if self._stop is not None:
            raise AssertionError('timer is already stopped')
        self._stop = self._time()
        self.flush()
        self.send(subname, self._start, self._stop)


def _get_stat_name(*name_parts):
    def to_str(value):
        if isinstance(value, str):
            return value
        elif isinstance(value, bytes):
            return value.decode('utf-8', 'replace')
        elif isinstance(value, int):
            return str(value)
        else:
            return repr(value)

    return '.'.join(to_str(x) for x in name_parts if x)


class StatsdConnection:
    """管理与 Statsd 服务器的连接，处理数据压缩和传输。"""

    def __init__(self, addr, compress=True):
        if addr:
            self.host, self.port = self._parse_addr(addr)
            self.sock = self._make_socket()
        else:
            self.host = self.port = self.sock = None
        self.compress = compress

    @classmethod
    def _make_socket(cls):
        return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    @staticmethod
    def _parse_addr(addr):
        host, port_str = addr.rsplit(':', 1)
        return host, int(port_str)

    @staticmethod
    def _compress(lines):
        compressed_lines = []
        previous = ''
        for line in sorted(lines):
            prefix = os.path.commonprefix([previous, line])
            if len(prefix) > 3:
                prefix_len = len(prefix)
                compressed_lines.append(
                    '^%02x%s' % (prefix_len, line[prefix_len:]))
            else:
                compressed_lines.append(line)
            previous = line
        return compressed_lines

    def _decompress(self, compressed_lines):
        decompressed_lines = []
        previous = ''
        for line in compressed_lines:
            if line.startswith('^'):
                prefix_len = int(line[1:3], 16)
                decompressed_lines.append(previous[:prefix_len] + line[3:])
                previous = previous[:prefix_len] + line[3:]
            else:
                decompressed_lines.append(line)
                previous = line
        return decompressed_lines

    def send(self, data):
        if self.sock is None:
            return
        data = ('%s:%s' % item for item in data)
        if self.compress:
            data = self._compress(data)
        payload = '\n'.join(data).encode('utf-8')

        server_address = (self.host, self.port)
        self.sock.sendto(payload, server_address)


class CountingStatBuffer:
    """Dictionary of keys to cumulative counts."""
    """用于存储和管理计数统计信息的类"""

    def __init__(self):
        self.data = collections.defaultdict(int)

    def record(self, key, delta):
        self.data[key] += delta

    def flush(self):
        """Yields accumulated counter data and resets the buffer."""
        data, self.data = self.data, collections.defaultdict(int)
        for k, v in data.items():
            yield k, str(v) + '|c'


class StringCountBuffer:
    """Dictionary of keys to counts of various values."""
    """用于存储和管理各种字符串值计数的类。"""

    def __init__(self):
        self.data = collections.defaultdict(
            functools.partial(collections.defaultdict, int))

    @staticmethod
    def _encode_string(string):
        # escape \ -> \\, | -> \&, : -> \;, and newline -> \n
        return (
            string.replace('\\', '\\\\')
            .replace('\n', '\\n')
            .replace('|', '\\&')
            .replace(':', '\\;'))

    def record(self, key, value, count=1):
        self.data[key][value] += count

    def flush(self):
        new_data = collections.defaultdict(
            functools.partial(collections.defaultdict, int))
        data, self.data = self.data, new_data
        for k, counts in data.items():
            for v, count in counts.items():
                yield k, str(count) + '|s|' + self._encode_string(v)


class StatsdClient:
    """汇集不同类型统计缓存，并处理与 Statsd 服务器的连接。"""
    _data_iterator = iter

    _make_conn = StatsdConnection

    def __init__(self, addr=None, sample_rate=1.0):
        self.sample_rate = sample_rate  # 样本率, 可能用于控制数据发送到统计服务的频率。这意味着只有一部分数据会被发送到统计服务进行记录或分析，而不是全部数据。
        """
        假设 sample_rate 设置为 0.5，则大约一半的数据会被发送到统计服务，另一半则会被忽略或丢弃，以达到对数据的采样和统计分析。这种方法可以有效地减少传输和存储开销，同时仍然提供对整体数据趋势的一定了解。
        """
        self.timing_stats = TimingStatBuffer()  # 用于存储和管理时间统计信息的类。它累积不同键的时间值和计数。
        self.counting_stats = CountingStatBuffer()
        self.string_counts = StringCountBuffer()
        self.connect(addr)

    def connect(self, addr):
        self.conn = self._make_conn(addr)

    def disconnect(self):
        self.conn = self._make_conn(None)

    def flush(self):
        data = list(self.timing_stats.flush())
        data.extend(self.counting_stats.flush())
        data.extend(self.string_counts.flush())
        self.conn.send(self._data_iterator(data))


class Counter:
    def __init__(self, client, name):
        self.client = client
        self.name = name

    def _send(self, subname, delta):
        name = _get_stat_name(self.name, subname)
        return self.client.counting_stats.record(name, delta)

    def increment(self, subname=None, delta=1):
        self._send(subname, delta)

    def decrement(self, subname=None, delta=1):
        self._send(subname, -delta)

    def __add__(self, delta):
        self.increment(delta=delta)
        return self

    def __sub__(self, delta):
        self.decrement(delta=delta)
        return self


class Stats:
    # Sample rate for recording cache hits/misses, relative to the global:记录缓存命中/未命中的采样率，相对于全局
    # sample_rate.
    CACHE_SAMPLE_RATE = 0.01

    CASSANDRA_KEY_SUFFIXES = ['error', 'ok']

    def __init__(self, addr, sample_rate):
        self.client = StatsdClient(addr, sample_rate)

    def get_timer(self, name, publish=True):
        return Timer(self.client, name, publish)

    # Just a convenience method to use timers as context managers clearly
    def quick_time(self, *args, **kwargs):
        return self.get_timer(*args, **kwargs)

    def transact(self, action, start, end):
        timer = self.get_timer('service_time')
        timer.send(action, start, end)

    def get_counter(self, name):
        return Counter(self.client, name)

    def action_count(self, counter_name, name, delta=1):
        counter = self.get_counter(counter_name)
        if counter:
            # from pylons import request
            # counter.increment('%s.%s' % (request.environ["pylons.routes_dict"]["action"], name), delta=delta)
            counter.increment('%s.%s' % ("routes_dict.action", name), delta=delta)

    def action_event_count(self, event_name, state=None, delta=1, true_name="success", false_name="fail"):
        counter_name = 'event.%s' % event_name
        if state == True:
            self.action_count(counter_name, true_name, delta=delta)
        elif state == False:
            self.action_count(counter_name, false_name, delta=delta)
        self.action_count(counter_name, 'total', delta=delta)

    def simple_event(self, event_name, delta=1):
        parts = event_name.split('.')
        counter = self.get_counter('.'.join(['event'] + parts[:-1]))
        if counter:
            counter.increment(parts[-1], delta=delta)

    def simple_timing(self, event_name, ms):
        self.client.timing_stats.record(event_name, start=0, end=ms)

    def event_count(self, event_name, name, sample_rate=None):
        if sample_rate is None:
            sample_rate = 1.0
        counter = self.get_counter('event.%s' % event_name)
        if counter and random.random() < sample_rate:
            counter.increment(name)
            counter.increment('total')

    def cache_count_multi(self, data, sample_rate=None):
        if sample_rate is None:
            sample_rate = self.CACHE_SAMPLE_RATE
        counter = self.get_counter('cache')
        if counter and random.random() < sample_rate:
            for name, delta in data.iteritems():
                counter.increment(name, delta=delta)

    def amqp_processor(self, queue_name):
        """用于记录 amqp 队列消费者/处理程序统计信息的装饰器。"""

        def decorator(processor):
            def wrap_processor(msgs, *args):
                # Work the same for amqp.consume_items and amqp.handle_items.
                msg_tup = set(msgs)

                metrics_name = "amqp." + queue_name
                start = time.time()
                try:
                    with baseplate_integration.make_server_span(metrics_name):
                        return processor(msgs, *args)
                finally:
                    service_time = (time.time() - start) / len(msg_tup)
                    for n, msg in enumerate(msg_tup):
                        fake_start = start + n * service_time
                        fake_end = fake_start + service_time
                        self.transact(metrics_name, fake_start, fake_end)
                    self.flush()

            return wrap_processor

        return decorator

    def flush(self):
        self.client.flush()

    def start_logging_timings(self):
        self.client.timing_stats.start_logging()

    def end_logging_timings(self):
        return self.client.timing_stats.end_logging()

    def cf_key_iter(self, operation, column_families, suffix):
        if not self.client:
            return
        if not isinstance(column_families, list):
            column_families = [column_families]
        for cf in column_families:
            yield '.'.join(['cassandra', cf, operation, suffix])

    def cassandra_timing(self, operation, column_families, success,
                         start, end):
        suffix = self.CASSANDRA_KEY_SUFFIXES[success]
        for key in self.cf_key_iter(operation, column_families, suffix):
            self.client.timing_stats.record(key, start, end)

    def cassandra_counter(self, operation, column_families, suffix, delta):
        for key in self.cf_key_iter(operation, column_families, suffix):
            self.client.counting_stats.record(key, delta)

    def pg_before_cursor_execute(self, conn, cursor, statement, parameters,
                                 context, executemany):
        from pylons import tmpl_context as c

        context._query_start_time = time.time()

        try:
            c.trace
        except TypeError:
            # the tmpl_context global isn't available out of request
            return

        if c.trace:
            context.pg_child_trace = c.trace.make_child("postgres")
            context.pg_child_trace.start()

    def pg_after_cursor_execute(self, conn, cursor, statement, parameters,
                                context, executemany):
        dsn = dict(part.split('=', 1)
                   for part in context.engine.url.query['dsn'].split())

        if getattr(context, "pg_child_trace", None):
            context.pg_child_trace.set_tag("host", dsn["host"])
            context.pg_child_trace.set_tag("db", dsn["dbname"])
            context.pg_child_trace.set_tag("statement", statement)
            context.pg_child_trace.finish()

        start = context._query_start_time
        self.pg_event(dsn['host'], dsn['dbname'], start, time.time())

    def pg_event(self, db_server, db_name, start, end):
        if not self.client:
            return
        key = '.'.join(['pg', db_server.replace('.', '-'), db_name])
        self.client.timing_stats.record(key, start, end)

    def count_string(self, key, value, count=1):
        self.client.string_counts.record(key, str(value), count=count)


if __name__ == '__main__':
    # Create a StatsdClient instance with the address of your Statsd server
    statsd_client = StatsdClient(addr='127.0.0.1:12345')

    # Start logging timings
    statsd_client.timing_stats.start_logging()  # ['operation_name.Stage1:1005.0837993621826|ms', '^142:2002.2122859954834|ms', '^143:500.718355178833|ms', '^0ftotal:3508.014440536499|ms']

    # Use Timer to measure the time for a specific operation
    with Timer(statsd_client, 'operation_name') as timer:
        # Perform your operation here
        # 模拟不同阶段的任务
        time.sleep(1)
        timer.intermediate("Stage1")

        time.sleep(2)
        timer.intermediate("Stage2")

    # Stop logging timings
    timings = statsd_client.timing_stats.end_logging()

    with Timer(statsd_client, 'operation_name'):
        # 模拟不同阶段的任务
        statsd_client.counting_stats.record("event_1", 2)
        statsd_client.counting_stats.record("event_2", 3)

    with Timer(statsd_client, 'operation_name') as timer:
        # 记录字符串值的计数
        statsd_client.string_counts.record("key_1", "value_1")
        statsd_client.string_counts.record("key_2", "value_2", 3)
        statsd_client.string_counts.record("key_1", "value_1")
        statsd_client.string_counts.record("key_2", "value_1", 2)

    # 计时器自动停止，并将记录发送给统计客户端
    statsd_client.flush()
