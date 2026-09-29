import numpy as np


def mape(actual: np.ndarray, predicted: np.ndarray) -> float | None:
    mask = actual != 0
    if not mask.any():
        return None
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def directional_accuracy(
    last_known: np.ndarray, actual: np.ndarray, predicted: np.ndarray
) -> float | None:
    """% of forecasts that called the direction of change from the last known value."""
    actual_dir = np.sign(actual - last_known)
    mask = actual_dir != 0
    if not mask.any():
        return None
    predicted_dir = np.sign(predicted - last_known)
    return float(np.mean(predicted_dir[mask] == actual_dir[mask]) * 100)


def interval_coverage(actual: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    return float(np.mean((actual >= lower) & (actual <= upper)) * 100)
