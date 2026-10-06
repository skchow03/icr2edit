"""UI-independent, ID-keyed parameter state shared by all editor views."""

import math
from fixed_point import encode_fixed_16_16, decode_fixed_16_16


class ParameterModel:
    def __init__(self):
        self.parameters = {}
        self.original = {}
        self.values = {}
        self._listeners = []

    def subscribe(self, callback):
        self._listeners.append(callback)

    def unsubscribe(self, callback):
        self._listeners.remove(callback)

    def load(self, parameters, values):
        registry = {}
        for param in parameters:
            pid = param.get("Parameter ID", "").strip()
            if not pid or pid in registry:
                raise ValueError(f"Missing or duplicate Parameter ID: {pid!r}")
            if values.get(pid) is None:
                raise ValueError(f"Cannot read parameter: {pid}")
            registry[pid] = param
        self.parameters = registry
        self.values = {pid: values[pid] for pid in registry}
        self.original = self.values.copy()

    @property
    def dirty(self):
        return {pid for pid, value in self.values.items() if value != self.original[pid]}

    def get_value(self, parameter_id):
        return self.values[parameter_id]

    def set_value(self, parameter_id, value):
        param = self.parameters[parameter_id]
        data_type = param.get("Data type", "").strip()
        if not math.isfinite(value):
            raise ValueError("Value must be finite")
        if data_type.lower() in {"16.16", "fixed16.16", "fixed16_16"}:
            value = decode_fixed_16_16(encode_fixed_16_16(value))
        else:
            if int(value) != value:
                raise ValueError("Integer parameter requires a whole number")
            value = int(value)
            bits = int(param["Length"]) * 8
            signed = data_type.startswith("Int")
            lower = -(1 << (bits - 1)) if signed else 0
            upper = (1 << (bits - int(signed))) - 1
            if not lower <= value <= upper:
                raise ValueError(f"Value out of range for {parameter_id}")
        if self.values[parameter_id] != value:
            self.values[parameter_id] = value
            self._notify(parameter_id)

    def reset_defaults(self, parameter_ids):
        """Stage CSV defaults for an explicit group without touching other edits."""
        for pid in parameter_ids:
            param = self.parameters[pid]
            raw = param["Default value"]
            value = float(raw) if param.get("Data type", "").lower() in {"16.16", "fixed16.16", "fixed16_16"} else int(raw)
            self.set_value(pid, value)

    def values_for(self, parameters):
        return {p["Parameter ID"]: self.values[p["Parameter ID"]] for p in parameters}

    def _notify(self, pid):
        for callback in tuple(self._listeners):
            callback(pid)

    def revert(self):
        changed = self.dirty
        self.values = self.original.copy()
        for pid in changed:
            self._notify(pid)

    def mark_saved(self):
        changed = self.dirty
        self.original = self.values.copy()
        for pid in changed:
            self._notify(pid)
