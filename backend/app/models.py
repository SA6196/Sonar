from typing import List, Optional, Literal
from pydantic import BaseModel, Field

SensingMode = Literal["TIER1", "TIER2", "DEGRADED"]

class SimulationParams(BaseModel):
    noise_level: float = Field(22, ge=0, le=100)
    target_amplitude: float = Field(0.55, ge=0, le=1)
    target_frequency: float = Field(4200, gt=0)
    target_position: float = Field(0.52, ge=0, le=1)
    target_duration: float = Field(2.4, gt=0)
    sampling_rate: float = Field(50000, gt=1000)
    filter_cutoff: float = Field(8000, gt=100)
    detection_threshold: float = Field(0.18, gt=0)
    battery_level: float = Field(0.86, ge=0, le=1)

class RawBlock(BaseModel):
    samples: List[float] = Field(min_length=32, max_length=20000)
    sampling_rate: float = Field(50000, gt=1000)
    battery_level: float = Field(0.86, ge=0, le=1)
    timestamp: Optional[int] = None
    detection_threshold: float = Field(0.18, gt=0)
    filter_cutoff: float = Field(8000, gt=100)
    adc_full_scale: Optional[float] = Field(None, gt=0, description="Explicit ADC full-scale count")

class ModeOverride(BaseModel):
    mode: SensingMode
