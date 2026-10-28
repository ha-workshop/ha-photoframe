# Как выпустить релиз

Релиз собирает GitHub (`.github/workflows/release.yml`): интерфейс из подмодуля `frontend/`
(ha-workshop/lovelace-photoframe), APK рамки и `photoframe.zip` для HACS. К релизу прикладываются
`photoframe.zip` и `photoframe.apk`; APK лежит и внутри интеграции — HA раздаёт его по
`/photoframe/photoframe.apk`.

## Один раз: ключ подписи APK

Android ставит новую версию APK поверх старой только с той же подписью. Релизы подписываются ключом
из секрета `ANDROID_KEYSTORE` — это `~/.android/debug.keystore` с Mac, которым подписаны уже
установленные рамки. Без секрета релиз не соберётся.

```bash
base64 -i ~/.android/debug.keystore | gh secret set ANDROID_KEYSTORE --repo ha-workshop/ha-photoframe
```

Или на сайте: скопировать ключ (`base64 -i ~/.android/debug.keystore | pbcopy`) →
*Settings → Secrets and variables → Actions → New repository secret*, имя `ANDROID_KEYSTORE`.

Проверить: `gh secret list --repo ha-workshop/ha-photoframe`.

Ключ не терять: с другим ключом рамкам придётся удалить APK и поставить заново (с новым входом в HA).

## Каждый релиз

1. Поменялся интерфейс или APK — поднять подмодуль на последний коммит фронтенда:

   ```bash
   git submodule update --remote frontend
   git commit -am "Фронтенд: последняя версия" && git push
   ```

2. Выпустить релиз с `main`. Номер — больше всех прежних (HACS берёт самый большой):

   ```bash
   gh release create v0.2.2 --target main --title v0.2.2 --notes "Что нового"
   ```

   Или на сайте: *Releases → Draft a new release*, тег `v0.2.2`, *Target* `main`, *Publish release*.
   Версия из тега сама попадает в `manifest.json` и в APK.

3. Дождаться сборки (пара минут) и проверить, что приложены `photoframe.zip` и `photoframe.apk`:

   ```bash
   gh run watch
   gh release view v0.2.2
   ```

4. В HA: *HACS → Photo Frame → ⋮ → Update information → Update*, перезапустить HA.

5. Рамки на Android: поставить поверх старого `http://<HA>/photoframe/photoframe.apk`
   (настройки и вход сохраняются) или по adb:

   ```bash
   curl -o /tmp/photoframe.apk http://192.168.100.10:8123/photoframe/photoframe.apk
   adb -s 192.168.100.110:5555 install -r /tmp/photoframe.apk
   ```

## Если сборка упала

```bash
gh run view --log-failed
```

Исправить, удалить неудавшийся релиз вместе с тегом и выпустить заново:

```bash
gh release delete v0.2.2 --cleanup-tag --yes
```

Частые причины:

- **Signing key** — нет секрета `ANDROID_KEYSTORE` (см. выше).
- **hassfest** — лишние поля в `manifest.json` (например, `categories` у сторонней интеграции не принимается).
- **HACS** — `hacs.json` должен оставаться таким: `name`, `homeassistant`, `render_readme`,
  `zip_release: true`, `filename: photoframe.zip`. Без `zip_release` HACS поставит исходники без интерфейса и APK.
  Предупреждение HACS про `categories` — только подсказка, его не исправить без ошибки hassfest.

## Публикация в магазине HACS (один раз)

Сейчас интеграцию ставят как пользовательский репозиторий. Чтобы она была в поиске HACS у всех, репозиторий
добавляют в [hacs/default](https://github.com/hacs/default). Требования: <https://hacs.xyz/docs/publish/include>.

Уже выполнено: репозиторий публичный, есть описание, темы, Issues и лицензия MIT; `hacs.json` с `name`;
значок в `custom_components/photoframe/brand/`; домена `photoframe` нет среди встроенных интеграций HA;
в Validate проходят hassfest и HACS action без `ignore` (предупреждение про `categories` — не ошибка).

1. Убедиться, что последний Validate на `main` зелёный, и **после него** выпустить релиз (см. выше).

2. Ссылки для заявки:

   ```bash
   gh release view --repo ha-workshop/ha-photoframe --json url -q .url
   gh run list --repo ha-workshop/ha-photoframe --workflow Validate --branch main --status success --limit 1 --json url -q '.[0].url'
   ```

   Ссылка на запуск Validate годится и для HACS action, и для hassfest — оба шага в нём.

3. Заявка — с **личного** аккаунта (не организации), из ветки форка:

   ```bash
   gh repo fork hacs/default --clone --remote && cd default
   git switch -c add-ha-photoframe
   ```

   В файл `integration` добавить строку `"ha-workshop/ha-photoframe",` **по алфавиту** (без учёта регистра;
   сейчас — между `ha-warmup/warmup` и `habity-design/…`). Проверить, что JSON цел:

   ```bash
   jq empty integration && git commit -am "Add ha-workshop/ha-photoframe" && git push -u origin add-ha-photoframe
   gh pr create --repo hacs/default --title "Add ha-workshop/ha-photoframe" --body-file ../pr-body.md
   ```

4. Текст заявки (`pr-body.md`) — шаблон hacs/default, все пункты отмечены, ссылки из шага 2:

   ```markdown
   ## Checklist

   - [x] I've read the [publishing documentation](https://hacs.xyz/docs/publish/start).
   - [x] I've added the [HACS action](https://hacs.xyz/docs/publish/action) to my repository.
   - [x] (For integrations only) I've added the [hassfest action](https://developers.home-assistant.io/blog/2020/04/16/hassfest/) to my repository.
   - [x] The actions are passing without any disabled checks in my repository.
   - [x] I've added a link to the action run on my repository below in the links section.
   - [x] I've created a new release of the repository after the validation actions were run successfully.

   ## Links

   Link to current release: <ссылка на релиз>
   Link to successful HACS action (without the `ignore` key): <ссылка на запуск Validate>
   Link to successful hassfest action (if integration): <ссылка на запуск Validate>
   ```

   Ревью не запрашивать — HACS закрывает такие заявки. Замечания придут в заявке; черновик (draft) после
   исправлений перевести в *Ready for review*.

5. После принятия: в README заменить значок `HACS-Custom` на `HACS-Default`
   (`https://img.shields.io/badge/HACS-Default-41BDF5.svg`, ссылка `https://hacs.xyz`) и убрать шаг
   с пользовательским репозиторием.
