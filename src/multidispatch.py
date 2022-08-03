import dispatch
import datetime
import default
import multiprocessing as mp
import time
import preprocess
from itertools import repeat


def apply_multiprocess_dispatch(s, intervals_per_process, process_type):
    path_to_out = default.OUT_DIR / 'record'
    for m in range(intervals_per_process):
        t = s + m * (default.THIRTY_MIN if process_type == 'predispatch' else default.FIVE_MIN)
        if process_type == 'dispatch':
            dispatch.formulate(start=t, interval=0, process=process_type, path_to_out=path_to_out,
                               dispatchload_flag=False)
        else:
            dispatch.get_all_dispatch(t, process_type, path_to_out)


def multiformulate(start_datetime, process_type, num_usage, download_flag=False):
    if process_type == 'dispatch':
        if download_flag:
            preprocess.download_dispatch_summary(start_datetime, True)
            # preprocess.download_xml(start_datetime, True)
        preprocess.download_dispatch_summary(start_datetime + default.ONE_DAY, True)
    elif process_type == 'p5min':
        if download_flag:
            preprocess.download_5min_predispatch(start_datetime, True)
        preprocess.download_5min_predispatch(start_datetime + default.ONE_DAY, True)
    elif process_type == 'predispatch':
        preprocess.download_predispatch(start_datetime, True)
        preprocess.download_xml(start_datetime + default.ONE_DAY, True)
    intervals_per_day = 48 if process_type == 'predispatch' else 288
    intervals_per_process = int(intervals_per_day / num_usage)
    minutes_per_process = intervals_per_process * (30 if process_type == 'predispatch' else 5)
    times = [start_datetime + i * datetime.timedelta(minutes=minutes_per_process) for i in range(num_usage)]
    # start = datetime.datetime(2021, 7, 20, 1, 0)
    # end = datetime.datetime(2021, 7, 21, 4, 5)
    # times = [start + default.FIVE_MIN * i for i in range(37)]
    # intervals_per_process = 1
    with mp.Pool(len(times)) as pool:
        pool.starmap(apply_multiprocess_dispatch, zip(times, repeat(intervals_per_process), repeat(process_type)))
    pool.close()
    pool.join()


def multiformulate_sequence_batteries():
    start_timeit = time.time()
    energies = [30, 3000]
    # energies = [150, 300, 600, 1500, 3000]
    with mp.Pool(len(energies)) as pool:
        pool.map(dispatch.formulate_sequence, energies)
    print("--- %s ---" % (time.time() - start_timeit))


if __name__ == '__main__':
    process_type = 'p5min'
    start_datetime = datetime.datetime(2021, 7, 19, 4, 30 if process_type == 'predispatch' else 5)
    num_usage = 16
    multiformulate(start_datetime, process_type, num_usage)
    # multiformulate_sequence_batteries()
