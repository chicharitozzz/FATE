#
#  Copyright 2019 The FATE Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import uuid
from typing import Iterable

from pyspark import SparkContext, RDD

# noinspection PyProtectedMember
from arch.api.cluster.eggroll import _DTable as DTable
from arch.api.table.abc.table import Table
from arch.api.table.pyspark import _RDD_ATTR_NAME
from arch.api.table.pyspark import materialize, STORAGE_LEVEL


class RDDTable(Table):

    # noinspection PyProtectedMember
    @classmethod
    def from_dtable(cls, dtable: DTable):
        namespace = dtable._namespace
        name = dtable._name
        partitions = dtable._partitions
        return RDDTable(namespace=namespace, name=name, partitions=partitions, dtable=dtable)

    @classmethod
    def from_rdd(cls, rdd: RDD, namespace: str, name: str):
        partitions = rdd.getNumPartitions()
        return RDDTable(namespace=namespace, name=name, partitions=partitions, rdd=rdd)

    def __init__(self, namespace: str,
                 name: str = None,
                 partitions: int = 1,
                 rdd: RDD = None,
                 dtable: DTable = None):

        self._valid_param_check(rdd, dtable, namespace, partitions)
        setattr(self, _RDD_ATTR_NAME, rdd)
        self._rdd = rdd
        self._partitions = partitions
        self._dtable = dtable
        self.schema = {}  # todo: ???
        self._name = name or str(uuid.uuid1())
        self._namespace = namespace

    def _new_from_rdd(self, rdd: RDD, name=None):
        rdd = materialize(rdd)
        name = name or str(uuid.uuid1())
        return RDDTable(namespace=self._namespace, name=name, partitions=rdd.getNumPartitions(), rdd=rdd, dtable=None)

    # self._rdd should not be pickled(spark requires all transformer/action to be invoked in driver).
    def __getstate__(self):
        state = dict(self.__dict__)
        if "_rdd" in state:
            del state["_rdd"]
        return state

    @staticmethod
    def _valid_param_check(rdd, dtable, namespace, partitions):
        assert (rdd is not None) or (dtable is not None), "params rdd and storage are both None"
        assert namespace is not None, "namespace is None"
        assert partitions > 0, "invalid partitions={0}".format(partitions)

    def get_partitions(self):
        return self._partitions

    def get_name(self):
        return self._name

    def get_namespace(self):
        return self._namespace

    # noinspection PyProtectedMember
    @property
    def rdd(self):
        """
        todo: storage -> rdd, to be optimized
        """
        if hasattr(self, "_rdd") and self._rdd is not None:
            return self._rdd

        if self._dtable is None:
            raise AssertionError("try create rdd from None storage")

        storage_iterator = self._dtable.collect(use_serialize=True)
        if self._dtable.count() <= 0:
            storage_iterator = []
        num_partition = self._dtable._partitions
        self._rdd = SparkContext.getOrCreate() \
            .parallelize(storage_iterator, num_partition) \
            .persist(STORAGE_LEVEL)
        return self._rdd

    @property
    def dtable(self):
        """
        rdd -> storage
        """
        if self._dtable:
            return self._dtable
        else:
            if not hasattr(self, "_rdd") or self._rdd is None:
                raise AssertionError("try create rdd from None storage")
            self._dtable = \
                self.save_as(name=self._name, namespace=self._namespace, partition=self._partitions)._dtable
        return self._dtable

    def map(self, func):
        from arch.api.table.pyspark.cluster.rdd_func import _map
        rtn_rdd = _map(self.rdd, func)
        return self._new_from_rdd(rtn_rdd)

    def mapValues(self, func):
        from arch.api.table.pyspark.cluster.rdd_func import _map_value
        rtn_rdd = _map_value(self.rdd, func)
        return self._new_from_rdd(rtn_rdd)

    def mapPartitions(self, func):
        from arch.api.table.pyspark.cluster.rdd_func import _map_partitions
        rtn_rdd = _map_partitions(self.rdd, func)
        return self._new_from_rdd(rtn_rdd)

    def reduce(self, func):
        return self.rdd.values().reduce(func)

    def join(self, other, func=None):
        from arch.api.table.pyspark.cluster.rdd_func import _join
        return self._new_from_rdd(_join(self.rdd, other.rdd, func))

    def glom(self):
        from arch.api.table.pyspark.cluster.rdd_func import _glom
        return self._new_from_rdd(_glom(self.rdd))

    def sample(self, fraction, seed=None):
        from arch.api.table.pyspark.cluster.rdd_func import _sample
        return self._new_from_rdd(_sample(self.rdd, fraction, seed))

    def subtractByKey(self, other):
        from arch.api.table.pyspark.cluster.rdd_func import _subtract_by_key
        return self._new_from_rdd(_subtract_by_key(self.rdd, other.rdd))

    def filter(self, func):
        from arch.api.table.pyspark.cluster.rdd_func import _filter
        return self._new_from_rdd(_filter(self.rdd, func))

    def union(self, other, func=lambda v1, v2: v1):
        from arch.api.table.pyspark.cluster.rdd_func import _union
        return self._new_from_rdd(_union(self.rdd, other.rdd, func))

    def flatMap(self, func):
        from arch.api.table.pyspark.cluster.rdd_func import _flat_map
        return self._new_from_rdd(_flat_map(self.rdd, func))

    def collect(self, min_chunk_size=0, use_serialize=True):
        if self._dtable:
            return self.dtable.collect(min_chunk_size, use_serialize)
        else:
            return iter(self.rdd.collect())

    """
    storage api
    """

    def put(self, k, v, use_serialize=True):
        rtn = self.dtable.put(k, v, use_serialize)
        self._rdd = None
        return rtn

    def put_all(self, kv_list: Iterable, use_serialize=True, chunk_size=100000):
        rtn = self.dtable.put_all(kv_list, use_serialize, chunk_size)
        self._rdd = None
        return rtn

    def get(self, k, use_serialize=True):
        return self.dtable.get(k, use_serialize)

    def delete(self, k, use_serialize=True):
        rtn = self.dtable.delete(k, use_serialize)
        self._rdd = None
        return rtn

    def destroy(self):
        if self._dtable:
            self._dtable.destroy()
        else:
            self._rdd = None
        return True

    def put_if_absent(self, k, v, use_serialize=True):
        rtn = self.dtable.put_if_absent(k, v, use_serialize)
        self._rdd = None
        return rtn

    # noinspection PyPep8Naming
    def take(self, n=1, keysOnly=False, use_serialize=True):
        if self._dtable:
            return self._dtable.take(n, keysOnly, use_serialize)
        else:
            rtn = self._rdd.take(n)
            if keysOnly:
                rtn = [pair[0] for pair in rtn]
            return rtn

    # noinspection PyPep8Naming
    def first(self, keysOnly=False, use_serialize=True):
        return self.take(1, keysOnly, use_serialize)[0]

    def count(self):
        if self._dtable:
            return self._dtable.count()
        else:
            return self._rdd.count()

    # noinspection PyProtectedMember
    def save_as(self, name, namespace, partition=None, use_serialize=True, persistent=False) -> 'RDDTable':
        partition = partition or self._partitions
        if self._dtable:
            _dtable = self._dtable.save_as(name, namespace, partition,
                                           use_serialize=use_serialize, persistent=persistent)
            return RDDTable.from_dtable(_dtable)
        else:
            from arch.api.table.pyspark.cluster.rdd_func import _save_as_func
            return _save_as_func(self._rdd, name=name, namespace=namespace, partition=partition, persistent=persistent)
