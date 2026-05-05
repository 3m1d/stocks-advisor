import numpy as np


def log_return(series, periods=1):
    return np.log(series / series.shift(periods))


def inverse_log_return(log_ret, prev_price):
    return prev_price * np.exp(log_ret)


def forward_log_return(series, periods: int = 1):
    """Лог-доходность на periods дней вперед"""
    return np.log(series.shift(-periods) / series)


def restore_current_price(log_ret, future_price):
    """Обратная функция лог-доходности: возвращает значение на основе будущего значения"""
    return future_price / np.exp(log_ret)
