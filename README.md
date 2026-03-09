# DTEK Monitor

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Custom Home Assistant integration for monitoring electricity outages in the DTEK OEM service area (Odesa region, Ukraine).

The integration polls the [DTEK OEM shutdowns page](https://www.dtek-oem.com.ua/ua/shutdowns) for the selected address, combines real outage status with planned and possible schedule windows, and exposes the result as Home Assistant sensors and calendars.

## Highlights

- Real-time outage status with outage type classification
- Separate calendars for confirmed outages and possible outage windows
- Schedule-group detection, including addresses that belong to multiple groups
- Stable entity/device identity tied to the configured address
- Adjustable polling interval through an options flow

## What's New in 1.2.0

- Added automatic migration from legacy entry-ID-based registry identifiers to stable address-based identifiers
- Preserved all DTEK schedule groups instead of keeping only the first one
- Refactored schedule logic into a dedicated domain module with test coverage
- Fixed overlap handling between factual and possible outage windows
- Extended calendar next-event lookup to the full weekly schedule horizon

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Go to `Custom repositories`.
3. Add `https://github.com/groove-max/ha-dtek-monitor` as an `Integration`.
4. Install `DTEK Monitor`.
5. Restart Home Assistant.

### Manual

1. Copy `custom_components/dtek_monitor` into `config/custom_components/`.
2. Restart Home Assistant.

## Configuration

1. Open `Settings -> Devices & Services -> Add Integration`.
2. Search for `DTEK Monitor`.
3. Complete the setup flow:
   - select the city;
   - select the street;
   - select the house number;
   - choose the polling interval.

After setup, open the integration card and use `Configure` to change the polling interval without removing the entry.

## Upgrade Notes for 1.1.x -> 1.2.0

- The config entry is migrated from version `1` to version `2`.
- Existing entity and device registry identifiers are migrated from the old `entry_id` format to stable address-based identifiers.
- Existing `entity_id` values should remain unchanged, so automations and dashboards continue to work.
- A new sensor is added for the complete list of schedule groups.

No manual re-add of the integration should be required.

## Entities

Examples below use the default Home Assistant object IDs created for a new installation. Existing upgraded installations may keep older object IDs if they were already registered or manually renamed.

### Binary Sensor

| Entity | Meaning |
|--------|---------|
| `binary_sensor.<address_slug>_power` | `on` when power is available, `off` during an outage |

Attributes:

- `outage_type`
- `outage_start`
- `outage_end`
- `outage_description`
- `schedule_groups`
- `outage_count`

### Sensors

| Entity | Meaning |
|--------|---------|
| `sensor.<address_slug>_outage_status` | Normalized outage type: `ok`, `emergency`, `planned`, `stabilization` |
| `sensor.<address_slug>_outage_description` | DTEK outage description text |
| `sensor.<address_slug>_outage_start` | Current outage start timestamp |
| `sensor.<address_slug>_outage_end` | Current outage end timestamp |
| `sensor.<address_slug>_schedule_group` | Primary schedule group for the address |
| `sensor.<address_slug>_all_schedule_groups` | All schedule groups reported by DTEK |
| `sensor.<address_slug>_dtek_last_update` | Timestamp reported by DTEK for the latest data refresh |
| `sensor.<address_slug>_schedule_changed` | Timestamp of the latest schedule change |

The primary schedule group sensor also exposes the complete `schedule_groups` list as an attribute.

### Calendars

| Entity | Meaning |
|--------|---------|
| `calendar.<address_slug>_outage_schedule` | Confirmed outage slots |
| `calendar.<address_slug>_possible_outage_schedule` | Possible outage windows after confirmed overlaps are removed |

## Schedule Semantics

- Confirmed outages come from factual DTEK schedule data.
- Possible outages come from preset DTEK schedule windows.
- When factual and preset windows overlap, the preset window is trimmed so the possible-outage calendar does not duplicate confirmed outage time.
- Calendar next-event lookup scans the full available weekly schedule, not only the next 48 hours.

## Architecture Overview

- `config_flow.py`: address selection, validation, and options flow
- `dtek_client.py`: HTTP access, session handling, HTML/API parsing
- `schedule.py`: pure schedule-domain logic for merging slots and finding next events
- `coordinator.py`: normalization of DTEK payloads into Home Assistant entity data
- `migration.py`: registry migration helpers used during upgrades

## Requirements

- Home Assistant `2026.3.0` or newer

Brand assets are bundled locally in `custom_components/dtek_monitor/brand/`, so no external icon hosting is required.

## Development

Run the local test suite with:

```bash
python -m unittest discover -s tests -v
```

Optional sanity check:

```bash
python -m compileall custom_components tests
```

## License

[MIT](LICENSE)

---

# DTEK Monitor (Українська)

Кастомна інтеграція Home Assistant для моніторингу відключень електроенергії в зоні обслуговування ДТЕК ОЕМ (Одеська область, Україна).

Інтеграція опитує [сторінку відключень ДТЕК ОЕМ](https://www.dtek-oem.com.ua/ua/shutdowns) для вибраної адреси, поєднує поточний стан відключення з плановими та можливими слотами графіка і публікує результат у Home Assistant через сенсори та календарі.

## Основні можливості

- Моніторинг стану електропостачання в реальному часі
- Класифікація типу відключення: аварійне, планове, стабілізаційне
- Окремі календарі для підтверджених і можливих відключень
- Підтримка адрес з кількома групами графіку
- Стабільна ідентичність сутностей і пристроїв, прив'язана до адреси
- Зміна інтервалу опитування через меню параметрів без повторного додавання інтеграції

## Що змінилося у 1.2.0

- Додано автоматичну міграцію зі старих ідентифікаторів реєстрів на стабільні адресні ідентифікатори
- Збережено всі групи графіку, які повертає ДТЕК
- Логіку розкладу винесено в окремий доменний модуль і покрито тестами
- Виправлено обробку перетинів між фактичними і можливими слотами
- Пошук наступної події в календарях тепер охоплює весь доступний тижневий горизонт

## Встановлення

### HACS

1. Відкрийте HACS у Home Assistant.
2. Перейдіть до `Custom repositories`.
3. Додайте `https://github.com/groove-max/ha-dtek-monitor` як `Integration`.
4. Встановіть `DTEK Monitor`.
5. Перезапустіть Home Assistant.

### Вручну

1. Скопіюйте `custom_components/dtek_monitor` до `config/custom_components/`.
2. Перезапустіть Home Assistant.

## Налаштування

1. Відкрийте `Налаштування -> Пристрої та служби -> Додати інтеграцію`.
2. Знайдіть `DTEK Monitor`.
3. Пройдіть кроки майстра:
   - оберіть місто;
   - оберіть вулицю;
   - оберіть номер будинку;
   - задайте інтервал опитування.

Після початкового налаштування можна відкрити картку інтеграції та використати `Налаштувати`, щоб змінити інтервал опитування без повторного додавання адреси.

## Примітки до оновлення 1.1.x -> 1.2.0

- Запис конфігурації мігрує з версії `1` на версію `2`.
- Сутності та пристрої автоматично переводяться зі старих `entry_id`-ідентифікаторів на стабільні адресні.
- Наявні `entity_id` мають зберегтися, тому автоматизації та дашборди не повинні зламатися.
- Додається новий сенсор з повним переліком груп графіку.

Повторно додавати інтеграцію вручну не потрібно.

## Сутності

Нижче наведені приклади стандартних `entity_id`, які Home Assistant створює для нової інсталяції. Після оновлення або ручного перейменування фактичні `entity_id` можуть відрізнятися.

### Бінарний сенсор

| Сутність | Значення |
|----------|----------|
| `binary_sensor.<address_slug>_power` | `on`, якщо електрика є; `off`, якщо зараз відключення |

Атрибути:

- `outage_type`
- `outage_start`
- `outage_end`
- `outage_description`
- `schedule_groups`
- `outage_count`

### Сенсори

| Сутність | Значення |
|----------|----------|
| `sensor.<address_slug>_outage_status` | Нормалізований тип відключення: `ok`, `emergency`, `planned`, `stabilization` |
| `sensor.<address_slug>_outage_description` | Текстовий опис відключення від ДТЕК |
| `sensor.<address_slug>_outage_start` | Час початку поточного відключення |
| `sensor.<address_slug>_outage_end` | Час завершення поточного відключення |
| `sensor.<address_slug>_schedule_group` | Основна група графіку для адреси |
| `sensor.<address_slug>_all_schedule_groups` | Усі групи графіку, які повернув ДТЕК |
| `sensor.<address_slug>_dtek_last_update` | Час останнього оновлення даних за версією ДТЕК |
| `sensor.<address_slug>_schedule_changed` | Час останньої зміни графіку |

Сенсор основної групи графіку також віддає повний список у вигляді атрибуту `schedule_groups`.

### Календарі

| Сутність | Значення |
|----------|----------|
| `calendar.<address_slug>_outage_schedule` | Підтверджені слоти відключень |
| `calendar.<address_slug>_possible_outage_schedule` | Можливі вікна відключення після віднімання підтверджених перетинів |

## Семантика графіків

- Підтверджені відключення будуються з фактичних даних графіка від ДТЕК.
- Можливі відключення будуються з preset-вікон графіка ДТЕК.
- Якщо factual і preset слоти перетинаються, preset-слот обрізається, щоб у календарі можливих відключень не дублювався вже підтверджений час.
- Пошук наступної події в календарях виконується по всьому доступному тижневому горизонту.

## Огляд архітектури

- `config_flow.py`: вибір адреси, валідація, меню параметрів
- `dtek_client.py`: HTTP-доступ, керування сесією, парсинг HTML та API-відповідей
- `schedule.py`: чиста доменна логіка для злиття слотів і пошуку наступної події
- `coordinator.py`: нормалізація даних ДТЕК у формат Home Assistant
- `migration.py`: допоміжна логіка міграції registry під час оновлення

## Вимоги

- Home Assistant `2026.3.0` або новіше

Брендові ресурси постачаються локально в `custom_components/dtek_monitor/brand/`, тому зовнішній хостинг іконок не потрібен.

## Розробка

Запуск локальних тестів:

```bash
python -m unittest discover -s tests -v
```

Додаткова sanity-перевірка:

```bash
python -m compileall custom_components tests
```

## Ліцензія

[MIT](LICENSE)
