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
