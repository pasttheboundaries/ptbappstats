"""
appstat = Stats()

appstat.Count
appstat.Performance
appstat.Times
appstat.CountResults

"""


from . import metrics # metrics import Count, Times, Performance
import json
from typing import Any


TYPE_ANNOTATION = 'ptbappstats_type'


class Stats:
    def __init__(self, file: str):
        self.file = file
        self.Performance = metrics.Performance(self)
        self.Times = metrics.Times(self)
        self.Count = metrics.Count(self)
        self.CountResults = metrics.CountResults(self)

    @property
    def registry(self):
        return {
            'Performance': self.Performance.registry,
            'Times': self.Times.registry,
            'Count': self.Count.registry,
            'CountResults': self.CountResults.registry
        }

    def serialize(self):
        registry = {k: dict(metric) for k, metric in self.registry.items()}
        for name, metric_registry in registry.items():
            metric_registry.update({TYPE_ANNOTATION: getattr(self, name).__class__.__name__})
        return json.dumps(registry, cls=StatsEncoder)

    def dump(self):
        with open(self.file, 'w', encoding='utf-8') as f:
            f.write(self.serialize())

    def load(self):
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                j = json.loads(f.read(), cls=StatsDecoder)
        except FileNotFoundError:
            raise

        for metric_name, metric_data in j.items():
            if TYPE_ANNOTATION in metric_data:
                cls = getattr(metrics, metric_data[TYPE_ANNOTATION])
                del metric_data[TYPE_ANNOTATION]
                metric = cls.load(self, metric_data)
                # setattr(self, metric_name, metric)

            else:
                pass

    def __getitem__(self, item):
        return self.registry[item]

    def __repr__(self):
        return f'Stats: {self.registry}'


class StatsEncoder(json.JSONEncoder):

    def __init__(self, *args, **kawrgs):
        super().__init__(*args, **kawrgs)

    def default(self, obj: Any):
        if isinstance(obj, metrics.Metric):
            idiomatic = obj.registry.cast()
            idiomatic[TYPE_ANNOTATION] = obj.__class__.__name__
            return idiomatic
        super().default(obj)


class StatsDecoder(json.JSONDecoder):

    def decode(self, o: str) -> Any:
        o = super().decode(o)
        if isinstance(o, str) and o.isdigit():
            return int(o)

        return o
