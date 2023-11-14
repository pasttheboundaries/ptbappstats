
from .base_metrics import (DictOfNumericsRegistry, DictOfDictRegistry, SingleNestValueMetric, DoubleNestValueMetric,
                           zero, pull_self, fn_name_template)
from functools import wraps


class CountRegistry(DictOfNumericsRegistry):
    pass


class Count(SingleNestValueMetric):
    """
    Counts calls
    """
    PRIMARY_REGISTRY = CountRegistry
    PRIMARY_REGISTRY_DEFAULT = lambda: 0


class CountResultsRegistry(DictOfDictRegistry):
    pass


class CountResultTable(DictOfNumericsRegistry):
    pass


class CountResults(DoubleNestValueMetric):
    PRIMARY_REGISTRY = CountResultsRegistry
    SECONDARY_REGISTRY = CountResultTable
    SECONDARY_REGITRY_DEFAULT = zero

    def __call__(self, result, serialisation=str):
        try:
            serialisation(result)
        except TypeError:
            raise ValueError(f'Unable to serialise declared result. Declare a valid serialization method.')
        return self.decorated_namespace(result, serialisation)

    def decorated_namespace(self, expected_result, serialisation):

        serialized = serialisation(expected_result)

        def decorator(fn):
            template = fn_name_template(fn)

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


AVALIABLE = (CountResults, Count)
