"""Convert pandas/numpy values into plain Python values that JSON can store.

numpy types (np.int64, np.float32, ...) are not JSON-serialisable, and JSON
has no NaN or infinity, so those become None.
"""

import math
from datetime import date, datetime

import numpy as np
import pandas as pd


def to_json_value(val):
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        # pd.isna on a list/array returns an array, not a bool
        pass
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (float, np.floating)):
        return None if math.isinf(val) else float(val)
    if isinstance(val, (pd.Timestamp, datetime, date)):
        return val.isoformat()
    return val
