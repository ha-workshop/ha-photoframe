<p align="center"><img src="https://raw.githubusercontent.com/ha-workshop/ha-photoframe/main/docs/icon.png" width="128" height="128" alt="Photo Frame"></p>

# Photo Frame — интеграция для Home Assistant

[English](README.md) · **Русский**

**Одна установка — и фоторамка целиком.** Планшет, старый телефон или Android-фоторамка показывают ваши фото,
большие часы и погоду; смахнули вверх — свет, климат, камеры, колонки и телевизор. Интеграция приносит всё
с собой: без отдельной карточки дашборда, аддонов и долгоживущих токенов.

## Что внутри

- **Карточка дашборда** `custom:photoframe-card` — доступна на всех дашбордах сразу после установки,
  ресурс добавлять не нужно.
- **Отдельное приложение** по адресу `http://<ваш HA>/photoframe/` — для браузера, «на экран Домой» и старых
  Android-рамок (APK-оболочка — в [lovelace-photoframe](https://github.com/ha-workshop/lovelace-photoframe)).
  Вход — через обычную страницу входа Home Assistant.
- **Общая конфигурация** для карточки и всех рамок: дома, их экраны и карточки, настройки слайдшоу —
  хранятся в Home Assistant (`.storage/photoframe`), правка сразу видна на всех рамках.
  Фото — из медиатеки (`/media/photoframe`).
- **Настройки в интерфейсе** — «Настройки → Устройства и службы → Photo Frame → Настроить»: папка фото,
  режим киоска по умолчанию, кто может менять дома и экраны (администраторы или все пользователи).

## Каждая рамка — устройство

Каждая рамка, открывшая приложение (APK, браузер, «на экран Домой»), появляется в «Настройки → Устройства»:

- **В сети** — пока рамка на связи;
- **Альбом** — подпапка папки фото (`/media/photoframe/<альбом>`) или «Все фото»;
- **Стартовый экран** — с него рамка начинает и к нему возвращается без касаний;
- **Текущее фото** — с самим фото в картинке сущности;
- кнопки **Следующее фото**, **Открыть панель**, **Вернуться к фото**, **Перезагрузить**.

Службы для автоматизаций (рамки выбираются устройствами; не выбраны — все в сети):
`photoframe.show_camera` (позвонили в дверь — камера у входа на 30 с), `photoframe.set_album`,
`photoframe.show_screen`, `photoframe.next_photo`. Переименуйте рамку как любое устройство — она узнает своё имя.

Сам интерфейс — экран с фото как на iPhone, экраны у домов, отдельная раскладка для телефона, графики —
описан в [lovelace-photoframe](https://github.com/ha-workshop/lovelace-photoframe).

## Установка

1. HACS → ⋮ → «Пользовательские репозитории» → `https://github.com/ha-workshop/ha-photoframe`, категория **Integration**.

   [![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ha-workshop&repository=ha-photoframe&category=Integration)
2. Установите **Photo Frame** и перезапустите Home Assistant.
3. «Настройки → Устройства и службы → Добавить интеграцию → Photo Frame».
4. Добавьте карточку **Photo Frame** на дашборд (лучше в вид «Панель») или откройте `/photoframe/` на устройстве.

Уже стоит **карточка Photo Frame** из HACS (категория Dashboard)? При первом запуске интеграция перенесёт дома
и экраны из карточки на дашборде «Фоторамка». Карточку можно оставить — интеграция это увидит и вторую копию
не подключит — или удалить.

## Разработка

Интерфейс — подмодуль [lovelace-photoframe](https://github.com/ha-workshop/lovelace-photoframe) в `frontend/`;
релиз собирает его в интеграцию (`photoframe.zip`).

```bash
git clone --recursive https://github.com/ha-workshop/ha-photoframe
scripts/build-frontend.sh      # интерфейс → custom_components/photoframe/frontend
dev/run.sh                     # тестовый Home Assistant в Docker: http://localhost:8125
```

`FRONTEND=../lovelace-photoframe scripts/build-frontend.sh` — собрать из рабочей копии вместо подмодуля.

## Лицензия

MIT
