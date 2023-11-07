
import logging
import os
import random
import socket
import sqlalchemy
import time
import traceback


logger = logging.getLogger('dm_manager')
logger.addHandler(logging.StreamHandler())
APPLICATION_NAME = "reddit@%s:%d" % (socket.gethostname(), os.getpid())


def get_engine(name, db_host='', db_user='', db_pass='', db_port='5432',
               pool_size=5, max_overflow=5, g_override=None):
    db_port = int(db_port)

    arguments = {
        "dbname": name,
        "host": db_host,
        "port": db_port,
        "application_name": APPLICATION_NAME,
    }
    if db_user:
        arguments["user"] = db_user
    if db_pass:
        arguments["password"] = db_pass
    dsn = "%20".join("%s=%s" % x for x in arguments.items())

    engine = sqlalchemy.create_engine(
        'postgresql:///?dsn=' + dsn,
        # strategy='threadlocal',
        pool_size=int(pool_size),
        max_overflow=int(max_overflow),
        # our code isn't ready for unicode to appear
        # in place of strings yet
        # use_native_unicode=False,
    )
    # engine.ex

    if g_override:
        sqlalchemy.event.listens_for(engine, 'before_cursor_execute')(
            g_override.stats.pg_before_cursor_execute)
        sqlalchemy.event.listens_for(engine, 'after_cursor_execute')(
            g_override.stats.pg_after_cursor_execute)

    return engine


class db_manager:
    def __init__(self):
        self.type_db = None
        self.relation_type_db = None
        self._things = {}
        self._relations = {}
        self._engines = {}
        self.avoid_master_reads = {}
        self.dead = {}

    def add_thing(self, name, thing_dbs, avoid_master=False, **kw):
        """thing_dbs is a list of database engines. the first in the
        list is assumed to be the master, the rest are slaves."""
        self._things[name] = thing_dbs
        self.avoid_master_reads[name] = avoid_master

    def add_relation(self, name, type1, type2, relation_dbs,
                     avoid_master=False, **kw):
        self._relations[name] = (type1, type2, relation_dbs)
        self.avoid_master_reads[name] = avoid_master

    def setup_db(self, db_name, g_override=None, **params):
        engine = get_engine(db_name, g_override=g_override, **params)
        self._engines[db_name] = engine

        if db_name not in ("email", "authorize", "hc", "traffic"):
            # test_engine creates a connection to the database, for some less
            # important and less used databases we will skip this and only
            # create the connection if it's needed
            self.test_engine(engine, g_override)

    def things_iter(self):
        for name, engines in self._things.iteritems():
            # ensure we ALWAYS return the actual master as the first,
            # regardless of if we think it's dead or not.
            yield name, [engines[0]] + [e for e in engines[1:]
                                        if e not in self.dead]

    def rels_iter(self):
        for name, (t1_name, t2_name, engines) in self._relations.iteritems():
            engines = [engines[0]] + [e for e in engines[1:]
                                      if e not in self.dead]
            yield name, (t1_name, t2_name, engines)

    def mark_dead(self, engine, g_override=None):
        logger.error("db_manager: marking connection dead: %r", engine)
        self.dead[engine] = time.time()

    # 原始代码
    def test_engine(self, engine, g_override=None):
        try:
            # list(engine.execute("select 1"))
            with engine.connect() as connection:
                query = sqlalchemy.text("SELECT 1")
                result = connection.execute(query)
                print(list(result))
            if engine in self.dead:
                logger.error("db_manager: marking connection alive: %r",
                            engine)
                del self.dead[engine]
            return True
        except Exception:
            logger.error(traceback.format_exc())
            logger.error("connection failure: %r" % engine)
            self.mark_dead(engine, g_override)
            return False

    def get_engine(self, name):
        return self._engines[name]

    def get_engines(self, names):
        return [self._engines[name] for name in names if name in self._engines]

    def get_read_table(self, tables):
        if len(tables) == 1:
            return tables[0]
        return  random.choice(list(tables))



# 创建 db_manager 实例
db_manager_instance = db_manager()

# 配置数据库连接信息
db_manager_instance.setup_db(
    "rytd",
    db_host="localhost",
    db_user="postgres",
    db_pass="liu*963.",
    db_port="5432",
    pool_size=5,
    max_overflow=5
)

# 添加事物
# db_manager_instance.add_thing("users", [db_manager_instance.get_engine("my_db")])

# 添加关系
# db_manager_instance.add_relation("user_posts", "users", "posts",
#     [db_manager_instance.get_engine("my_db")]
# )

# 获取数据库引擎
engine = db_manager_instance.get_engine("rytd")

# 测试数据库连接
if db_manager_instance.test_engine(engine):
    print("Database connection is alive.")
else:
    print("Database connection is dead.")

# 标记数据库连接为死亡
# db_manager_instance.mark_dead(engine)

