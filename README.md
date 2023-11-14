#PTB app stats

Application stats to be used with application functions.

Use:
```
# import Stats object
from ptbappstats import Stats

# define dump file path
path = '/path/to/the/dump/file'

# instantate Stats
stats = Stats()

# apply metric to the function you want to monitor
# function my_func will be monitored with Hourly
@stats.Hourly
def my_func(*args, *kwargs):
    ...

# function exit_function will be monitored with Count metric
# also stats data will be dumped and reset each time the exit_function returns
@stats.Dump(path, update=True, purge=True)
@stats.Count
def exit_function():
    ...

.
.
.    
```

#Stats decorators:
##Metrics:  
Metric decorators should be applied to functions or methods, to keep the functio(method) stats.


###Stats.Hourly()  
Records the history of function call times with 24 hourly granularity

###Stats.Daily()  
Records the history of function call times with daily granularity

###Stats.Weekly()  
Records the history of function call times with week granularity

###Stats.Monthly()  
Records the history of function call times with monthly granularity

###Stats.Hours()  
Aggregates the times of function calls with 24 hourly granularity

###Stats.Days()  
Aggregates the times of function calls with daily granularity

###Stats.Weekdays()  
Aggregates the times of function calls with week-days granularity

###Stats.Months()  
Aggregates the times of function calls with monthly granularity

###Stats.Count  
Counts function calls

###Stats.CountResults(result, serialistion=str)
- result: Any
- serialisation: callable - must be able to transform result to jsonable type.  
This is necessary because the result param will be included in stats registry.

Counts function calls if the returned value == result

###Stats.Performance
will record function performance times

###Stats.CpuUse
will record cpu percent use for monitored functions
Can plot the results

## other:
###Stats.Dump(path, update: bool = True, purge: bool = True)
This decorator will call Stats.dump after the function has returned.
dump and purge parameters: see Stats.dump (method).  
It is advised to keep the routine: dump with update mode on, 
and purge mode on, unless needed otherwise.

#Stats object:

###Stats()

####methods:  
 - purge(): zeroes all stats.
 - dump(path, update: bool = True): - dumps stats a file - 
this should be used to save current stats state.  
If update is set to True (default), 
stats object registry will be updated from file before dumped.  
update = False overwrites the filed data.
 - serialize(): returns json serialized object
 - update_from_historical(path): updates self metrics by the values from the file.  
This function adds (eg. number of function calls) and recalculates (eg. mean) 
stored metrics onto the current Stats counts and calculations. 
This means that multiple calls to this method will damage the stats.
<span style="color:red">**Make sure this is only called once!**</span> (usually before stats dump).  
There is no such thing as "load" (and re-use) stats.  
Stats are applied at compile-time as decorators, and can not be reapplied in the run-time.
For the purpose of reading saved file use plane python methods and json.loads or Stats.read.  
 - read(path): - reads dumped data and exposes a ReadOnlyStats object.


####attributes:  
 - Stats.registry: actual registry object
 

###ReadOnlyStats()

This is a dummy Stats class, solely for the purpose of showing stats in a human-readable form.
None of the metrics accessible from ReadOnlyStats instance is connected or overlooking any function, 
so as the run-time goes on none of the functions performance will be recorded in the ReadOnlyStats instance metrics.

#Advised routines:  
Stats are designed to be used in code. 
Decorators applied to coded functions will wrap the functions and apply Metric methods.  
This happens each time an app is started in a separate process.
It is understood that storing stats makes sense only with one of the following routines:

###1. Zero to Hero routine (default routine)
App starts countin stats each time it is started. 
Before stats get dumped to file, it is checked if the older file (of the same name) exists.
If there is previuos data saved, all datata: old and new, will be joined before save. 
Also current stats will be updated.
Note Currently working stats will only be updated at the time of dumping.
Dumping can be done at any time.
When stats data is dumped, Stats object restores itself and purges all data.
So it starts counting from zero but all previous data is saved (dumped to file).
<span style="color:lightblue">For this routine use update=True and purge=True. 
Use only stats.dump() as frequently as you need during the app runtime.</span> 
Those are default settings.

###2. Die hard routine:
Stats start from zero and continue untill app is closed.
Dumping overwrites the dump file each time it is saved.
It means progress is incrementally recorded BUT 
once the application is restarted, counting stats starts all over.
Next time the app is started and data is dumped - the dump file will be overwritten.
<span style="color:lightblue">For this routine use update=False, purge=False at dumping.
Use only stats.dump() as frequently as you need during the app runtime.</span>  

#Limitations:

1) Stats instances use decoration time to apply metrics.
This will be projected to the dump file.
If the code changes and one of the stat decorations is removed this will also cause disappearing the sstat from the dump file.
<span style="color:lightblue">Be sure to save a copy of the dump file before changing the code (before removing stats decorations).</span>
2) Periodic metrics gives some time overhead (about 1 sec / 100_000 calls). 
Which makes those metrics time costly for the monitoring functions 
that either need to be fast or need to be called frequently.
But at the same time they might be very usefull for monitoring user activity.
3) CpuUse and MemoryUse metrics are sampled every 0.1 sec.
For functions faster than this resolution, metric might collect useless values. 
Also this metric measures only the kernel process that performs the function calculations, 
but not the children porcesses.

