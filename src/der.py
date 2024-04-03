import datetime
import shutil
import default
import helpers
import os

# TODO: Test horizon extension
start = datetime.datetime(2020, 9, 1, 5, 10)
predispatch_start = default.get_predispatch_time(start)

times = [predispatch_start + j * default.THIRTY_MIN for j in range(2, helpers.get_total_intervals('predispatch', predispatch_start))]

end_time = start + default.ONE_DAY - default.FIVE_MIN
extend_time = end = times[-1]
if extend_time < end_time:
    # 30min-based
    while end_time - extend_time > default.THIRTY_MIN:
        extend_time += default.THIRTY_MIN
        times.append(extend_time)
    # # 5min-based
    # while extend_time <= end_time:
    #     extend_time += default.FIVE_MIN
    #     times.append(extend_time)
    print(1)
    print(times)
elif extend_time > end_time:
    while extend_time >= end_time + default.THIRTY_MIN:
        times.pop()
        extend_time = times[-1]
    times[-1] = min(extend_time, end_time)
    end = None
    print('2')
    print(times)
