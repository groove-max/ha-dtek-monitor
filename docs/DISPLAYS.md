# DTEK schedules and battery on GeekMagic

[Українська](DISPLAYS.uk.md) · [Back to README](../README.md)

> Available since **DTEK Monitor 2.0.0-rc6**. Update the integration and restart HA before enabling the display sensor.

A small display can show today's schedule for all groups, highlighted building and apartment groups, a clock, the next scheduled change and inverter battery charge. The Telegram companion is not required.

## Requirements

- GeekMagic already receiving images from HA. These templates were checked with **GeekMagic Display 1.6.0**, the SD_PRO profile and a 240×240 display. Other firmware needs testing on its device.
- A configured DTEK Monitor building or personal account.
- For the battery: a percentage sensor and a power sensor **in watts, positive for charging and negative for discharging**, from any integration. If your source uses another sign or kW, normalize it with a Home Assistant template sensor first.
- HA time zone set to Europe/Kyiv.

## Enable the display data

1. Open **Settings → Devices & services → DTEK Monitor**.
2. Choose your building or personal account device.
3. Find the disabled **Schedule display data** entity, open its settings and enable it. Wait for its state and attributes to appear.
4. Copy its entity ID. Choose the account's entity for personal group selection, or the building's entity for all building groups.

The entity is disabled by default. Enabling it makes no additional DTEK requests: it uses the integration's existing verified data. The large `days` attribute is excluded from Recorder history. This sensor contains no address, account number or credentials.

## Set up Hero

In the **GeekMagic** panel, create a view with the **Hero** layout and **watchOS** theme. Add four **HTML** widgets in this order:

| Position | Template | Entity (template data) |
|---|---|---|
| Large top area | [grid.html](../examples/geekmagic/grid.html) | Your schedule display sensor |
| Bottom left | [groups.html](../examples/geekmagic/groups.html) | The same sensor |
| Bottom centre | [clock.html](../examples/geekmagic/clock.html) | The same sensor |
| Bottom right | [battery.html](../examples/geekmagic/battery.html) | Not needed |

Paste each file's entire content into **HTML Template**. In the battery template, replace `sensor.display_battery_percent` and `sensor.display_battery_power` with your entities. Check the preview and assign the view to the device. The supplied on-screen text is Ukrainian and can be edited directly in the templates.

Enable **Animate** on the battery widget and set **Animation Loop = 3.2**. Enable the device's **Animations** switch in HA. Values also work without animation. Start with a **10-second** display refresh interval; this does not change DTEK polling.

## Actual electricity status

The schedule and countdown describe DTEK's plan. For the actual state, the top widget can also show a green **«СВІТЛО Є»**, red **«СВІТЛА НЕМАЄ»**, or grey **«СТАН НЕВІДОМИЙ»** badge. It updates with the display and remains visible when the schedule is unavailable.

Replace `binary_sensor.display_grid_present` in `grid.html` with your **actual grid presence** binary sensor (`on` = present). The source must become unavailable when its evidence is missing/stale. Do not use the DTEK schedule/power entity or an inverter's backed-up output for this badge. If you have a backed-up inverter with a periodic grid-input frequency sensor, [power.yaml](../examples/geekmagic/power.yaml) shows an optional HA template helper with freshness checking and 10-second loss / 30-second recovery delays. Merge it into your existing template configuration; change the source entity first. It does not require the bot.

For the JSON builder, pass `--power-state binary_sensor.your_grid_present`. Omit it to hide the badge. When copying the HTML manually without a source, the badge honestly shows unknown. The badge uses its own HA source; the bot may wait longer for its additional confirmation sensor.

## Reading the display

- A blue row background marks building groups; a bright outline marks selected personal groups. Other groups remain visible.
- Orange means a planned outage; orange hatching means a possible outage; blue-grey bands indicate weekly forecasts; grey hatching means unknown data. An unhatched dark interval means no outage in the confirmed schedule.
- The vertical line is the current time. Past bands to its left are dimmed; future bands retain their contrast. Group labels and selection borders remain unchanged. Interval boundaries retain their original minute offsets; visual precision is limited by the display's pixels.
- More than 12 groups use pages that change every 20 seconds. Up to six building groups stay on every page; larger building selections page with the whole table. The group list also pages when it contains more than four groups.
- The countdown shows the earliest start or end among the selected groups and identifies the affected groups when more than one is selected. A scheduled end is not proof that electricity has returned.
- An unselected apartment group shows the building groups and asks you to select your own in HA. No personal countdown is guessed.
- **−148 W in red** means discharging; **+350 W in green** means charging; **0 W** is neutral. An unavailable sensor shows a dash rather than zero. Battery fill colour follows its charge level.

A schedule error clears old bands. If HA, the network or the display itself disconnects, the device may retain its last image: a frozen clock helps identify this. HA, networking and the display need backup power to remain useful during outages.

You can edit the templates in GeekMagic. The optional [build_view.py](../examples/geekmagic/build_view.py) produces a view JSON for GeekMagic API users; it does not install a view or contact HA or DTEK.
