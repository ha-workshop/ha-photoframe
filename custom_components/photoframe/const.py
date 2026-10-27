"""Константы интеграции Photo Frame."""

DOMAIN = "photoframe"

# Хранилище: дома, их экраны и настройки слайдшоу — в том же виде, что в конфиге карточки дашборда.
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

# Карточка дашборда, из которой переносим данные при первом запуске.
CARD_TYPE = "custom:photoframe-card"
SETUP_DASHBOARD = "photo-frame"

# Настройки интеграции (Options).
CONF_MEDIA_FOLDER = "media_folder"
CONF_KIOSK = "kiosk"
CONF_EDIT = "edit"
EDIT_ADMINS = "admins"
EDIT_USERS = "users"

DEFAULT_MEDIA_FOLDER = "photoframe"

# Адреса, по которым интеграция раздаёт интерфейс.
URL_PWA = "/photoframe"
URL_CARD = "/photoframe_card/photoframe-card.js"
