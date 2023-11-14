
import inspect
from collections import defaultdict
from functools import wraps
from typing import Protocol, Any
from typing import TypeVar
from itertools import dropwhile


def validate_other_same_class(self, other):
    if not isinstance(other, self.__class__):
        raise TypeError(f'Could not update_from_historical {self.__class__} with: {other.__class__}')


def pull_self(args):
    try:
        return args[0].__class__.__name__
    except (IndexError, AttributeError):
        return ''


def fn_name_template(fn):
    if 'self' in inspect.signature(fn).parameters:
        return '.'.join((fn.__module__, '{}', fn.__name__))
    else:
        return '.'.join((fn.__module__, fn.__name__))


def zero():
    return 0


def fn_name_abbr(fn_name: str):
    return '.'.join(dropwhile(lambda x: x.startswith('_'), fn_name.split('.')))


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
        ...

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
        template = fn_name_template(fn)

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
    SECONDARY_REGISTRY = DictOfNumericsRegistry
    SECONDARY_REGITRY_DEFAULT = zero

    def __init__(self):
        super().__init__()
        self._registry = self.PRIMARY_REGISTRY()

    def __call__(self, *args, **kwargs):
        """
        This overrides Metric.__call__
        as this might vary in subclasses
        """
        ...

    def serialize(self):
        return self.registry.cast()

    @classmethod
    def load(cls, d):
        metric = cls()
        for fn_name, loaded_secondary_registry in d.items():
            self_secondary_registry = metric.registry[fn_name] = cls.SECONDARY_REGISTRY(cls.SECONDARY_REGITRY_DEFAULT)
            for key, n in loaded_secondary_registry.items():
                self_secondary_registry[key] += n

        return metric
