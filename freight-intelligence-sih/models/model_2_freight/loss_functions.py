"""
Custom Asymmetric Regret Loss Functions for Maritime Freight Forecasting
Lin-Lin & Asymmetric Huber Loss to penalize under-forecasting freight spikes more heavily than over-forecasting.
"""

import numpy as np

def asymmetric_regret_loss(y_true, y_pred, alpha: float = 2.5, beta: float = 1.0):
    """
    Lin-Lin Asymmetric Loss:
    If y_true > y_pred (Under-prediction, market spike missed):
        loss = alpha * (y_true - y_pred)
    If y_pred >= y_true (Over-prediction):
        loss = beta * (y_pred - y_true)
    """
    err = y_true - y_pred
    return np.where(err > 0, alpha * err, beta * (-err))

def asymmetric_huber_loss(y_true, y_pred, delta: float = 1.0, alpha: float = 2.5, beta: float = 1.0):
    """
    Smooth differentiable Asymmetric Huber Loss suitable for gradient boosting and neural nets.
    """
    err = y_true - y_pred
    abs_err = np.abs(err)
    
    # Base Huber
    huber = np.where(abs_err <= delta, 0.5 * (err ** 2), delta * (abs_err - 0.5 * delta))
    
    # Asymmetric multiplier: heavier on under-prediction (err > 0)
    multiplier = np.where(err > 0, alpha, beta)
    return multiplier * huber

def calculate_confidence_bounds(y_pred: float, volatility: float, horizon_days: int) -> tuple[float, float]:
    """
    Calculates upper and lower asymmetric confidence bounds for horizon projection.
    Upper bound expands faster because freight rate upside risks (surges) are higher than downside drops.
    """
    horizon_factor = np.sqrt(horizon_days / 7.0)
    lower_bound = round(max(5.0, y_pred - (volatility * 0.85 * horizon_factor)), 2)
    upper_bound = round(y_pred + (volatility * 1.35 * horizon_factor), 2)
    return lower_bound, upper_bound
