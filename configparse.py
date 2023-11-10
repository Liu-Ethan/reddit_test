"""这段代码的主要目的是将配置文件中的原始字符串配置值解析为适当的 Python 数据类型，以便在应用程序中使用。
它提供了一种可扩展的方式，可以根据配置规范定义不同数据类型的配置值和解析规则。
这使得应用程序可以根据配置文件中的值来自动选择适当的解析器，并且具有一定的灵活性。
"""
import re


class ConfigValue(object):
    _bool_map = dict(true=True, false=False)

    @staticmethod
    def str(v, key=None):
        return str(v)

    @staticmethod
    def int(v, key=None):
        return int(v)

    @staticmethod
    def float(v, key=None):
        return float(v)

    @staticmethod
    def bool(v, key=None):
        if v in (True, False, None):
            return bool(v)
        try:
            return ConfigValue._bool_map[v.lower()]
        except KeyError:
            raise ValueError("Unknown value for %r: %r" % (key, v))

    @staticmethod
    def tuple(v, key=None):
        return tuple(ConfigValue.to_iter(v))

    @staticmethod
    def set(v, key=None):
        return set(ConfigValue.to_iter(v))

    @staticmethod
    def set_of(value_type, delim=','):
        def parse(v, key=None):
            return set(value_type(x)
                       for x in ConfigValue.to_iter(v, delim=delim))
        return parse

    @staticmethod
    def tuple_of(value_type, delim=','):
        def parse(v, key=None):
            return tuple(value_type(x)
                         for x in ConfigValue.to_iter(v, delim=delim))
        return parse

    @staticmethod
    def dict(key_type, value_type, delim=',', kvdelim=':'):
        def parse(v, key=None):
            values = (i.partition(kvdelim)
                      for i in ConfigValue.to_iter(v, delim=delim))
            return {key_type(x): value_type(y) for x, _,  y in values}
        return parse

    @staticmethod
    def choice(**choices):
        def parse_choice(v, key=None):
            try:
                return choices[v]
            except KeyError:
                raise ValueError("Unknown option for %r: %r not in %r" % (key, v, choices.keys()))
        return parse_choice

    @staticmethod
    def to_iter(v, delim = ','):
        return (x.strip() for x in v.split(delim) if x)

    # @staticmethod
    # def timeinterval(v, key=None):
    #     # this import is at function level because it relies on the cythonized
    #     # modules being present which is a problem for plugin __init__s that
    #     # use this module since they are imported in the early stages of the
    #     # makefile
    #     from r2.lib.utils import timeinterval_fromstr
    #     return timeinterval_fromstr(v)

    messages_re = re.compile(r'"([^"]+)"')
    @staticmethod
    def messages(v, key=None):
        return ConfigValue.messages_re.findall(v.decode("string_escape"))

    @staticmethod
    def baseplate(baseplate_parser):
        def adapter(v, key=None):
            return baseplate_parser(v)
        return adapter


class ConfigValueParser(dict):
    def __init__(self, raw_data):
        dict.__init__(self, raw_data)
        self.config_keys = {}
        self.raw_data = raw_data

    def add_spec(self, spec):
        new_keys = []
        for parser, keys in spec.items():
            # keys can be either a list or a dict
            for key in keys:
                assert key not in self.config_keys
                self.config_keys[key] = parser
                new_keys.append(key)
        self._update_values(new_keys)

    def _update_values(self, keys):
        for key in keys:
            if key not in self.raw_data:
                continue

            value = self.raw_data[key]
            if key in self.config_keys:
                parser = self.config_keys[key]
                value = parser(value, key)
            self[key] = value



# config_data = {
#     'name': 'John',
#     'age': '30',
#     'height': '175.5',
#     'is_enabled': 'true',
#     'fruits': 'apple,banana,orange',
#     'numbers': '1,2,3,4,5',
#     'address': """{
#         "street": "123 Main St",
#         "city": "New York",
#         "zip_code": "10001"
#     }""",
#     'favorite_color': 'blue',
# }

# 创建 ConfigValueParser 对象
# config_parser = ConfigValueParser(config_data)

# 添加配置规范
# config_parser.add_spec({
#     ConfigValue.str: ['name'],
#     ConfigValue.int: ['age'],
#     ConfigValue.float: ['height'],
#     ConfigValue.bool: ['is_enabled'],
#     ConfigValue.set: ['fruits'],
#     ConfigValue.tuple: ['numbers'],
#     ConfigValue.dict: ['address'],
#     ConfigValue.choice(red='red', blue='blue', green='green'): ['favorite_color'],
# })

# # 访问解析后的配置值
# name = config_parser['name']
# age = config_parser['age']
# height = config_parser['height']
# is_enabled = config_parser['is_enabled']
# fruits = config_parser['fruits']
# numbers = config_parser['numbers']
# address = config_parser['address']
# favorite_color = config_parser['favorite_color']

# # 输出解析后的配置值
# print(f"Name: {name}, Age: {age}, Height: {height}, Is Enabled: {is_enabled}")
# print(f"Fruits: {fruits}, Numbers: {numbers}, Address: {address}")
# print(f"Favorite Color: {favorite_color}")

