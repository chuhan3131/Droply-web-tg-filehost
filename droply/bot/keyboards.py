from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📤 Загрузить файл", callback_data="upload"),
        InlineKeyboardButton(text="⛓️ Мои файлы", callback_data="links")
    )
    b.row(InlineKeyboardButton(text="☎ Техподдержка", url="https://t.me/rgegrtthrh"))
    return b.as_markup()

def back_to_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    return b.as_markup()

def upload() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main"))
    return b.as_markup()

def file_settings_menu(file_code: str, notify_visits: bool = True, notify_downloads: bool = True) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=("👁️ Визиты: ON" if notify_visits else "👁️ Визиты: OFF"),
                             callback_data=f"user_toggle_visits_{file_code}"),
        InlineKeyboardButton(text=("⬇️ Скачивания: ON" if notify_downloads else "⬇️ Скачивания: OFF"),
                             callback_data=f"user_toggle_downloads_{file_code}")
    )
    b.row(InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_{file_code}"))
    b.row(InlineKeyboardButton(text="🔄 Заменить файл", callback_data=f"replace_{file_code}"))
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="links"))
    return b.as_markup()


def admin_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📊 Дашборд", callback_data="admin_dashboard"),
        InlineKeyboardButton(text="📁 Все файлы", callback_data="all_links")
    )
    b.row(InlineKeyboardButton(text="🔎 Поиск", callback_data="admin_search"))
    b.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="sending"))
    b.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    return b.as_markup()

def admin_files_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="⬅️", callback_data="admin_prev"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="all_links"),
        InlineKeyboardButton(text="➡️", callback_data="admin_next"),
    )
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu"))
    return b.as_markup()

def admin_file_actions(file_code: str, notify_visits: bool, notify_downloads: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=("👁️ Визиты: ON" if notify_visits else "👁️ Визиты: OFF"),
                             callback_data=f"admin_toggle_visits_{file_code}"),
        InlineKeyboardButton(text=("⬇️ Скачивания: ON" if notify_downloads else "⬇️ Скачивания: OFF"),
                             callback_data=f"admin_toggle_downloads_{file_code}")
    )
    b.row(
        InlineKeyboardButton(text="📜 Логи", callback_data=f"admin_logs_{file_code}"),
        InlineKeyboardButton(text="🧾 CSV", callback_data=f"admin_logs_csv_{file_code}")
    )
    b.row(
        InlineKeyboardButton(text="❌ Удалить", callback_data=f"admin_delete_{file_code}")
    )
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="all_links"))
    return b.as_markup()

def cancel_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_menu"))
    return b.as_markup()
