# DTEK Monitor

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Custom Home Assistant integration for monitoring electricity outages in the DTEK OEM service area (Odesa region, Ukraine).

Polls the [DTEK OEM website](https://www.dtek-oem.com.ua/ua/shutdowns) for real-time outage status and scheduled disconnection data for a specific address.

## Features

- **Real-time outage monitoring** — binary sensor and detailed status sensors
- **Outage type classification** — emergency, planned, stabilization
- **Two schedule calendars** — separate calendars for confirmed outages and possible outages
- **Schedule group tracking** — detects and reports your address's schedule group
- **Automatic schedule updates** — keeps outage and possible outage schedules up to date
- **Multi-outage support** — handles multiple simultaneous outages with severity-based priority

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/groove-max/ha-dtek-monitor` with category **Integration**
4. Search for "DTEK Monitor" and install
5. Restart Home Assistant

### Manual

1. Download the `custom_components/dtek_monitor` folder
2. Copy it to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "DTEK Monitor"
3. Follow the setup wizard:
   - Select your **city**
   - Select your **street**
   - Select your **house number**
   - Set the **polling interval** (default: 300 seconds)

## Entities

### Binary Sensor

| Entity | Description |
|--------|-------------|
| `binary_sensor.<address>_power` | `on` when power is available, `off` during outage |

Attributes: `outage_type`, `outage_start`, `outage_end`, `outage_description`, `schedule_groups`, `outage_count`

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.<address>_status` | Outage type: `ok`, `emergency`, `planned`, `stabilization` |
| `sensor.<address>_outage_description` | DTEK outage description text |
| `sensor.<address>_outage_start` | Outage start timestamp |
| `sensor.<address>_outage_end` | Outage end timestamp |
| `sensor.<address>_schedule_group` | Schedule group for your address (e.g. GPV5.1) |
| `sensor.<address>_last_update` | Last DTEK data update timestamp |
| `sensor.<address>_schedule_changed` | Last schedule change timestamp |

### Calendars

| Entity | Description |
|--------|-------------|
| `calendar.<address>_outage_schedule` | Confirmed planned outages (Графік відключень) |
| `calendar.<address>_possible_schedule` | Possible outage windows (Графік можливих відключень) |

The outage schedule calendar shows confirmed disconnections from DTEK's schedule. The possible outage calendar shows time windows when disconnection may occur but is not guaranteed.

## Requirements

- **Home Assistant 2026.3.0** or newer (required for local brand icons)

Integration icons are bundled in the `brand/` folder and served locally by HA — no internet connection needed for icons, and no submission to the [home-assistant/brands](https://github.com/home-assistant/brands) repository is required.

## Automation Examples

### Notify on power outage

```yaml
automation:
  - alias: "Power outage notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.dtek_your_street_your_house_power
        to: "off"
    action:
      - service: notify.mobile_app
        data:
          title: "Power outage"
          message: >
            Power outage detected.
            Type: {{ state_attr('binary_sensor.dtek_your_street_your_house_power', 'outage_type') }}
```

### Notify on schedule group change

```yaml
automation:
  - alias: "Schedule group changed"
    trigger:
      - platform: state
        entity_id: sensor.dtek_your_street_your_house_schedule_group
    condition:
      - condition: template
        value_template: "{{ trigger.from_state.state != trigger.to_state.state }}"
    action:
      - service: notify.mobile_app
        data:
          title: "Schedule group changed"
          message: "New group: {{ states('sensor.dtek_your_street_your_house_schedule_group') }}"
```

---

# DTEK Monitor (Українська)

Кастомна інтеграція Home Assistant для моніторингу відключень електроенергії в зоні обслуговування ДТЕК ОЕМ (Одеська область, Україна).

## Можливості

- **Моніторинг відключень в реальному часі** — бінарний сенсор та детальні сенсори стану
- **Класифікація типу відключення** — аварійне, планове, стабілізаційне
- **Два календарі графіків** — окремі календарі для планових та можливих відключень
- **Відстеження групи графіку** — визначає групу вашої адреси
- **Автоматичне оновлення графіків** — підтримує актуальність графіків відключень та можливих відключень

## Встановлення

### HACS (Рекомендовано)

1. Відкрийте HACS в Home Assistant
2. Натисніть меню з трьома крапками → **Custom repositories**
3. Додайте `https://github.com/groove-max/ha-dtek-monitor` з категорією **Integration**
4. Знайдіть "DTEK Monitor" та встановіть
5. Перезапустіть Home Assistant

### Вручну

1. Завантажте папку `custom_components/dtek_monitor`
2. Скопіюйте її до `config/custom_components/` вашого Home Assistant
3. Перезапустіть Home Assistant

## Налаштування

1. Перейдіть до **Налаштування → Пристрої та служби → Додати інтеграцію**
2. Знайдіть "DTEK Monitor"
3. Дотримуйтесь майстра налаштування:
   - Оберіть **місто**
   - Оберіть **вулицю**
   - Оберіть **номер будинку**
   - Встановіть **інтервал оновлення** (за замовчуванням: 300 секунд)

## Сутності

### Бінарний сенсор

| Сутність | Опис |
|----------|------|
| `binary_sensor.<адреса>_power` | `on` — електроенергія є, `off` — відключення |

### Сенсори

| Сутність | Опис |
|----------|------|
| `sensor.<адреса>_status` | Тип: `ok`, `emergency`, `planned`, `stabilization` |
| `sensor.<адреса>_outage_description` | Опис відключення від ДТЕК |
| `sensor.<адреса>_outage_start` | Час початку відключення |
| `sensor.<адреса>_outage_end` | Час закінчення відключення |
| `sensor.<адреса>_schedule_group` | Група графіку (напр. GPV5.1) |
| `sensor.<адреса>_last_update` | Час останнього оновлення даних |
| `sensor.<адреса>_schedule_changed` | Час останньої зміни графіку |

### Календарі

| Сутність | Опис |
|----------|------|
| `calendar.<адреса>_outage_schedule` | Графік відключень (підтверджені) |
| `calendar.<адреса>_possible_schedule` | Графік можливих відключень |

## Вимоги

- **Home Assistant 2026.3.0** або новіше (необхідно для локальних іконок)

Іконки інтеграції знаходяться в папці `brand/` та обслуговуються локально — не потрібне з'єднання з інтернетом для іконок та не потрібно подавати їх до репозиторію [home-assistant/brands](https://github.com/home-assistant/brands).

## Ліцензія

[MIT](LICENSE)
