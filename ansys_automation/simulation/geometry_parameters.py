
def calculate_geometry_parameters(inputs=None):
    """Calculate Shell and Bellow geometry dimensions in millimetres."""

    params = {
        "NSID": 242.82,
        "SLTS": 2234.0,
        "T1": 15.09,
        "T2": 24.56,
        "T3": 14.0,
        "R1": 45.0,
        "L3": 65.0,
        "L4": 20.0,
        "L5": 20.0,
        "L6": 25.0,
        "L7": 75.0,
        "TPSL": 3.0,
    }

    if inputs:
        for name in params:
            if name in inputs:
                params[name] = float(inputs[name])

    for name, value in params.items():
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero.")

    NSID = params["NSID"]
    SLTS = params["SLTS"]
    T1 = params["T1"]
    T2 = params["T2"]
    T3 = params["T3"]
    R1 = params["R1"]
    L3 = params["L3"]
    L4 = params["L4"]
    L5 = params["L5"]
    L6 = params["L6"]
    L7 = params["L7"]
    TPSL = params["TPSL"]

    if T2 <= T1:
        raise ValueError("T2 must be greater than T1.")

    R4 = R1
    SID = NSID / 2
    R3 = T3 + R4
    L8 = T2 - T3
    BID = SID + R1 + R3 + L4 + L8
    R2 = R1 + T3
    L1 = SLTS / 2
    L9 = (T2 - T1) * TPSL
    L10 = T3 + R1 + R4 + L3 + L5 + L6 + L7
    L2 = L1 - L10

    if L8 <= 0:
        raise ValueError("L8 must be positive; check T2 and T3.")

    if L2 <= 0:
        raise ValueError("L2 must be positive; check SLTS and length inputs.")

    params.update({
        "R2": R2,
        "R3": R3,
        "R4": R4,
        "SID": SID,
        "BID": BID,
        "L1": L1,
        "L2": L2,
        "L8": L8,
        "L9": L9,
        "L10": L10,
    })

    return params
