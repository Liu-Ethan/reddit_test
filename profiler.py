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

import cProfile
import pstats
from functools import wraps, partial


def profile(fn):
    @wraps(fn)
    def _fn(*a, **kw):
        currently_profiling = cProfile.Profile()
        currently_profiling.enable()

        ret = fn(*a, **kw)

        currently_profiling.disable()
        stats = pstats.Stats(currently_profiling)
        stats.sort_stats('cumtime')
        stats.print_stats()

        return ret
    return _fn


# 使用装饰器
@profile
def my_function():
    # 在这里编写需要性能分析的代码
    for i in range(10000):
        _ = [j for j in range(i)]

# 调用函数，触发性能分析
my_function()