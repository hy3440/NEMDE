import dispatch
import datetime
import default
import multiprocessing as mp
import logging


def apply_multiprocess_dispatch(s):
    process_type = 'p5min'
    intervals_per_process = 72
    cvp, voll, market_price_floor = dispatch.prepare(s)
    for m in range(intervals_per_process):
        t = s + m * (default.THIRTY_MIN if process_type == 'predispatch' else default.FIVE_MIN)
        if process_type == 'dispatch':
            dispatch.dispatch(start=t, interval=0, process=process_type, cvp=cvp, voll=voll,
                              market_price_floor=market_price_floor, dispatchload_flag=False)
        else:
            dispatch.get_all_dispatch(t, process_type, cvp=cvp, voll=voll, market_price_floor=market_price_floor)


if __name__ == '__main__':
    total_hours = 24
    start_datetime = datetime.datetime(2020, 9, 1, 4, 5)
    logging.basicConfig(filename=default.LOG_DIR / 'multiprocess.log', filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)
    num_cores = int(mp.cpu_count())
    print(num_cores)
    # times = [start_datetime + i * datetime.timedelta(hours=(total_hours/num_cores)) for i in range(num_cores)]
    # with mp.Pool(4) as pool:
    #     pool.map(apply_multiprocess_dispatch, times)
    # pool.close()
    # pool.join()



