
from .base_metrics import (DictOfNumericsRegistry, DictOfDictRegistry, SingleNestValueMetric, DoubleNestValueMetric,
                           zero)


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


AVALIABLE = (CountResults, Count)
