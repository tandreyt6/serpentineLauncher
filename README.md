# Serpentine Launcher

Открытый лаунчер Minecraft для управления сборками, модами и запуском игры. Написан на Python и QML: интерфейс использует PySide6 и Universal GUI, а собственное ядро Core отвечает за установку игры, загрузки и управление клиентами.

## Возможности

- Отдельные сборки Minecraft со своими параметрами и файлами.
- Установка Vanilla, Fabric, Quilt, Forge и NeoForge.
- Поиск модов Modrinth, очередь загрузок, зависимости и импорт `.mrpack`.
- Выбор Java, настройка памяти, управление запущенными клиентами и просмотр журналов.
- Русский и английский интерфейс, базовые светлая и тёмная темы.
- Локальные offline-профили и CLI. Авторизация Microsoft в текущей версии не реализована.

## Как пользоваться

Создайте профиль, затем добавьте сборку: выберите версию Minecraft и, при необходимости, загрузчик модов. Лаунчер загрузит игровые файлы и зависимости. После установки можно добавить моды, настроить Java и память, затем запустить игру из карточки сборки.

Для Minecraft нужна подходящая 64-битная Java; её версия зависит от версии игры. Лаунчер ищет установленную Java при первом запуске. Если она не найдена, установите её самостоятельно и укажите путь в настройках.

## Запуск из исходников

Основная платформа разработки и сборки — Windows, Python 3.11 или новее, 64 бита. Команды выполняются из корня репозитория в PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -B Core/tools/themes/build_themes.py
.\.venv\Scripts\python.exe -B main.py
```

Скрипт `build_themes.py` собирает базовые светлую и тёмную темы из `theme_sources`. Повторите его запуск после изменения исходников тем.

Universal GUI — отдельная зависимость. Его wheel находится в корне репозитория и устанавливается через `requirements.txt`.

Справка по командам CLI:

```powershell
.\.venv\Scripts\python.exe -B main.py --help
```

## Сборка Windows EXE

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -B Core/build/build.py
```

Nuitka создаёт самостоятельную папку `лаунчер` с `SerpantineLauncher.exe`. При первой компиляции может потребоваться загрузка C-компилятора. Параметры: `Core/build/build.py --help`. Для передачи приложения нужна вся итоговая папка.

## Лицензия

Код лаунчера распространяется под GNU GPL версии 3 (`GPL-3.0-only`), полный текст — в [LICENSE](LICENSE). Эта лицензия не меняет лицензии зависимостей, включая отдельный wheel Universal GUI. Сведения о зависимостях — в [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Minecraft принадлежит Mojang и Microsoft. Проект не является официальным продуктом Mojang или Microsoft. Игровые JAR, моды, миры и ресурсы игры в репозитории отсутствуют.
