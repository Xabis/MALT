def int2(value, default=0):
    try:
        return int(value)
    except ValueError:
        return default