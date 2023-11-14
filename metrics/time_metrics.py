import datetime
import time
from collections import namedtuple, defaultdict
from functools import wraps
from math import ceil

import matplotlib.axes
from matplotlib import pyplot as plt
import matplotlib.ticker as mticker


from pandas import Period

from .base_metrics import (DictOfNumericsRegistry, fn_name_template, pull_self, DictOfDictRegistry,
                           validate_other_same_class, DoubleNestValueMetric, zero, SingleNestValueMetric, fn_name_abbr)

PERIODIC_FUNCTIONS = {
    'h': lambda x: Period(x, 'H').hour,
    'm': lambda x: Period(x, 'M').month,
    'd': lambda x: Period(x, 'D').day,
    'w': lambda x: Period(x, 'D').day_of_week
}

PERIODIC_X_TICKS ={
    'h': 24,
    'm': 12,
    'd': 31,
    'w': 7
}

TIMELINE_FUNCTIONS = {
    'h': lambda x: Period(x, 'H').start_time.strftime('%Y%m%dh%H'),
    'm': lambda x: Period(x, 'M').start_time.strftime('%Y%m'),
    'd': lambda x: Period(x, 'D').start_time.strftime('%Y%m%d'),
    'w': lambda x: Period(x, 'D').start_time.strftime('%Y%m%dw%W')
}


# Periodic -------------------------------
class PeriodicRegistry(DictOfDictRegistry):
    pass


class PeriodsTable(DictOfNumericsRegistry):
    pass


class PeriodicBase(DoubleNestValueMetric):
    """
    Periodic metrics monitor functions over defined periods
    (ie: over day hours, week days, month days, or year months)
    """
    PRIMARY_REGISTRY = PeriodicRegistry
    SECONDARY_REGISTRY = PeriodsTable
    SECONDARY_REGITRY_DEFAULT = zero
    TIME_TAG = 'h'
    TIME_STAMP_FUNCTIONS = PERIODIC_FUNCTIONS

    def __call__(self, fn):
        return self.decorator(fn)

    def decorator(self, fn):
        template = fn_name_template(fn)

        @wraps(fn)
        def wrapper(*args, **kwargs):

            fn_name = template.format(pull_self(args))
            try:
                count_table = self.registry[fn_name]
            except KeyError:
                count_table = self.registry[fn_name] = \
                    self.__class__.SECONDARY_REGISTRY(self.__class__.SECONDARY_REGITRY_DEFAULT)
            time_tag = self.__class__.TIME_TAG
            count_table[self.__class__.TIME_STAMP_FUNCTIONS[time_tag](datetime.datetime.now())] += 1

            return fn(*args, **kwargs)

        return wrapper

    def plot(self):
        k = len(self.registry)
        fig, axs = plt.subplots(k)
        if isinstance(axs, matplotlib.axes.Axes):
            axs = [axs]
        for ax, fn in zip(axs, tuple(self.registry.keys())):
            times = self.registry[fn]
            # x = []
            # y = []
            # maximum = max(tuple(times.keys()))
            # for i in range(maximum + 1):
            #     x.append(i)
            #     y.append(times.get(i, 0))
            x = tuple(times.keys())
            y = tuple(times.values())

            ax.bar(x, y, label=fn_name_abbr(fn))
            ax.xaxis.set_major_locator(mticker.AutoLocator())
            ax.yaxis.set_major_locator(mticker.MultipleLocator(ceil(max(y)/10)))
            ax.set_xticks(range(PERIODIC_X_TICKS[self.__class__.TIME_TAG]))
            ax.legend()
        plt.ylabel("n")
        plt.xlabel(self.__class__.__name__.lower())
        plt.tight_layout()
        return fig

    @classmethod
    def load(cls, d):
        """
        this is overwrites the original method because int must be applied to secondary dict key
        """
        metric = cls()
        for fn_name, loaded_secondary_registry in d.items():
            self_secondary_registry = metric.registry[fn_name] = cls.SECONDARY_REGISTRY(cls.SECONDARY_REGITRY_DEFAULT)
            for key, n in loaded_secondary_registry.items():
                self_secondary_registry[int(key)] += n

        return metric


class Hours(PeriodicBase):
    TIME_TAG = 'h'


class Weekdays(PeriodicBase):
    TIME_TAG = 'w'


class Days(PeriodicBase):
    TIME_TAG = 'd'


class Months(PeriodicBase):
    TIME_TAG = 'm'


# Timeline -----------------------------------
class TimelineRegistry(DictOfDictRegistry):
    pass


class TimelineTable(DictOfNumericsRegistry):
    pass


class TimelineBase(PeriodicBase):
    """
    Timeline metrics montior activity with a defined time resolution
    """
    PRIMARY_REGISTRY = TimelineRegistry
    SECONDARY_REGISTRY = TimelineTable
    SECONDARY_REGITRY_DEFAULT = zero
    TIME_STAMP_FUNCTIONS = TIMELINE_FUNCTIONS
    TIME_TAG = 'h'

    @classmethod
    def load(cls, d):
        """
        this is overwrites the original method because int must NOT be applied to secondary dict key
        """
        metric = cls()
        for fn_name, loaded_secondary_registry in d.items():
            self_secondary_registry = metric.registry[fn_name] = cls.SECONDARY_REGISTRY(cls.SECONDARY_REGITRY_DEFAULT)
            for key, n in loaded_secondary_registry.items():
                self_secondary_registry[key] += n

        return metric

class Hourly(TimelineBase):
    TIME_TAG = 'h'


class Daily(TimelineBase):
    TIME_TAG = 'd'


class Weekly(TimelineBase):
    TIME_TAG = 'w'


class Monthly(TimelineBase):
    TIME_TAG = 'm'


# Performance ------------------------------------
class PerformanceData(namedtuple('PerformanceData', field_names=('n', 'total', 'mean'))):
    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        n: int = self.n + historical.n
        total: int = self.total + historical.total
        mean: float = total / n
        return PerformanceData(n, total, mean)

    @classmethod
    def null(cls):
        return PerformanceData(0, 0, 0)


class PerformanceRegistry(defaultdict):
    def __repr__(self):
        return f'{self.__class__.__name__}: {self.cast()}'

    def purge(self):
        for k in self.keys():
            self[k] = PerformanceData.null()

    def cast(self):
        return {k: tuple(v) for k, v in self.items()}

    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        for k, v in historical.items():
            self[k] = self.get(k, PerformanceData.null()).update_from_historical(v)


class Performance(SingleNestValueMetric):
    """
    counts performance metric
    """
    PRIMARY_REGISTRY = PerformanceRegistry
    PRIMARY_REGISTRY_DEFAULT = PerformanceData.null

    def __init__(self,):
        super().__init__()
        self._registry = PerformanceRegistry(PerformanceData.null)

    def decorator(self, fn):
        template = fn_name_template(fn)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            fn_name = template.format(pull_self(args))
            old = self.registry[fn_name]
            t0 = time.perf_counter()
            result = fn(*args, **kwargs)
            t1 = time.perf_counter() - t0
            n = old.n + 1
            total = old.total + t1
            mean = total / n
            self.registry[fn_name] = PerformanceData(n, total, mean)
            return result
        return wrapper

    def serialize(self):
        return self.registry.cast()

    @classmethod
    def load(cls, d):
        metric = cls()
        for fn, perfs in d.items():
            loaded_n, loaded_total, loaded_mean = perfs
            metric.registry[fn] = PerformanceData(loaded_n, loaded_total, loaded_mean)
        return metric


AVAILABLE = (Hours, Days, Weekdays, Months, Hourly, Weekly, Daily, Monthly, Performance)