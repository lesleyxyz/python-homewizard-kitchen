from enum import Enum


class KettleStatus(Enum):
    ON = "on"
    HEATING_TO_TARGET = "heating_to_target"
    FINISHED_HEATING_TO_TARGET = "finished_heating_to_target"
    KEEPING_WARM = "keeping_warm"
