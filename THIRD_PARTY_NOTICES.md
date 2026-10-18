# Зависимости

Лицензия GPL-3.0-only этого проекта не заменяет лицензии зависимостей. Python-пакеты устанавливаются через `requirements.txt` и `requirements-build.txt`; их исходники и уведомления доступны в соответствующих проектах и установленных дистрибутивах.

| Компонент | Версия | Источник |
| --- | --- | --- |
| working-universal-gui | 0.2.5+launcherfix12 | Wheel в корне репозитория, предоставлен автором UGF как отдельная зависимость |
| Qt for Python / PySide6 и Shiboken6 | 6.11.0 | [Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html) |
| Pillow | 12.3.0 | [Pillow](https://github.com/python-pillow/Pillow) |
| markdown-it-py | 4.2.0 | [markdown-it-py](https://github.com/executablebooks/markdown-it-py) |
| mdurl | 0.1.2 | [mdurl](https://github.com/executablebooks/mdurl) |
| Nuitka, инструмент сборки | 4.2.2 | [Nuitka](https://github.com/Nuitka/Nuitka) |
| ordered-set, инструмент сборки | 4.1.0 | [ordered-set](https://github.com/rspeer/ordered-set) |
| zstandard, инструмент сборки | 0.25.0 | [python-zstandard](https://github.com/indygreg/python-zstandard) |

Qt содержит собственные сторонние компоненты. При распространении собранного приложения необходимо сохранять относящиеся к включённым библиотекам тексты лицензий и уведомления; перечень Qt приведён в официальной документации по ссылке выше.

Universal GUI — отдельный проект автора лаунчера. Его wheel включён с разрешения автора. В метаданных этой версии wheel лицензия UGF не указана; GPL-3.0-only лаунчера не присваивается фреймворку. Исходники и отдельная лицензия UGF в этот репозиторий не включены.
