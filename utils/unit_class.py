from dataclasses import dataclass
import xml.etree.ElementTree as ET
from typing import List, Tuple, Dict, Any, Optional, Callable
import numpy as np
from enum import Enum


class ModelUnit(Enum):
    METERS = "m"
    MILLIMETERS = "mm"
    CENTIMETERS = "cm"

@dataclass
class UnitConverter:
    source_unit: ModelUnit
    target_unit: ModelUnit
    
    _CONVERSION_FACTORS = {
        (ModelUnit.METERS, ModelUnit.MILLIMETERS): 1000,
        (ModelUnit.METERS, ModelUnit.CENTIMETERS): 100,
        (ModelUnit.MILLIMETERS, ModelUnit.CENTIMETERS): 0.1,
        (ModelUnit.MILLIMETERS, ModelUnit.METERS): 0.001,
        (ModelUnit.CENTIMETERS, ModelUnit.METERS): 0.01,
        (ModelUnit.CENTIMETERS, ModelUnit.MILLIMETERS): 10,
    }
    
    def __post_init__(self):
        self.conversion_factor = self._get_conversion_factor()
    
    def _get_conversion_factor(self) -> float:
        if self.source_unit == self.target_unit:
            return 1.0
        return self._CONVERSION_FACTORS.get((self.source_unit, self.target_unit))
    
    def convert(self, value: float) -> float:
        return value * self.conversion_factor
    
    def convert_points(self, points: np.ndarray) -> np.ndarray:
        return points * self.conversion_factor