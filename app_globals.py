from configparse import ConfigValueParser, ConfigValue
from utils import queues
class Globals(object):
    

    def __init__(self, config_data):
        self.config =  ConfigValueParser(config_data)
        self.config.add_spec({
            ConfigValue.str: ['amqp_user', 'amqp_host', 'amqp_pass', 'amqp_virtual_host'],
            # ConfigValue.int: ['age'],
            # ConfigValue.float: ['height'],
            ConfigValue.bool: ['amqp_logging', 'shard_commentstree_queues', 'shard_author_query_queues',
                               'shard_subreddit_query_queues', 'shard_domain_query_queues'],
            # ConfigValue.set: ['fruits'],
            # ConfigValue.tuple: ['hardcache_categories'],
            # ConfigValue.dict: ['address'],
            # ConfigValue.choice(red='red', blue='blue', green='green'): ['favorite_color'],
        })
        # log = logging.getLogger('reddit')
        self.queues = queues.declare_queues(self)   
        # self.tz = pytz.timezone('UTC')
        # dtz = global_conf.get('display_timezone', tz)
        # self.display_tz = pytz.timezone('UTC')
        


    def __getattr__(self, name):
        if not name.startswith('_') and name in self.config:
            return self.config[name]
        else:
            raise AttributeError("g has no attr %r" % name)

