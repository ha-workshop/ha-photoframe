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

# Рамки как устройства (этап 2).
PLATFORMS = ["binary_sensor", "button", "light", "select", "sensor"]
SIGNAL_FRAME_ADDED = "photoframe_frame_added"
SIGNAL_FRAME_UPDATED = "photoframe_frame_updated_{}"
ALBUM_ALL = "all"
MANUFACTURER = "ha-workshop"
