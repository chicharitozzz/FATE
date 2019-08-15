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

import os
import uuid
from typing import Iterable

from arch.api import RuntimeInstance
from arch.api import WorkMode, NamingPolicy
from arch.api.core import EggRollContext
from arch.api.utils import file_utils
from arch.api.utils.log_utils import LoggerFactory
from arch.api.table.abc.table import Table

from arch.api.utils.profile_util import log_elapsed


# noinspection PyProtectedMember
def init(job_id=None,
         mode: WorkMode = WorkMode.STANDALONE,
         naming_policy: NamingPolicy = NamingPolicy.DEFAULT,
         master=None):
    if RuntimeInstance.EGGROLL:
        return
    if job_id is None:
        job_id = str(uuid.uuid1())
        LoggerFactory.set_directory()
    else:
        LoggerFactory.set_directory(os.path.join(file_utils.get_project_base_directory(), 'logs', job_id))
    RuntimeInstance.MODE = mode

    eggroll_context = EggRollContext(naming_policy=naming_policy)
    if mode == WorkMode.STANDALONE:
        # from arch.api.standalone.eggroll import Standalone
        # RuntimeInstance.EGGROLL = Standalone(job_id=job_id, eggroll_context=eggroll_context)
        from arch.api.table.eggroll.standalone.table_manager import DTableManager
        RuntimeInstance.EGGROLL = DTableManager(job_id=job_id, eggroll_context=eggroll_context)
    elif mode == WorkMode.CLUSTER:
        # from arch.api.cluster.eggroll import _EggRoll
        # from arch.api.cluster.eggroll import init as c_init
        # c_init(job_id, eggroll_context=eggroll_context)
        # RuntimeInstance.EGGROLL = _EggRoll.get_instance()
        from arch.api.table.eggroll.cluster.table_manager import DTableManager
        RuntimeInstance.EGGROLL = DTableManager(job_id=job_id, eggroll_context=eggroll_context)
    elif mode == WorkMode.SPARK_LOCAL:
        from arch.api.table.pyspark.standalone.table_manager import RDDTableManager
        rdd_manager = RDDTableManager(job_id=job_id, eggroll_context=eggroll_context)
        RuntimeInstance.EGGROLL = rdd_manager
    elif mode == WorkMode.SPARK_CLUSTER:
        from arch.api.table.pyspark.cluster.table_manager import RDDTableManager
        rdd_manager = RDDTableManager(job_id=job_id, eggroll_context=eggroll_context, master=master)
        RuntimeInstance.EGGROLL = rdd_manager
    table("__federation__", job_id, partition=10)


@log_elapsed
def table(name, namespace, partition=1, persistent=True, create_if_missing=True, error_if_exist=False,
          in_place_computing=False) -> Table:
    return RuntimeInstance.EGGROLL.table(name=name,
                                         namespace=namespace,
                                         partition=partition,
                                         persistent=persistent,
                                         in_place_computing=in_place_computing)


@log_elapsed
def parallelize(data: Iterable, include_key=False, name=None, partition=1, namespace=None, persistent=False,
                create_if_missing=True, error_if_exist=False, chunk_size=100000, in_place_computing=False) -> Table:
    return RuntimeInstance.EGGROLL.parallelize(data=data, include_key=include_key, name=name, partition=partition,
                                               namespace=namespace,
                                               persistent=persistent,
                                               chunk_size=chunk_size,
                                               in_place_computing=in_place_computing)


def cleanup(name, namespace, persistent=False):
    return RuntimeInstance.EGGROLL.cleanup(name=name, namespace=namespace, persistent=persistent)


# noinspection PyPep8Naming
def generateUniqueId():
    return RuntimeInstance.EGGROLL.generateUniqueId()


def get_job_id():
    return RuntimeInstance.EGGROLL.job_id
