import tdb_lite
import sqlalchemy as sa

class HardCacheBackend(object):
    def __init__(self, gc):
        self.tdb = tdb_lite(gc)
        self.profile_categories = {}
        TZ = gc.display_tz

        def _table(metadata):
            """用于创建一个数据库表。该表具有category、ids、value、kind和expiration等列。这个函数在循环中处理一个列表中的项目，根据分隔符将项目拆分为不同的部分，并根据这些部分创建一个数据库表。最后，它将一个字典映射关系添加到该函数的实例中。"""
            return sa.Table(gc.db_app_name + '_hardcache', metadata,
                            sa.Column('category', sa.String, nullable = False,
                                      primary_key = True),
                            sa.Column('ids', sa.String, nullable = False,
                                      primary_key = True),
                            sa.Column('value', sa.String, nullable = False),
                            sa.Column('kind', sa.String, nullable = False),
                            sa.Column('expiration',
                                      sa.DateTime(timezone = True),
                                      nullable = False)
                            )
        enginenames_by_category = {}
        all_enginenames = set()
        for item in gc.hardcache_categories:
            chunks = item.split(":")
            if len(chunks) < 2:
                raise ValueError("Invalid hardcache_overrides")
            category = chunks.pop(0)
            enginenames_by_category[category] = []
            for c in chunks:
                if c == '!profile':
                    self.profile_categories[category] = True
                elif c.startswith("!"):
                    raise ValueError("WTF is [%s] in hardcache_overrides?" % c)
                else:
                    all_enginenames.add(c)
                    enginenames_by_category[category].append(c)

        assert('*' in enginenames_by_category.keys())

        engines_by_enginename = {}
        for enginename in all_enginenames:
            engine = gc.dbm.get_engine(enginename)
            md = self.tdb.make_metadata(engine)
            table = _table(md)
            indstr = self.tdb.index_str(table, 'expiration', 'expiration')
            self.tdb.create_table(table, [ indstr ])
            engines_by_enginename[enginename] = table

        self.mapping = {}
        for category, enginenames in enginenames_by_category.iteritems():
            self.mapping[category] = [ engines_by_enginename[e]
                                       for e in enginenames]
