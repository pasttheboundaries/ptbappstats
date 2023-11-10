import datetime
import inspect
import time
from collections import defaultdict, namedtuple
from functools import wraps
from typing import Protocol, Any
from pandas import Period


def fn_name__template(fn):
    if 'self' in inspect.signature(fn).parameters:
        return '.'.join((fn.__module__, '{}', fn.__name__))
    else:
        return '.'.join((fn.__module__, fn.__name__))


class Registry(Protocol):
    def cast(self) -> dict:
        ...

    def __setitem__(self, item, value) -> None:
        ...

    def __getitem__(self, item) -> Any:
        ...

    def update(self, m) -> None:
        ...


class Metric:

    """
    Base class

    """
    def __init__(self, stats):
        self._registry: Registry
        self.stats = stats

    @property
    def registry(self):
        return getattr(self.stats, self.__class__.__name__)._registry

    def decorator(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        return wrapper

    def serialize(self):
        ...

    @classmethod
    def load(cls, stats, d):
        ...

    def __call__(self, fn):
        if not callable(fn):
            raise ValueError(f'Invalid decorator use. Metric must be used to decorate a function or method.')
        return self.decorator(fn)

    def __repr__(self):
        return f'{self.__class__.__name__}: {self.registry}'


def pull_self(args):
    try:
        return args[0].__class__.__name__
    except (IndexError, AttributeError):
        return ''


class CallCounts(defaultdict):
    def cast(self):
        return dict(self)

    def __repr__(self):
        return f'{self.__class__.__name__} :{self.cast()}'


class Count(Metric):
    """
    Counts calls
    """
    def __init__(self, stats):
        super().__init__(stats)
        self._registry = CallCounts(lambda: 0)

    def decorator(self, fn):
        template = fn_name__template(fn)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            fn_name = template.format(pull_self(args))
            self.registry[fn_name] += 1

            return fn(*args, **kwargs)
        return wrapper

    def serialize(self):
        return self.registry.cast()

    @classmethod
    def load(cls, stats, d):
        metric = cls(stats)
        setattr(stats, cls.__name__, metric)
        metric.registry.update(d)
        return metric


resolver_functions = {
    'h': lambda x: Period(x, 'H').hour,
    'm': lambda x: Period(x, 'M').month,
    'd': lambda x: Period(x, 'D').day,
    'w': lambda x: Period(x, 'D').day_of_week
}


class CallTimes(dict):  # fn: TimeTables
    def __setitem__(self, key, value) -> None:
        if not isinstance(key, str):
            raise TypeError(f'Illegal key type {type(key)}')
        if not isinstance(value, TimeTables):
            raise TypeError(f'CallTimes value must be TimeTables')
        super().__setitem__(key, value)

    def __repr__(self):
        return f'CallTimes: {self.cast()}'

    def cast(self):
        return {k: d.cast() for k, d in self.items()}


class TimeTables(dict):
    def __setitem__(self, key, value) -> None:
        if not isinstance(key, str) or key not in Times.ALLOWED:
            raise ValueError(f'Illegal key {key}')
        if not isinstance(value, TimesTable):
            raise TypeError(f'CallTimes value must be dict')
        super().__setitem__(key, value)

    def cast(self):
        return {k: d.cast() for k, d in self.items()}

    def __repr__(self):
        return f'TaimeTables: {self.cast()}'


class TimesTable(defaultdict):  # 22: 234

    def __setitem__(self, key, value):
        if isinstance(key, str) and key.isdigit():
            key = int(key)
        elif isinstance(key, int):
            pass
        else:
            raise ValueError(f'Invalid key {key}.')
        if not isinstance(value, int):
            raise TypeError(f'TimesTable value must be int.')
        super().__setitem__(key, value)

    def __repr__(self):
        return f'TimesTable: {self.cast()}'

    def cast(self):
        return dict(self)


class Times(Metric):
    """
    Count call times with predefined resolution

    """
    DEFAULT_RESOLUTION = 'h'
    ALLOWED = 'mdwh'

    def __init__(self, stats):
        super().__init__(stats)
        self._registry = CallTimes()
        self.time_tables = None

    def __call__(self, resolution=DEFAULT_RESOLUTION):
        if resolution not in self.ALLOWED:
            raise ValueError(f'resolution must be one of: {tuple(self.ALLOWED)}')
        return self.decorated_namespace(resolution)

    def decorated_namespace(self, resolution):

        def decorator(fn):
            template = fn_name__template(fn)
            times_table_initial = TimesTable(lambda: 0)

            @wraps(fn)
            def wrapper(*args, **kwargs):
                _time = resolver_functions[resolution](datetime.datetime.now())
                fn_name = template.format(pull_self(args))
                try:
                    times_table = self.registry[fn_name][resolution]
                except KeyError:
                    self.registry[fn_name] = TimeTables()
                    times_table = self.registry[fn_name][resolution] = times_table_initial
                times_table[_time] += 1
                return fn(*args, **kwargs)

            return wrapper
        return decorator

    def serialize(self):
        return self.registry.cast()

    @classmethod
    def load(cls, stats, d):
        metric = cls(stats)
        setattr(stats, cls.__name__, metric)
        for fn, time_tables in d.items():
            reg_fn_time_tables = metric.registry[fn] = TimeTables()
            for resolution, timetable in time_tables.items():
                reg_fn_time_tables[resolution] = TimesTable(lambda: 0)
                for t, n in timetable.items():
                    reg_fn_time_tables[resolution][t] += n
        return metric


class PerformanceData(namedtuple('PerformanceData', field_names=('n', 'total', 'mean'))):
    pass


class PerformaceTable(defaultdict):
    def __repr__(self):
        return f'PerformanceTable: {self.cast()}'

    def cast(self):
        return {k: tuple(v) for k, v in self.items()}


class Performance(Metric):
    """
    counts performance metric
    """
    def __init__(self, stats):
        super().__init__(stats)
        self._registry = PerformaceTable(lambda: PerformanceData(0, 0, 0))

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
    def load(cls, stats, d):
        metric = cls(stats)
        setattr(stats, cls.__name__, metric)
        for fn, perfs in d.items():
            # old = metric.registry[fn]
            loaded_n, loaded_total, loaded_mean = perfs
            # n = old.n + loaded_n
            # total = old.total + loaded_total
            # mean = old.mean + loaded_mean
            metric.registry[fn] = PerformanceData(loaded_n, loaded_total, loaded_mean)
        return metric


class ResultCounts(dict):
    def __setitem__(self, key, value) -> None:
        if not isinstance(key, str):
            raise TypeError(f'Illegal key type {type(key)}')
        if not isinstance(value, CountTable):
            raise TypeError(f'ResultCounts value must be CountTable')
        super().__setitem__(key, value)

    def __repr__(self):
        return f'ResultCounts: {self.cast()}'

    def cast(self):
        return {k: d.cast() for k, d in self.items()}


class CountTable(defaultdict):  # 22: 234

    def __setitem__(self, key, value):
        if not isinstance(value, int):
            raise TypeError(f'TimesTable value must be int.')
        super().__setitem__(key, value)

    def __repr__(self):
        return f'CountTable: {self.cast()}'

    def cast(self):
        return dict(self)


class CountResults(Metric):
    """
    Count call times with predefined resolution

    """

    def __init__(self, stats):
        super().__init__(stats)
        self._registry = ResultCounts()
        self.result_tables = None

    def __call__(self, result, serialisation=str):
        try:
            serialisation(result)
        except TypeError:
            raise ValueError(f'Unable to serialise declared result. Declare a valid serialization method.')
        return self.decorated_namespace(result, serialisation)

    def decorated_namespace(self, expected_result, serialisation):
        serialized = serialisation(expected_result)

        def decorator(fn):
            template = fn_name__template(fn)

            @wraps(fn)
            def wrapper(*args, **kwargs):
                result = fn(*args, **kwargs)
                if result != expected_result:
                    return result

                fn_name = template.format(pull_self(args))

                try:
                    count_table = self.registry[fn_name]
                except KeyError:
                    count_table = self.registry[fn_name] = CountTable(lambda: 0)

                count_table[serialized] += 1
                return result

            return wrapper
        return decorator

    def serialize(self):
        return self.registry.cast()

    @classmethod
    def load(cls, stats, d):
        metric = cls(stats)
        setattr(stats, cls.__name__, metric)
        for fn, count_table in d.items():
            reg_fn_count_tables = metric.registry[fn] = CountTable(lambda: 0)
            for serialised, n in count_table.items():
                reg_fn_count_tables[serialised] += n

        return metric
