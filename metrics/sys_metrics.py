import multiprocessing
import time
from collections import namedtuple
from functools import wraps
from typing import Tuple

import numpy as np
import psutil
from matplotlib import pyplot as plt

from .base_metrics import SingleNestValueMetric, fn_name_template, validate_other_same_class, pull_self, fn_name_abbr
from .time_metrics import PerformanceRegistry

CPU_MEASURMENT_INTERVAL = 0.1
RSS_MEASURMENT_INTERVAL = 0.1


class NMeansTupleData:
    n: int
    values: Tuple[float, ...]

    def update_from_historical(self, other) -> 'NMeansTupleData':
        validate_other_same_class(self, other)
        current_n = self.n
        other_n = other.n
        current_arr = np.array(self.values)
        other_arr = np.array(other.values)
        length: int = max(len(current_arr), len(other_arr))
        current_arr.resize(length)
        other_arr.resize(length)

        new_mean = tuple(((current_n * current_arr) + (other_n * other_arr)) / (current_n + other_n))
        return self.__class__(current_n + other_n, new_mean)

    @classmethod
    def null(cls) -> 'NMeansTupleData':
        return cls(0, (0,))


class CPUMeanUseData(namedtuple('CPUMeanUseData', field_names=('n', 'values')), NMeansTupleData):
    pass


class CPUUseRegistry(PerformanceRegistry):

    def purge(self):
        for k in self.keys():
            self[k] = CPUMeanUseData.null()

    def cast(self):
        return {k: tuple(v) for k, v in self.items()}

    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        for k, v in historical.items():
            self[k] = self.get(k, CPUMeanUseData.null()).update_from_historical(v)


def cpu_measurment(q, pid, flag):
    process = [p for p in psutil.process_iter(['pid']) if p.pid == pid][0]
    while not flag.is_set():
        q.put(process.cpu_percent(interval=CPU_MEASURMENT_INTERVAL))


class CpuUse(SingleNestValueMetric):
    """
    CPU use is sampled every 0.1 sec (CPU_MEASURMENT_INTERVAL)
    For functions faster than this resolution metric might collect useless values.
    """
    PRIMARY_REGISTRY = CPUUseRegistry
    PRIMARY_REGISTRY_DEFAULT = CPUMeanUseData.null

    def decorator(self, fn):
        template = fn_name_template(fn)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            fn_name = template.format(pull_self(args))
            # setup
            pid = psutil.Process().pid
            with multiprocessing.Manager() as manager:
                flag = manager.Event()
                flag.clear()
                q = manager.Queue()
                # calculate
                p = multiprocessing.Process(target=cpu_measurment, args=(q, pid, flag))
                p.start()
                result = fn(*args, **kwargs)
                flag.set()

                p.join()
                m = []
                while not q.empty():
                    m.append(q.get())
                self.registry[fn_name] = self.registry[fn_name].update_from_historical(CPUMeanUseData(1, tuple(m)))
                return result
        return wrapper

    def serialize(self):
        return self.registry.cast()

    @classmethod
    def load(cls, d):
        metric = cls()
        for fn, perfs in d.items():
            n, values = perfs
            metric.registry[fn] = CPUMeanUseData(n, values)
        return metric

    def plot(self):
        fig = plt.Figure()
        for fn, v in self.registry.items():
            n, values = v
            plt.plot(np.linspace(0, len(values) * CPU_MEASURMENT_INTERVAL, len(values)), values, label=fn_name_abbr(fn))
        plt.ylabel("CPU %")
        plt.xlabel("seconds")
        plt.legend()
        plt.tight_layout()
        return fig


class MemoryUseMean(namedtuple('MemoryUseMean', field_names=('n', 'values')), NMeansTupleData):
    pass


class MemoryUseRegistry(PerformanceRegistry):

    def purge(self):
        for k in self.keys():
            self[k] = MemoryUseMean.null()

    def cast(self):
        return {k: tuple(v) for k, v in self.items()}

    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        for k, v in historical.items():
            self[k] = self.get(k, MemoryUseMean.null()).update_from_historical(v)


def memory_measurment(metrics, pid, flag):
    process = [p for p in psutil.process_iter(['pid']) if p.pid == pid][0]
    metrics.put(process.memory_info().rss)
    while not flag.is_set():
        time.sleep(RSS_MEASURMENT_INTERVAL)
        metrics.put(process.memory_info().rss)


def calculate_change(i):
    i = [i[n] - i[0] for n in range(0, len(i))]
    return tuple(i)


class MemoryUse(SingleNestValueMetric):
    """
    This monitors rss:
        rss (aka “Resident Set Size”) is the non-swapped physical memory a process has used.
        On UNIX it matches “top“‘s RES column.
        On Windows this is an alias for wset field, and it matches “Mem Usage” column of taskmgr.exe.

    """
    PRIMARY_REGISTRY = MemoryUseRegistry
    PRIMARY_REGISTRY_DEFAULT = MemoryUseMean.null

    def decorator(self, fn):
        template = fn_name_template(fn)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            fn_name = template.format(pull_self(args))
            # setup
            pid = psutil.Process().pid
            with multiprocessing.Manager() as manager:
                flag = manager.Event()
                flag.clear()
                q = manager.Queue()
                # calculate
                p = multiprocessing.Process(target=memory_measurment, args=(q, pid, flag))
                p.start()
                result = fn(*args, **kwargs)
                flag.set()
                p.join()
                m = []
                while not q.empty():
                    m.append(q.get())
                m = calculate_change(m)
                self.registry[fn_name] = self.registry[fn_name].update_from_historical(MemoryUseMean(1, m))
                return result
        return wrapper

    def serialize(self):
        return self.registry.cast()

    @classmethod
    def load(cls, d):
        metric = cls()
        for fn, perfs in d.items():
            n, values = perfs
            metric.registry[fn] = MemoryUseMean(n, values)
        return metric

    def plot(self):
        fig = plt.Figure()
        for fn, v in self.registry.items():
            n, values = v
            plt.plot(np.linspace(0, len(values) * RSS_MEASURMENT_INTERVAL, len(values)), values, label=fn_name_abbr(fn))
        plt.ylabel("bytes")
        plt.xlabel("seconds")
        plt.legend()
        plt.tight_layout()
        return fig


AVALIABLE = (CpuUse, MemoryUse)
