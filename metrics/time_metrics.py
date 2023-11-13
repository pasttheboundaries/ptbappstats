import datetime
import time
from collections import namedtuple, defaultdict
from functools import wraps

from pandas import Period

from .base_metrics import (DictOfNumericsRegistry, Metric, fn_name__template, pull_self, DictOfDictRegistry,
                           UpdatableFromHistorical, validate_other_same_class, DoubleNestValueMetric, zero)

PERIODIC_FUNCTIONS = {
    'h': lambda x: Period(x, 'H').hour,
    'm': lambda x: Period(x, 'M').month,
    'd': lambda x: Period(x, 'D').day,
    'w': lambda x: Period(x, 'D').day_of_week
}

TIMELINE_FUNCTIONS = {  ## TODO
    'h': lambda x: Period(x, 'H').to_datetime64(),
    'm': lambda x: Period(x, 'M').date(),
    'd': lambda x: Period(x, 'D').date(),
    'w': lambda x: Period(x, 'D').date()
}


class PeriodicRegistry(DictOfDictRegistry):
    pass


class PeriodsTable(DictOfNumericsRegistry):
    pass


class PeriodicBase(DoubleNestValueMetric):
    PRIMARY_REGISTRY = PeriodicRegistry
    SECONDARY_REGISTRY = PeriodsTable
    SECONDARY_REGITRY_DEFAULT = zero
    PERIODIC_FUNCTION = PERIODIC_FUNCTIONS['h']

    def __init__(self):
        super().__init__()
        self._registry = self.PRIMARY_REGISTRY()

    def __call__(self):
        return self.decorated_namespace()

    def decorated_namespace(self):
        """

        """
        def decorator(fn):
            template = fn_name__template(fn)

            @wraps(fn)
            def wrapper(*args, **kwargs):

                fn_name = template.format(pull_self(args))
                try:
                    count_table = self.registry[fn_name]
                except KeyError:
                    count_table = self.registry[fn_name] = \
                        self.__class__.SECONDARY_REGISTRY(self.__class__.SECONDARY_REGITRY_DEFAULT)

                count_table[self.__class__.PERIODIC_FUNCTION(datetime.datetime.now())] += 1

                return fn(*args, **kwargs)

            return wrapper
        return decorator

    def serialize(self):
        return self.registry.cast()

    @classmethod
    def load(cls, d):
        metric = cls()
        for fn, count_table in d.items():
            reg_fn_count_tables = metric.registry[fn] = cls.SECONDARY_REGISTRY(cls.SECONDARY_REGITRY_DEFAULT)
            for period, n in count_table.items():
                reg_fn_count_tables[period] += n
        return metric


class TimelineBase(DoubleNestValueMetric):
    # TODO
    pass


class Hourly(PeriodicBase):
    PERIODIC_FUNCTION = PERIODIC_FUNCTIONS['h']


class Weekdaily(PeriodicBase):
    PERIODIC_FUNCTION = PERIODIC_FUNCTIONS['w']


class Daily(PeriodicBase):
    PERIODIC_FUNCTION = PERIODIC_FUNCTIONS['d']


class Monthly(PeriodicBase):
    PERIODIC_FUNCTION = PERIODIC_FUNCTIONS['m']


class PerformanceData(namedtuple('PerformanceData', field_names=('n', 'total', 'mean'))):
    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        n: int = self.n + historical.n
        total: int = self.total + historical.total
        mean: float = total / n
        return PerformanceData(n, total, mean)


class PerformanceRegistry(defaultdict):
    def __repr__(self):
        return f'PerformanceTable: {self.cast()}'

    def purge(self):
        for k in self.keys():
            self[k] = PerformanceData(0, 0, 0)

    def cast(self):
        return {k: tuple(v) for k, v in self.items()}

    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        for k, v in historical.items():
            self[k] = self.get(k, PerformanceData(0, 0, 0)).update_from_historical(v)


class Performance(Metric):
    """
    counts performance metric
    """
    def __init__(self,):
        super().__init__()
        self._registry = PerformanceRegistry(lambda: PerformanceData(0, 0, 0))

    def decorator(self, fn):
        template = fn_name__template(fn)

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


AVAILABLE = (Hourly, Weekdaily, Daily, Monthly, Performance)