import multiprocessing
from collections import namedtuple
from functools import wraps

import numpy as np
import psutil
from matplotlib import pyplot as plt
from time_metrics import PerformanceRegistry

from .base_metrics import SingleNestValueMetric, fn_name__template, validate_other_same_class, pull_self

CPU_MEASURMENT_INTERVAL = 0.1


class CPUMeanUsePair(namedtuple('CPUMeanUsePair', field_names=('n', 'values'))):
    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        historical_n, historical_values = historical
        new_arr = np.array(historical_values)
        current_n, current_arr = self
        current_arr = np.array(current_arr)
        length = max(len(new_arr), len(current_arr))
        new_arr.resize(length)
        current_arr.resize(length)

        new_mean = tuple(((current_n * current_arr) + (historical_n * new_arr)) / (current_n + historical_n))
        new_n = self.n + 1
        return CPUMeanUsePair(new_n, new_mean)


class CPUUseRegistry(PerformanceRegistry):
    def __repr__(self):
        return f'PerformanceTable: {self.cast()}'

    def purge(self):
        for k in self.keys():
            self[k] = CPUMeanUsePair(0, (0,))

    def cast(self):
        return {k: tuple(v) for k, v in self.items()}

    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        for k, v in historical.items():
            self[k] = self.get(k, CPUMeanUsePair(0, (0,))).update_from_historical(v)


def measurment(metrics, pid, flag):
    process = [p for p in psutil.process_iter(['pid']) if p.pid == pid][0]
    while not flag.is_set():
        metrics.put(process.cpu_percent(interval=CPU_MEASURMENT_INTERVAL))
    return metrics


class CPUUse(SingleNestValueMetric):
    """
    CPU use is sampled every 0.1 sec (CPU_MEASURMENT_INTERVAL)
    For functions faster than this resolution metric might collect useless values.
    """
    PRIMARY_REGISTRY = CPUUseRegistry
    PRIMARY_REGISTRY_DEFAULT = lambda: CPUMeanUsePair(0, (0,))

    def decorator(self, fn):
        template = fn_name__template(fn)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            fn_name = template.format(pull_self(args))
            # old_n, old_values = self.registry[fn_name]
            # setup
            pid = psutil.Process().pid
            flag = multiprocessing.Event()
            flag.clear()
            metrics = multiprocessing.Queue()
            # calculate
            p = multiprocessing.Process(target=measurment, args=(metrics, pid, flag))
            p.start()
            result = fn(*args, **kwargs)
            flag.set()
            p.join()
            m = []
            while not metrics.empty():
                m.append(metrics.get())
            self.registry[fn_name] = self.registry[fn_name].update_from_historical(CPUMeanUsePair(1, tuple(m)))
            return result
        return wrapper

    def serialize(self):
        return self.registry.cast()

    @classmethod
    def load(cls, d):
        metric = cls()
        for fn, perfs in d.items():
            n, values = perfs
            metric.registry[fn] = CPUMeanUsePair(n, values)
        return metric

    def plot(self):
        fig = plt.Figure()
        labels = []
        for k, v in self.registry.items():
            n, values = v
            plt.plot(np.linspace(0, len(values) * CPU_MEASURMENT_INTERVAL, len(values)), values, label=k.split('.')[-1])
            labels.append(k)
        plt.ylabel("CPU %")
        plt.xlabel("seconds")
        plt.legend()
        return fig


AVALIABLE = (CPUUse,)
