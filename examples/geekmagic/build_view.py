"""Build an importable GeekMagic view without contacting HA or DTEK."""

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def entity_id(value):
    if not re.fullmatch(r"sensor\.[a-z0-9_]+", value):
        raise argparse.ArgumentTypeError("Expected a sensor entity ID")
    return value


def binary_entity_id(value):
    if not re.fullmatch(r"binary_sensor\.[a-z0-9_]+", value):
        raise argparse.ArgumentTypeError("Expected a binary_sensor entity ID")
    return value


def build_view(display, battery_percent, battery_power, power_state=None):
    widgets = []
    for slot, name in enumerate(("grid", "groups", "clock", "battery")):
        template = (ROOT / (name + ".html")).read_text()
        options = {"html": template}
        if name == "grid":
            options["html"] = (
                template.replace("binary_sensor.display_grid_present", binary_entity_id(power_state))
                if power_state else template.replace("states('binary_sensor.display_grid_present')", "'not_configured'")
            )
        if name == "battery":
            options["html"] = template.replace("sensor.display_battery_percent", battery_percent).replace("sensor.display_battery_power", battery_power)
            options.update(animate=True, loop_seconds=3.2)
        else:
            options["entity_id"] = display
        widgets.append({"slot": slot, "type": "html", "options": options})
    return {"name": "ДТЕК · Енергія", "layout": "hero", "theme": "watchos", "widgets": widgets}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--display", type=entity_id, required=True)
    parser.add_argument("--battery-percent", type=entity_id, required=True)
    parser.add_argument("--battery-power", type=entity_id, required=True)
    parser.add_argument("--power-state", type=binary_entity_id, help="Actual grid presence: on=present, off=absent; never a schedule forecast")
    args = parser.parse_args()
    print(json.dumps(build_view(args.display, args.battery_percent, args.battery_power, args.power_state), ensure_ascii=False, indent=2))
