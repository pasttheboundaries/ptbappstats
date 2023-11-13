
import inspect
from collections import defaultdict
from functools import wraps
from typing import Protocol, Any
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


def zero():
    return 0


MetricType = TypeVar('MetricType')


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


class DictOfNumericsRegistry(defaultdict):

    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        for k, v in historical.items():
            self[k] += v

    def cast(self):
        return dict(self)

    def purge(self):
        keys = tuple(self.keys())
        for k in keys:
            del self[k]

    def __repr__(self):
        return f'{self.__class__.__name__} :{self.cast()}'


class DictOfDictRegistry(dict):
    def __setitem__(self, key, value) -> None:
        if not isinstance(key, str):
            raise TypeError(f'Illegal key type {type(key)}. Key must be string.')
        if not isinstance(value, dict):
            raise TypeError(f'{self.__class__.__name__} value must be dict type')
        super().__setitem__(key, value)

    def __repr__(self):
        return f'{self.__class__.__name__}: {self.cast()}'

    def update_from_historical(self, historical):
        validate_other_same_class(self, historical)
        for k, v in historical.items():
            if self.get(k, None) is None:
                self[k] = v
            else:
                if isinstance(self[k], dict):
                    self[k].update_from_historical(v)
                else:
                    pass

    def purge(self):
        for k, v in self.items():
            v.purge()

    def cast(self):
        return {k: d.cast() for k, d in self.items()}


class SingleNestValueMetric(Metric):
    """
    Counts calls
    """
    PRIMARY_REGISTRY = DictOfNumericsRegistry
    PRIMARY_REGISTRY_DEFAULT = zero

    def __init__(self) -> None:
        super().__init__()
        self._registry = self.__class__.PRIMARY_REGISTRY(self.__class__.PRIMARY_REGISTRY_DEFAULT)

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
        if not isinstance(d, dict):
            raise TypeError(f'Could not load {type(d)}')
        metric = cls()
        metric._registry.update(d)
        return metric


class DoubleNestValueMetric(Metric):
    """
    Count call times with predefined resolution

    """
    PRIMARY_REGISTRY = DictOfNumericsRegistry
    PRIMARY_REGITRY_DEFAULT = lambda: dict()
    SECONDARY_REGISTRY = DictOfNumericsRegistry
    SECONDARY_REGITRY_DEFAULT = zero

    def __init__(self):
        super().__init__()
        self._registry = self.PRIMARY_REGISTRY()

    def __call__(self, result, serialisation=str):
        try:
            serialisation(result)
        except TypeError:
            raise ValueError(f'Unable to serialise declared result. Declare a valid serialization method.')
        return self.decorated_namespace(result, serialisation)

    def decorated_namespace(self, expected_result, serialisation):
        """
        TODO this is not generic !!!
        """

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
                    count_table = self.registry[fn_name] = self.__class__.SECONDARY_REGISTRY(self.__class__.SECONDARY_REGITRY_DEFAULT)

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
            reg_fn_count_tables = metric.registry[fn] = cls.SECONDARY_REGISTRY(cls.SECONDARY_REGITRY_DEFAULT)
            for serialised, n in count_table.items():
                reg_fn_count_tables[serialised] += n

        return metric


# def dummy_tertiary_dict_key(secondary_dict_key):
#     return secondary_dict_key

#
# class TripleNestValueMetric(Metric):
#     """
#     Base class
#     Secondary dict key is to be set during decoration time.
#     This will decide about the tertiary dict key resolution method.
#     Tertiary_dict_key is derived from secondary dict key.
#     secondary_dict_key will be passed to TERTIARY_DICT_KEY_PROXY callable to obtain the tertiary_dict_key.
#
#     This organises the metric so:
#      - the registry primary dict holds method relevant secondary dicts
#      - the registry secondary dict holds the metric type relevant dicts
#      - the registry tertiary dict holds the metric values relevant to the circumstances defined by the secondary
#
#     """
#     PRIMARY_REGISTRY = DictOfDictRegistry
#     SECONDARY_REGISTRY = DictOfDictRegistry
#     TERTIARY_DICT_KEY_PROXY = dummy_tertiary_dict_key
#     TERTIARY_REGISTRY = DictOfNumericsRegistry
#     TERTIARY_REGISTRY_DEFAULT = zero
#     DEFAULT_SECONDARY_DICT_KEY = None
#
#     def __init__(self) -> None:
#         super().__init__()
#         self._registry = self.__class__.PRIMARY_REGISTRY()
#         self.time_tables = None
#
#     def __call__(self, resolution=DEFAULT_SECONDARY_DICT_KEY):
#         return self.decorated_namespace(resolution)
#
#     def decorated_namespace(self, secondary_dict_k):
#
#         def decorator(fn):
#             template = fn_name__template(fn)
#             times_table_initial = self.__class__.TERTIARY_REGISTRY(self.__class__.TERTIARY_REGISTRY_DEFAULT)
#
#             @wraps(fn)
#             def wrapper(*args, **kwargs):
#                 tertiary_dict_key = self.__class__.TERTIARY_DICT_KEY_PROXY(secondary_dict_k)
#                 fn_name = template.format(pull_self(args))
#                 try:
#                     times_table = self.registry[fn_name][secondary_dict_k]
#                 except KeyError:
#                     self.registry[fn_name] = self.__class__.SECONDARY_REGISTRY()
#                     times_table = self.registry[fn_name][secondary_dict_k] = times_table_initial
#
#                 times_table[tertiary_dict_key] += 1
#                 return fn(*args, **kwargs)
#
#             return wrapper
#         return decorator
#
#     def serialize(self):
#         return self.registry.cast()
#
#     @classmethod
#     def load(cls, d) -> MetricType:
#         metric = cls()
#         for fn, time_tables in d.items():
#             metric.registry[fn] = cls.SECONDARY_REGISTRY()
#             for resolution, timetable in time_tables.items():
#                 metric.registry[fn][resolution] = cls.TERTIARY_REGISTRY(lambda: 0)
#                 for t, n in timetable.items():
#                     metric.registry[fn][resolution][t] += n
#                     metric.registry[fn][resolution][t] += n
#         return metric
