"""Solar AC forecast for the rooftop pilot.

The forecast is a file the scheduler can read. This package does not open a
serial port, write a Modbus register, or otherwise control equipment.
"""

from forecasting.config import TIMEZONE

__all__ = ["TIMEZONE"]
