import json
import preprocess


def condition1(process, i):
    """ All intervals of dispatch and first interval of p5min and predispatch.

    Args:
        process (str): 'dispatch', 'p5min' or 'predispatch'
        i (int): Interval number

    Returns:
        bool: True if satisfied; False otherwise.
    """
    return process == 'dispatch' or i == 0


def condition2(process, i):
    """ All intervals of dispatch, first interval of p5min, and none of predispatch.

        Args:
            process (str): 'dispatch', 'p5min' or 'predispatch'
            i (int): Interval number

        Returns:
            bool: True if satisfied; False otherwise.
        """
    return process == 'dispatch' or (process == 'p5min' and i == 0)


def condition3(process, dis, pre, rhs):
    c1 = (process == 'p5min' or process == 'predispatch') and pre
    c2 = process == 'dispatch' and dis
    c3 = rhs is not None
    return (c1 or c2) and c3


def read_cvp():
    input_dir = preprocess.DATA_DIR / 'CVP.json'
    with input_dir.open() as f:
        return json.load(f)


def get_total_intervals(process, start_time):
    dispatch_intervals = 1
    p5min_intervals = 12
    if process == 'dispatch':
        return dispatch_intervals
    elif process == 'p5min':
        return p5min_intervals
    else:
        pre_dir = preprocess.DATA_DIR / 'predispatch_intervals.json'
        with pre_dir.open() as f:
            return json.load(f)[start_time.strftime('%H:%M')]