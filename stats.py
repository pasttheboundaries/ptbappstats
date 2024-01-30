
"""
appstat = Stats()

appstat.Count
appstat.Performance
appstat.Times
appstat.CountResults

"""

import json
from typing import Any
from functools import wraps
from filelock import FileLock


from .metrics import sys_metrics, time_metrics, count_metrics
from .metrics.base_metrics import Metric

AVAILABLE_METRICS = {m.__name__: m for m in count_metrics.AVALIABLE}
AVAILABLE_METRICS.update({m.__name__: m for m in sys_metrics.AVALIABLE})
AVAILABLE_METRICS.update({m.__name__: m for m in time_metrics.AVAILABLE})


def read_json_file(path: str):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.loads(f.read(), cls=StatsDecoder)
    except FileNotFoundError:
        raise


class Stats:

    def __init__(self):
        self.metric_names = []

    @property
    def registry(self):
        return {name: self.__getattribute__(name).registry for name in self.metric_names}

    def __getattr__(self, item):
        try:
            return self.__getattribute__(item)
        except AttributeError:
            if item in AVAILABLE_METRICS:
                setattr(self, item, AVAILABLE_METRICS[item]())
                metric = self.__getattribute__(item)
                self.metric_names.append(item)
                return metric
            else:
                raise

    def serialize(self):
        registry = {k: dict(metric) for k, metric in self.registry.items()}
        return json.dumps(registry, cls=StatsEncoder)

    def dump(self, path, update: bool = True, purge: bool = True):
        with FileLock(path + '.lock'):
            if update:
                try:
                    self.update_from_historical(path)
                except FileNotFoundError:
                    pass
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.serialize())
            if purge:
                self.purge()

    def _load_dumped(self, path: str):
        j = read_json_file(path)

        for metric_name, metric_data in j.items():
            if metric_name in AVAILABLE_METRICS:
                metric_cls = AVAILABLE_METRICS[metric_name]
                metric = metric_cls.load(metric_data)
                setattr(self, metric_name, metric)
                self.metric_names.append(metric_name)
            else:
                pass

    def update_from_historical(self, path: str):
        loaded_stats = Stats()
        loaded_stats._load_dumped(path)
        for metric_name in self.metric_names:  # update owned metrics only
            self_metric = getattr(self, metric_name)
            try:
                loaded_metric_data = loaded_stats.__getattribute__(metric_name)
                self_metric.update_from_historical(loaded_metric_data)
            except AttributeError:
                pass
        return self

    def send(self, url, method='POST'):
        from requests import Request, Session
        r = Request(method, url, data=self.registry)
        r = r.prepare()
        s = Session()
        resp = s.send(r)
        return resp

    def purge(self):
        for metric_name in self.metric_names:
            metric = getattr(self, metric_name)
            metric.purge()
        return self

    @classmethod
    def read(cls, path):
        ros = ReadOnlyStats()
        ros._load_dumped(path)
        return ros

    def Dump(self, path, update=True, purge=True):
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                try:
                    result = fn(*args, **kwargs)
                except:
                    result = None
                finally:
                    self.dump(path, update=update, purge=purge)
                return result
            return wrapper
        return decorator

    def __getitem__(self, item):
        return self.registry[item]

    def __repr__(self):
        return f'{self.__class__.__name__}: {self.registry}'


class ReadOnlyStats(Stats):
    pass


class StatsEncoder(json.JSONEncoder):

    def __init__(self, *args, **kawrgs):
        super().__init__(*args, **kawrgs)

    def default(self, obj: Any):
        if isinstance(obj, Metric):
            idiomatic = obj.registry.cast()
            return idiomatic
        super().default(obj)


class StatsDecoder(json.JSONDecoder):

    def decode(self, o: str) -> Any:
        o = super().decode(o)
        if isinstance(o, str) and o.isdigit():
            return int(o)

        return o
