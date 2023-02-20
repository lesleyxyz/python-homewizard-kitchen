from ..enums import KettleStatus
import collections
import copy


class Kettle:
    def __init__(self, device: dict) -> None:
        self.device = copy.deepcopy(device)

    def __deep_update(self, orig_dict: dict, new_dict: dict) -> dict:
        for key, val in new_dict.items():
            if isinstance(val, collections.abc.Mapping):
                orig_dict[key] = self.__deep_update(orig_dict.get(key, {}), val)
            elif isinstance(val, list):
                orig_dict[key] = (orig_dict.get(key, []) + val)
            else:
                orig_dict[key] = new_dict[key]
        return orig_dict

    def _deep_update(self, new_dict: dict):
        return self.__deep_update(self.device, new_dict)

    def to_json(self) -> dict:
        return copy.deepcopy(self.device)

    def start(self):
        self._deep_update({"state": {
            "action": "start"
        }})

    def stop(self):
        self._deep_update({"state": {
            "action": "stop"
        }})

    def set_target_temperature(self, target_temperature: int):
        # should be between 40 and 100 in steps of 5
        self._deep_update({"state": {
            "target_temperature": target_temperature
        }})

    def get_target_temperature(self) -> int:
        return self.device.get("state", {}).get("target_temperature")

    def get_current_temperature(self) -> int:
        return self.device.get("state", {}).get("current_temperature")

    def get_status(self) -> KettleStatus:
        return KettleStatus(self.device.get("state", {}).get("status"))

    def is_online(self) -> bool:
        return self.device.get("online", False)

    def get_version(self) -> str:
        return self.device.get("version")

    def get_model(self) -> str:
        return self.device.get("model")

    def get_id(self) -> str:
        return self.device.get("device")

    def set_name(self, name: str):
        self._deep_update({"name": name})

    def get_name(self) -> str:
        return self.device.get("name")

    def get_boil_before_target(self) -> bool:
        return self.device.get("state", {}).get("boil_before_target", False)

    def set_boil_before_target(self, bbt: bool):
        self.device.setdefault("state", {})["boil_before_target"] = bbt

    def get_keep_warm_enabled(self) -> bool:
        return self.device.get("state", {}).get("keep_warm_enabled", False)

    def set_keep_warm_enabled(self, kw: bool):
        self.device.setdefault("state", {})["keep_warm_enabled"] = kw

    def get_keep_warm_set_time(self) -> int:
        return self.device.get("state", {}).get("keep_warm_set_time", False)

    def set_keep_warm_set_time(self, kw_time: int):
        self.device.setdefault("state", {})["keep_warm_set_time"] = kw_time
