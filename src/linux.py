import dispatch
import datetime
import default
import multiprocessing as mp
import logging


def apply_multiprocess_predispatch(s):
    process = 'predispatch'
    n = 8
    cvp, voll, market_price_floor = dispatch.prepare(s)
    for m in range(n):
        t = s + m * default.THIRTY_MIN
        dispatch.get_all_dispatch(t, process, cvp=cvp, voll=voll, market_price_floor=market_price_floor)


if __name__ == '__main__':
    path_to_log = default.LOG_DIR / 'linux.log'
    logging.basicConfig(filename=path_to_log, filemode='w', format='%(levelname)s: %(asctime)s %(message)s',
                        level=logging.DEBUG)

    with mp.Pool() as pool:
        result = pool.map(apply_multiprocess_predispatch,
                          [datetime.datetime(2020, 9, 1, 12, 30),
                           datetime.datetime(2020, 9, 1, 16, 30),
                           datetime.datetime(2020, 9, 1, 20, 30),
                           datetime.datetime(2020, 9, 2, 0, 30)])
    pool.close()
    pool.join()
