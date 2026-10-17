# serpentineLauncher

Открытый лаунчер Minecraft на Python и QML. Интерфейс работает на PySide6 и Universal GUI; установкой игры, сборками, файлами и процессами управляет собственный Core.

## Возможности

- Отдельные сборки Minecraft, карточки и список, редактор параметров и файлов.
- Установка Vanilla, Fabric, Quilt, Forge и NeoForge.
- Поиск модов Modrinth, очередь загрузок, зависимости и импорт `.mrpack`.
- Управление Java, памятью, запущенными клиентами и журналами.
- Русский и английский интерфейс, базовые светлая и тёмная темы.
- Локальные offline-профили и CLI. Авторизация Microsoft в текущей версии не реализована.

## Запуск из исходников

Основная платформа разработки и сборки — Windows, Python 3.11 или новее, 64 бита. Команды выполняются из корня репозитория в PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -B Core/tools/themes/build_themes.py
.\.venv\Scripts\python.exe -B main.py
```

Скрипт тем собирает два базовых пакета из `theme_sources`. Они не хранятся в Git как сгенерированные файлы. После изменения исходников тем выполните этот скрипт повторно.

Universal GUI подключён отдельной зависимостью: файл `working_universal_gui-0.2.5+launcherfix10-py3-none-any.whl` в корне устанавливается через `requirements.txt`. Исходники UGF не входят в этот репозиторий; для фреймворка планируется отдельный репозиторий.

Для запуска Minecraft установите подходящую 64-битную Java: требуемая версия зависит от выбранной версии игры. При первом запуске лаунчер ищет Java и напоминает создать профиль. Java не скачивается автоматически.

## Проверка интерфейса

Проверки используют временные данные и не запускают Minecraft:

```powershell
.\.venv\Scripts\python.exe -B main.py --verify-release-ui
.\.venv\Scripts\python.exe -B main.py --verify-release-ui --live --software
.\.venv\Scripts\python.exe -B main.py --verify-release-ui --custom
```

Доступные команды CLI:

```powershell
.\.venv\Scripts\python.exe -B main.py --help
.\.venv\Scripts\python.exe -B main.py builds --format=json
```

## Сборка Windows EXE

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -B Core/build/build.py --prepare-only
.\.venv\Scripts\python.exe -B Core/build/build.py
```

Nuitka создаёт самостоятельную папку `лаунчер` с `SerpantineLauncher.exe`. При первой компиляции может потребоваться загрузка C-компилятора. Параметры: `Core/build/build.py --help`. Для передачи приложения нужна вся итоговая папка.

## Структура и данные

`main.py` — точка входа; `Core` — логика, CLI и сборщик; `ui` — QML; `assets` — обязательные ресурсы и заводские значения интерфейса; `langs` — русский перевод; `theme_sources` — две базовые темы.

Настройки и профили создаются локально в `SerpantineLauncher.json`, состояние тем — в `SerpantineThemeHealth.json`. Игровые файлы, библиотеки, журналы и пользовательские темы находятся в `builds`, `Cores`, `libs`, `logs` и `themes`. Эти данные исключены из Git. Экспериментальные темы, мастерская, виртуальное окружение и готовые EXE не входят в исходники.

## Лицензия

Код лаунчера распространяется под GNU GPL версии 3 (`GPL-3.0-only`), полный текст — в [LICENSE](LICENSE). Эта лицензия не меняет лицензии зависимостей, включая отдельный wheel Universal GUI. Сведения о зависимостях — в [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Minecraft принадлежит Mojang и Microsoft. Проект не является официальным продуктом Mojang или Microsoft. Игровые JAR, моды, миры и ресурсы игры в репозитории отсутствуют.
