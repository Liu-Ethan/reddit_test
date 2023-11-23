from utils.utils import tup

error_list = dict((
    ('USER_REQUIRED', "Please log in to do that. {chars} "),
    # ('SHORT_PASSWORD', _('the password must be at least {chars} characters')),
    ('MOD_REQUIRED', "You must be a moderator to do that."),
    ('SHORT_PASSWORD', "The password must be at least {chars} characters."),
    ('INVALID_EMAIL', "Invalid email format."),
    ('INVALID_USERNAME', "Invalid username."),
))


class Storage(dict):
    """
    A Storage object is like a dictionary except `obj.foo` can be used
    in addition to `obj['foo']`.

        >>> o = Storage(a=1)
        >>> o.a
        1
        >>> o['a']
        1
        >>> o.a = 2
        >>> o['a']
        2
        >>> del o.a
        >>> o.a
        Traceback (most recent call last):
            ...
        AttributeError: 'a'

    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as k:
            raise AttributeError(k)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError as k:
            raise AttributeError(k)

    def __repr__(self):
        return '<Storage ' + dict.__repr__(self) + '>'


errors = Storage([(e, e) for e in error_list.keys()])


class RedditError(Exception):
    name = None
    fields = None
    code = None

    def __init__(self, name=None, msg_params=None, fields=None, code=None):
        super().__init__()

        if name is not None:
            self.name = name

        # Assuming error_list is defined elsewhere
        self.i18n_message = error_list.get(self.name)
        self.msg_params = msg_params or {}

        if fields is not None:
            # list of fields in the original form that caused the error
            self.fields = tup(fields)

        if code is not None:
            self.code = code

    @property
    def message(self):
        return self.i18n_message.format(**self.msg_params)

    def __iter__(self):
        """
         for key, value in e:
            print(f'{key}: {value}')
        """
        yield ('name', self.name)
        yield ('message', self.message)

    def __repr__(self):
        # print(e) 时的输出
        return f'<RedditError: {self.name}>'

    def __str__(self):
        return repr(self)


class ErrorSet:
    def __init__(self):
        self.errors = {}

    def __contains__(self, pair):
        """Expects an (error_name, field_name) tuple and checks to
        see if it's in the errors list."""
        return pair in self.errors

    def get(self, name, default=None):
        return self.errors.get(name, default)

    def get_first(self, field_name, *error_names):
        for error_name in error_names:
            error = self.get((error_name, field_name))
            return error

    def __getitem__(self, name):
        return self.errors[name]

    def __repr__(self):
        return f"<ErrorSet {list(self)}>"

    def __iter__(self):
        for x in self.errors:
            yield x

    def __len__(self):
        return len(self.errors)

    def add(self, error_name, msg_params=None, field=None, code=None):
        for field_name in tup(field):
            e = RedditError(error_name, msg_params, fields=field_name, code=code)
            self.add_error(e)

    def add_error(self, error):
        for field_name in (error.fields,) if isinstance(error.fields, str) else error.fields:
            self.errors[(error.name, field_name)] = error

    def remove(self, pair):
        """Expects an (error_name, field_name) tuple and removes it
        from the errors list."""
        if pair in self.errors:
            del self.errors[pair]


class UserRequiredException(RedditError):
    name = errors.USER_REQUIRED
    code = 403


if __name__ == "__main__":
    # try:
    #     raise UserRequiredException(msg_params={"chars": 12})
    # except UserRequiredException as e:
    #     for key, value in e:
    #         print(f'{key}: {value}')
    # 创建 ErrorSet 对象
    errors = ErrorSet()

    # 添加一些错误到 ErrorSet 对象中
    errors.add('SHORT_PASSWORD', {'chars': 8}, field='password')
    errors.add('INVALID_EMAIL', field='email')
    errors.add('INVALID_USERNAME', field='username')
    print(errors)
    # 获取特定字段的第一个错误
    first_error = errors.get_first('email', 'INVALID_EMAIL', 'INVALID_USERNAME')
    if first_error:
        print(f"First error for email: {first_error.name}")

    # 检查某个错误是否在 ErrorSet 对象中
    if ('INVALID_EMAIL', 'email') in errors:
        print("Invalid email error found in errors!")

    # 删除特定的错误
    errors.remove(('INVALID_EMAIL', 'email'))

    # 迭代 ErrorSet 中的错误
    print("All errors:")
    for error in errors:
        print(error)
