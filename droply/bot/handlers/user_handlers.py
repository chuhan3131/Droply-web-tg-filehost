from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiohttp
import urllib.parse

from ..config import BASE_URL
from ..keyboards import main_menu, back_to_main, upload, file_settings_menu


router = Router()


@router.message(Command("start"))
async def start(message: Message):
    user_name = message.from_user.first_name or "друг"
    text = (
        f"<b>👋 Привет, {user_name}! Droply — удобный файлообменник прямо в Telegram.\n\n"
        "Выберите действие ниже ⬇️</b>"
    )
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")



@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("<b>Главное меню:</b>", reply_markup=main_menu(), parse_mode='HTML')
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("<b>Главное меню:</b>", reply_markup=main_menu(), parse_mode='HTML')
    await callback.answer()


@router.callback_query(F.data == "upload")
async def upload_callback(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("<b>Отправьте файл сообщением. (макс. размер 50 МБ)</b>", reply_markup=upload(), parse_mode='HTML')
    await callback.answer()


@router.callback_query(F.data == "links")
async def my_links(callback: CallbackQuery):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/api/files/{callback.from_user.id}") as resp:
                if resp.status != 200:
                    await callback.message.edit_text("<b>❌ Ошибка при получении файлов</b>", reply_markup=back_to_main(), parse_mode='HTML')
                    return

                result = await resp.json()
                files = result.get("files", [])
                if not files:
                    await callback.message.edit_text("📎 У вас пока нет загруженных файлов", reply_markup=back_to_main())
                    return
                text = "📎 <b>Ваши файлы:</b>"
                kb = InlineKeyboardBuilder()
                for i, f in enumerate(files, 1):
                    kb.row(
                        InlineKeyboardButton(
                            text=f"{i}. {f['filename']}",
                            callback_data=f"file_{f['file_code']}"
                        )
                    )
                kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

                await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception as e:
        await callback.message.edit_text(f"<b>❌ Ошибка:</b> <code>{e}</code>", reply_markup=back_to_main(), parse_mode='HTML')
    await callback.answer()


@router.callback_query(F.data.startswith("file_"))
async def file_actions(callback: CallbackQuery):
    file_code = callback.data.split("_", 1)[1]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/api/stats/{file_code}") as resp:
                if resp.status != 200:
                    await callback.answer("Файл не найден"); return
                stats = await resp.json()
                size_mb = (stats.get("size", 0) / 1024 / 1024) if stats.get("size") else 0
                await callback.message.edit_text(
                    f"<b>📁 Файл: {stats['filename']}\n\n"
                    f"📦 Размер: {size_mb:.2f} MB\n"
                    f"👁 Посещения: {stats['visits']} | 📥 Скачивания: {stats['downloads']}\n"
                    f"🔗 Ссылка: <code>{BASE_URL}/{file_code}</code></b>\n",
                    reply_markup=file_settings_menu(file_code, stats["notify_visits"], stats["notify_downloads"]),
                    parse_mode='HTML'
                )
    except Exception as e:
        await callback.answer(f"Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data.startswith("user_toggle_visits_"))
async def user_toggle_visits(callback: CallbackQuery):
    file_code = callback.data.split("_")[-1]
    try:
        async with aiohttp.ClientSession() as s:
            form = aiohttp.FormData()
            form.add_field("user_id", str(callback.from_user.id))
            async with s.patch(f"{BASE_URL}/api/files/{file_code}/notify_visits", data=form) as r:
                if r.status == 200:
                    async with s.get(f"{BASE_URL}/api/stats/{file_code}") as r2:
                        st = await r2.json()
                        size_mb = (st.get("size", 0) / 1024 / 1024) if st.get("size") else 0
                        await callback.message.edit_text(
                            f"<b>📁 Файл: {st['filename']}\n\n"
                            f"📦 Размер: {size_mb:.2f} MB\n"
                            f"👁 Посещения: {st['visits']} | 📥 Скачивания: {st['downloads']}\n"
                            f"🔗 Ссылка: <code>{BASE_URL}/{file_code}</code></b>\n",
                            reply_markup=file_settings_menu(file_code, st["notify_visits"], st["notify_downloads"]),
                            parse_mode='HTML'
                        )
                else:
                    await callback.answer("Ошибка")
    except Exception as e:
        await callback.answer(f"Ошибка: {e}")
    await callback.answer()

@router.callback_query(F.data.startswith("user_toggle_downloads_"))
async def user_toggle_downloads(callback: CallbackQuery):
    file_code = callback.data.split("_")[-1]
    try:
        async with aiohttp.ClientSession() as s:
            form = aiohttp.FormData()
            form.add_field("user_id", str(callback.from_user.id))
            async with s.patch(f"{BASE_URL}/api/files/{file_code}/notify_downloads", data=form) as r:
                if r.status == 200:
                    async with s.get(f"{BASE_URL}/api/stats/{file_code}") as r2:
                        st = await r2.json()
                        size_mb = (st.get("size", 0) / 1024 / 1024) if st.get("size") else 0
                        await callback.message.edit_text(
                            f"<b>📁 Файл: {st['filename']}\n\n"
                            f"📦 Размер: {size_mb:.2f} MB\n"
                            f"👁 Посещения: {st['visits']} | 📥 Скачивания: {st['downloads']}\n"
                            f"🔗 Ссылка: <code>{BASE_URL}/{file_code}</code></b>\n",
                            reply_markup=file_settings_menu(file_code, st["notify_visits"], st["notify_downloads"]),
                            parse_mode='HTML'
                        )
                else:
                    await callback.answer("Ошибка")
    except Exception as e:
        await callback.answer(f"Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data.startswith("delete_"))
async def delete_file(callback: CallbackQuery):
    file_code = callback.data.split("_", 1)[1]
    try:
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("user_id", str(callback.from_user.id))
            async with session.delete(f"{BASE_URL}/api/files/{file_code}", data=form) as resp:
                if resp.status == 200:
                    await callback.message.edit_text("<b>✅ Файл успешно удалён</b>", reply_markup=back_to_main(), parse_mode='HTML')
                else:
                    await callback.message.edit_text("<b>❌ Ошибка при удалении файла</b>", reply_markup=back_to_main(), parse_mode='HTML')
    except Exception as e:
        await callback.message.edit_text(f"<b>❌ Ошибка:</b> <code>{e}</code>", reply_markup=back_to_main(), parse_mode='HTML')
    await callback.answer()


@router.callback_query(F.data.startswith("replace_"))
async def replace_file(callback: CallbackQuery, state: FSMContext):
    file_code = callback.data.split("_", 1)[1]
    await state.update_data(replace_file_code=file_code)
    await callback.message.edit_text(
        "<b>Отправьте новый файл для замены.\n\n<blockquote><i>💡 Ссылка останется прежней.</i></blockquote></b>",
        reply_markup=upload(),
        parse_mode='HTML'
    )
    await callback.answer()


@router.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("replace_file_code"):
        await message.answer("<b>❌ Пожалуйста, отправьте файл для замены, а не текст</b>", parse_mode='HTML')
        return


@router.message(F.document | F.photo | F.video | F.audio | F.voice)
async def handle_file(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state and "broadcast" in current_state:
        return

    loading_msg = await message.answer("🔄 <b>Загружаю файл...</b>", parse_mode='HTML')

    try:
        if message.document:
            file = message.document
            file_size = file.file_size
            file_name = file.file_name
        elif message.photo:
            file = message.photo[-1]
            file_size = file.file_size
            file_name = f"photo_{file.file_id}.jpg"
        elif message.video:
            file = message.video
            file_size = file.file_size
            file_name = file.file_name or f"video_{file.file_id}.mp4"
        elif message.audio:
            file = message.audio
            file_size = file.file_size
            file_name = file.file_name or f"audio_{file.file_id}.mp3"
        elif message.voice:
            file = message.voice
            file_size = file.file_size
            file_name = f"voice_{file.file_id}.ogg"
        else:
            await loading_msg.edit_text("<b>❌ Неподдерживаемый тип файла</b>", parse_mode='HTML')
            return

        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 МБ
        if file_size > MAX_FILE_SIZE:
            await loading_msg.edit_text(
                f"<b>❌ Файл слишком большой!</b>\n\n"
                f"Размер: {file_size / 1024 / 1024:.2f} МБ\n"
                f"Максимальный размер: 50 МБ\n\n"
                f"Пожалуйста, отправьте файл меньшего размера.",
                parse_mode='HTML'
            )
            return

        await loading_msg.edit_text("📥 <b>Скачиваю файл из Telegram...</b>", parse_mode='HTML')

        file_info = await message.bot.get_file(file.file_id)
        downloaded = await message.bot.download_file(file_info.file_path)
        file_bytes = downloaded.read()

        await loading_msg.edit_text("📤 <b>Загружаю файл на сервер...</b>", parse_mode='HTML')

        data = await state.get_data()
        replace_file_code = data.get("replace_file_code")

        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("file", file_bytes, filename=file_name)
            form.add_field("user_id", str(message.from_user.id))

            if replace_file_code:
                await loading_msg.edit_text("🔄 <b>Заменяю файл...</b>", parse_mode='HTML')

                async with session.put(f"{BASE_URL}/api/files/{replace_file_code}/replace", data=form) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        await loading_msg.edit_text(
                            f"<b>✅ Файл заменён!\n\n"
                            f"📁 Имя: {result['filename']}\n"
                            f"🔗 Ссылка: <code>{result['download_url']}</code></b>",
                            reply_markup=back_to_main(),
                            parse_mode='HTML'
                        )
                        await state.clear()
                    else:
                        error_text = await resp.text()
                        await loading_msg.edit_text(
                            f"<b>❌ Ошибка при замене файла:</b>\n<code>{error_text[:100]}...</code>",
                            parse_mode='HTML'
                        )
            else:
                await loading_msg.edit_text("📤 <b>Загружаю файл...</b>", parse_mode='HTML')

                async with session.post(f"{BASE_URL}/api/upload", data=form) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        filename = urllib.parse.unquote(result["filename"])
                        await loading_msg.edit_text(
                            f"<b>✅ Файл загружен!\n\n"
                            f"📁 Имя: {filename}\n"
                            f"🔗 Ссылка: <code>{result['download_url']}</code></b>",
                            reply_markup=back_to_main(),
                            parse_mode='HTML'
                        )
                    else:
                        error_text = await resp.text()
                        await loading_msg.edit_text(
                            f"<b>❌ Ошибка при загрузке файла:</b>\n<code>{error_text[:100]}...</code>",
                            parse_mode='HTML'
                        )

    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 100:
            error_msg = error_msg[:100] + "..."

        await loading_msg.edit_text(
            f"<b>❌ Ошибка при загрузке:</b>\n<code>{error_msg}</code>",
            parse_mode='HTML'
        )
    finally:
        if await state.get_data():
            await state.clear()