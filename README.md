#PTB app stats

to be used with application functions

Use:
```
# import Stats object
from ptbappstats import Stats

# define dump file path
path = '/path/to/the/dump/file'

# instantate Stats
stats = Stats(path)

# apply metric to the function you want to monitor
@stats.Times('d')
def my_func(*args, *kwargs):
    ...
```

metrics:

####Stats.Times(resolution)  
resolution: str - one of:  
 - m: month
 - d: day
 - w: week day
 - h: hour  

Records the time of call with declared time granularity

####Stats.Count  
Counts function calls

####Stats.CountResults(result, serialistion=str)
- result: Any
- serialisation: callable - must be able to transform result to jsonable type.  
This is necessary because the result param will be included in stats registry.

Counts function calls if the returned value == result

####Stats.Performace
will record function performance times

####Stats(path)
requires path to the dump file.  
methods:  
 - dump(): - dumps stats a file
 - load(): loads from a file. This shadows instnce data, so it is advised against loading into already working Stats.
 - serialize(): returns json serialized object
 - 
attributes
- Stats.registry: actual registry object
