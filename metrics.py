import datetime
import inspect
import time
from collections import defaultdict, namedtuple
from functools import wraps
from typing import Protocol, Any
from pandas import Period
from typing import TypeVar


def validate_other_same_class(self, other):
    if not isinstance(other, self.__class__):
        raise TypeError(f'Could not update_from_historical {self.__class__} with: {other.__class__}')


def pull_self(args):
    try:
        return args[0].__class__.__name__
    except (IndexError, AttributeError):
        return ''


def fn_name__template(fn):
    if 'self' in inspect.signature(fn).parameters:
        return '.'.join((fn.__module__, '{}', fn.__name__))
    else:
        return '.'.join((fn.__module__, fn.__name__))


MetricType = TypeVar('MetricType')


class UpdatableFromHistorical:
    pass


class UpdatableFromHistoricalDictOfDicts(UpdatableFromHistorical):
    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        for k, v in historical.items():
            if self.get(k, None) is None:
                self[k] = v
            else:
                if isinstance(self[k], UpdatableFromHistorical):
                    self[k].update_from_historical(v)
                else:
                    pass


class UpdatableFromHistoricalDictOfValues(UpdatableFromHistorical):
    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        for k, v in historical.items():
            self[k] += v


class Registry(Protocol):
    def cast(self) -> dict:
        ...

    def __setitem__(self, item, value) -> None:
        ...

    def __getitem__(self, item) -> Any:
        ...

    def update(self, m) -> None:
        ...

    def update_from_historical(self):
        ...

    def purge(self):
        ...


class Metric:
    """
    Base class

    """
    def __init__(self) -> None:
        """must instantiate self._registry"""
        ...
        self._registry = None

    @property
    def registry(self):
        return self._registry

    def decorator(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        return wrapper

    def serialize(self):
        ...

    def purge(self):
        self.registry.purge()

    @classmethod
    def load(cls, d) -> MetricType:
        ...

    def update_from_historical(self, historical: MetricType) -> MetricType:
        validate_other_same_class(self, historical)
        self._registry.update_from_historical(historical._registry)
        return self

    def __call__(self, fn):
        if not callable(fn):
            raise ValueError(f'Invalid decorator use. Metric must be used to decorate a function or method.')
        return self.decorator(fn)

    def __repr__(self):
        return f'{self.__class__.__name__}: {self.registry}'


class CountRegistry(defaultdict, UpdatableFromHistoricalDictOfValues):
    def cast(self):
        return dict(self)

    def purge(self):
        keys = tuple(self.keys())
        for k in keys:
            del self[k]

    def __repr__(self):
        return f'{self.__class__.__name__} :{self.cast()}'


class Count(Metric):
    """
    Counts calls
    """
    def __init__(self) -> None:
        super().__init__()
        self._registry = CountRegistry(lambda: 0)

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
    def load(cls, d) -> MetricType:
        metric = cls()
        metric._registry.update(d)
        return metric


resolver_functions = {
    'h': lambda x: Period(x, 'H').hour,
    'm': lambda x: Period(x, 'M').month,
    'd': lambda x: Period(x, 'D').day,
    'w': lambda x: Period(x, 'D').day_of_week
}


class TimesRegistry(dict, UpdatableFromHistoricalDictOfDicts):  # fn: TimeTables
    def __setitem__(self, key, value) -> None:
        if not isinstance(key, str):
            raise TypeError(f'Illegal key type {type(key)}')
        if not isinstance(value, TimeTables):
            raise TypeError(f'TimesRegistry value must be TimeTables')
        super().__setitem__(key, value)

    def __repr__(self):
        return f'TimesRegistry: {self.cast()}'

    def purge(self):
        for k, v in self.items():
            v.purge()

    def cast(self):
        return {k: d.cast() for k, d in self.items()}


class TimeTables(dict, UpdatableFromHistoricalDictOfDicts):
    def __setitem__(self, key, value) -> None:
        if not isinstance(key, str) or key not in Times.ALLOWED:
            raise ValueError(f'Illegal key {key}')
        if not isinstance(value, TimeTable):
            raise TypeError(f'TimesRegistry value must be dict')
        super().__setitem__(key, value)

    def purge(self):
        for k, v in self.items():
            v.purge()

    def cast(self):
        return {k: d.cast() for k, d in self.items()}

    def __repr__(self):
        return f'TaimeTables: {self.cast()}'


class TimeTable(defaultdict, UpdatableFromHistoricalDictOfValues):  # 22: 234

    def __setitem__(self, key, value):
        if isinstance(key, str) and key.isdigit():
            key = int(key)
        elif isinstance(key, int):
            pass
        else:
            raise ValueError(f'Invalid key {key}.')
        if not isinstance(value, int):
            raise TypeError(f'TimeTable value must be int.')
        super().__setitem__(key, value)

    def purge(self):
        keys = tuple(self.keys())
        for k in keys:
            del self[k]

    def __repr__(self):
        return f'TimeTable: {self.cast()}'

    def cast(self):
        return dict(self)


class Times(Metric):
    """
    Counts call times with predefined resolution

    """
    DEFAULT_RESOLUTION = 'h'
    ALLOWED = 'mdwh'

    def __init__(self) -> None:
        super().__init__()
        self._registry = TimesRegistry()
        self.time_tables = None

    def __call__(self, resolution=DEFAULT_RESOLUTION):
        if resolution not in self.ALLOWED:
            raise ValueError(f'resolution must be one of: {tuple(self.ALLOWED)}')
        return self.decorated_namespace(resolution)

    def decorated_namespace(self, resolution):

        def decorator(fn):
            template = fn_name__template(fn)
            times_table_initial = TimeTable(lambda: 0)

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
    def load(cls, d) -> MetricType:
        metric = cls()
        for fn, time_tables in d.items():
            metric.registry[fn] = TimeTables()
            for resolution, timetable in time_tables.items():
                metric.registry[fn][resolution] = TimeTable(lambda: 0)
                for t, n in timetable.items():
                    metric.registry[fn][resolution][t] += n
        return metric


class PerformanceData(namedtuple('PerformanceData', field_names=('n', 'total', 'mean')), UpdatableFromHistorical):
    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        n: int = self.n + historical.n
        total: int = self.total + historical.total
        mean: float = total / n
        return PerformanceData(n, total, mean)


class PerformaceRegistry(defaultdict, UpdatableFromHistorical):
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
        self._registry = PerformaceRegistry(lambda: PerformanceData(0, 0, 0))

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


class CountResultsRegistry(dict, UpdatableFromHistoricalDictOfDicts):
    def __setitem__(self, key, value) -> None:
        if not isinstance(key, str):
            raise TypeError(f'Illegal key type {type(key)}')
        if not isinstance(value, CountResultTable):
            raise TypeError(f'CountResultsRegistry value must be CountResultTable')
        super().__setitem__(key, value)

    def purge(self):
        for k, v in self.items():
            v.purge()

    def __repr__(self):
        return f'CountResultsRegistry: {self.cast()}'

    def cast(self):
        return {k: d.cast() for k, d in self.items()}


class CountResultTable(defaultdict, UpdatableFromHistoricalDictOfValues):

    def __setitem__(self, key, value):
        if not isinstance(value, int):
            raise TypeError(f'TimeTable value must be int.')
        super().__setitem__(key, value)

    def __repr__(self):
        return f'CountResultTable: {self.cast()}'

    def cast(self):
        return dict(self)

    def purge(self):
        keys = tuple(self.keys())
        for k in keys:
           del self[k]


class CountResults(Metric):
    """
    Count call times with predefined resolution

    """

    def __init__(self):
        super().__init__()
        self._registry = CountResultsRegistry()
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
                    count_table = self.registry[fn_name] = CountResultTable(lambda: 0)

                count_table[serialized] += 1
                return result

            return wrapper
        return decorator

    def serialize(self):
        return self.registry.cast()

    @classmethod
    def load(cls, d):
        metric = cls()
        for fn, count_table in d.items():
            reg_fn_count_tables = metric.registry[fn] = CountResultTable(lambda: 0)
            for serialised, n in count_table.items():
                reg_fn_count_tables[serialised] += n

        return metric
