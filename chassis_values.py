"""Display conversions and approximate body-aero comparisons from CSV meanings."""


def aero_summary(drag_raw, ratio_raw, rear_raw, stock_drag, stock_ratio):
    drag = drag_raw / 65536
    ratio = ratio_raw / 100
    rear = rear_raw / 65536
    return {
        "drag": drag,
        "ratio": ratio,
        "front_percent": (1 - rear) * 100,
        "rear_percent": rear * 100,
        "relative_drag": drag_raw / stock_drag * 100,
        "relative_downforce": drag_raw * ratio_raw / (stock_drag * stock_ratio) * 100,
    }
