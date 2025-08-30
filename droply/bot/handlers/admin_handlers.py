from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp

from ..keyboards import admin_menu, admin_files_menu, admin_file_actions, cancel_keyboard
from ..config import ADMIN_IDS, BASE_URL

router = Router()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

class SearchState(StatesGroup):
    waiting_for_query = State()

_admin_pages = {}

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("👨‍💻 Админ панель", reply_markup=admin_menu())
    else:
        await message.answer("❌ У вас нет доступа к админ панели")

@router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(callback: CallbackQuery):
    if callback.from_user.id in ADMIN_IDS:
        await callback.message.delete()
        await callback.message.answer("👨‍💻 Админ панель", reply_markup=admin_menu())
    await callback.answer()

# ====== ДАШБОРД ======
@router.callback_query(F.data == "admin_dashboard")
async def admin_dashboard(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен"); return
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{BASE_URL}/api/admin/stats?admin_id={callback.from_user.id}") as r:
                if r.status != 200:
                    await callback.message.edit_text("❌ Ошибка при получении статистики", reply_markup=admin_menu()); return
                st = await r.json()
                text = (
                    "📊 <b>Дашборд</b>\n\n"
                    f"📁 Файлов: <b>{st['total_files']}</b> "
                    f"(+{st['files_this_week']} за 7д)\n"
                    f"💾 Объем: <b>{st['total_size_mb']} MB</b>\n"
                    f"👁 Визитов: <b>{st['total_visits']}</b> "
                    f"(+{st['visits_this_week']} за 7д)\n"
                    f"⬇️ Скачиваний: <b>{st['total_downloads']}</b> "
                    f"(+{st['downloads_this_week']} за 7д)\n\n"
                    "🏆 <b>Топ по скачиваниям:</b>\n" +
                    ("\n".join([f"{i+1}. {t['filename']} — {t['downloads']}" for i,t in enumerate(st['top_files'])]) or "—")
                )
                await callback.message.edit_text(text, reply_markup=admin_menu(), parse_mode="HTML")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=admin_menu())
    await callback.answer()

# ====== СПИСОК ФАЙЛОВ ======
@router.callback_query(F.data == "all_links")
async def admin_all_files(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен"); return
    info = _admin_pages.get(callback.from_user.id, {"page": 1, "q": None, "size": 10})
    await _send_files_page(callback, info["page"], info["q"], info["size"])

@router.callback_query(F.data == "admin_prev")
async def admin_prev(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(); return
    info = _admin_pages.get(callback.from_user.id, {"page": 1, "q": None, "size": 10})
    info["page"] = max(1, info["page"] - 1)
    _admin_pages[callback.from_user.id] = info
    await _send_files_page(callback, info["page"], info["q"], info["size"])

@router.callback_query(F.data == "admin_next")
async def admin_next(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(); return
    info = _admin_pages.get(callback.from_user.id, {"page": 1, "q": None, "size": 10})
    info["page"] += 1
    _admin_pages[callback.from_user.id] = info
    await _send_files_page(callback, info["page"], info["q"], info["size"])

async def _send_files_page(callback: CallbackQuery, page: int, q: str | None, size: int):
    try:
        async with aiohttp.ClientSession() as s:
            url = f"{BASE_URL}/api/admin/files?admin_id={callback.from_user.id}&page={page}&size={size}"
            if q: url += f"&q={q}"
            async with s.get(url) as r:
                if r.status != 200:
                    await callback.message.edit_text("❌ Ошибка при получении файлов", reply_markup=admin_menu()); return
                result = await r.json()
                files = result.get("files", [])
                total = result.get("total", 0)
                if not files and page > 1:
                    await callback.answer("Конец списка");
                    _admin_pages[callback.from_user.id] = {"page": max(1, page-1), "q": q, "size": size}
                    return
                text = f"📁 <b>Все файлы</b> (стр {result['page']}, всего {total})\n\n"
                for i, f in enumerate(files, 1):
                    text += (
                        f"{i}. <b>{f['filename']}</b>\n"
                        f"   💾 {f['size_mb']} MB | 👤 ID: {f['user_id']}\n"
                        f"   🔗 <code>{f['download_url']}</code>\n"
                        f"   ⚙️ /manage_{f['file_code']}\n\n"
                    )
                await callback.message.edit_text(text, reply_markup=admin_files_menu(), parse_mode="HTML")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=admin_menu())
    await callback.answer()


@router.message(F.text.regexp(r"^/manage_[A-Za-z0-9]+$"))
async def admin_manage_file(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    code = message.text.split("_",1)[1]
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{BASE_URL}/api/stats/{code}") as r:
                if r.status != 200:
                    await message.answer("❌ Файл не найден"); return
                st = await r.json()
                size_mb = (st.get("size", 0) / 1024 / 1024) if st.get("size") else 0
                text = (
                    f"<b>Управление файлом</b>\n\n"
                    f"📁 {st['filename']}\n"
                    f"📦 {size_mb:.2f} MB\n"
                    f"👁 {st['visits']} | ⬇️ {st['downloads']}\n"
                    f"🔗 <code>{'{}/{}'.format(BASE_URL, code)}</code>"
                )
                kb = admin_file_actions(code, st["notify_visits"], st["notify_downloads"])
                await message.answer(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ====== ТУМБЛЕРЫ УВЕДОМЛЕНИЙ ======
@router.callback_query(F.data.startswith("admin_toggle_visits_"))
async def admin_toggle_visits(callback: CallbackQuery):
    await _admin_toggle(callback, field="notify_visits")

@router.callback_query(F.data.startswith("admin_toggle_downloads_"))
async def admin_toggle_downloads(callback: CallbackQuery):
    await _admin_toggle(callback, field="notify_downloads")

async def _admin_toggle(callback: CallbackQuery, field: str):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен"); return
    code = callback.data.split("_")[-1]
    try:
        async with aiohttp.ClientSession() as s:
            form = aiohttp.FormData()
            form.add_field("admin_id", str(callback.from_user.id))
            form.add_field("field", field)
            async with s.patch(f"{BASE_URL}/api/admin/files/{code}/toggle", data=form) as r:
                if r.status == 200:
                    async with s.get(f"{BASE_URL}/api/stats/{code}") as r2:
                        st = await r2.json()
                        size_mb = (st.get("size", 0) / 1024 / 1024) if st.get("size") else 0
                        text = (
                            f"<b>Управление файлом</b>\n\n"
                            f"📁 {st['filename']}\n"
                            f"📦 {size_mb:.2f} MB\n"
                            f"👁 {st['visits']} | ⬇️ {st['downloads']}\n"
                            f"🔗 <code>{'{}/{}'.format(BASE_URL, code)}</code>"
                        )
                        kb = admin_file_actions(code, st["notify_visits"], st["notify_downloads"])
                        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
                else:
                    await callback.answer("Ошибка")
    except Exception as e:
        await callback.answer(f"Ошибка: {e}")
    await callback.answer()

# ====== ЛОГИ ======
@router.callback_query(F.data.startswith("admin_logs_"))
async def admin_logs_view(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен"); return
    code = callback.data.split("_", 2)[2]
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{BASE_URL}/api/admin/logs/{code}?admin_id={callback.from_user.id}&page=1&size=20") as r:
                if r.status != 200:
                    await callback.answer("Ошибка"); return
                data = await r.json()
                rows = data.get("logs", [])
                if not rows:
                    await callback.message.edit_text("📜 Логи пусты", reply_markup=admin_menu()); return
                lines = []
                for r in rows:
                    place = ", ".join([p for p in [r['country'], r['city']] if p])
                    lines.append(f"{'👁' if r['type']=='visit' else '⬇️'} {r['time']}  IP: {r['ip']}  {place}")
                await callback.message.edit_text(
                    f"📜 <b>Последние события ({len(rows)})</b>\n\n" + "\n".join(lines),
                    reply_markup=admin_menu(),
                    parse_mode="HTML"
                )
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=admin_menu())
    await callback.answer()

@router.callback_query(F.data.startswith("admin_logs_csv_"))
async def admin_logs_csv(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен"); return
    code = callback.data.split("_", 3)[3]
    link = f"{BASE_URL}/api/admin/logs/{code}/export.csv?admin_id={callback.from_user.id}"
    await callback.answer()
    await callback.message.answer(f"🧾 CSV: {link}")

# ====== ПОИСК ======
@router.callback_query(F.data == "admin_search")
async def admin_search(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен"); return
    await state.set_state(SearchState.waiting_for_query)
    await callback.message.edit_text("🔎 Введите строку поиска (имя файла или код):", reply_markup=cancel_keyboard())
    await callback.answer()

@router.message(SearchState.waiting_for_query)
async def admin_search_query(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    q = (message.text or "").strip()
    _admin_pages[message.from_user.id] = {"page": 1, "q": q, "size": 10}
    await state.clear()

    class DummyCb:
        from_user = message.from_user
        async def answer(self, *a, **kw): pass
        @property
        def message(self): return message
    await _send_files_page(DummyCb(), 1, q, 10)

# ====== РАССЫЛКА ======
@router.callback_query(F.data == "sending")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен"); return
    await state.set_state(BroadcastState.waiting_for_message)
    await callback.message.edit_text(
        "📢 <b>Рассылка сообщений</b>\n\nОтправьте сообщение для рассылки всем пользователям.\nПоддерживается HTML.",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(BroadcastState.waiting_for_message)
async def admin_broadcast_message(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("message", message.text)
            form.add_field("admin_id", str(message.from_user.id))
            async with session.post(f"{BASE_URL}/api/admin/broadcast", data=form) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    await message.answer(f"✅ {result['message']}", reply_markup=admin_menu())
                else:
                    await message.answer("❌ Ошибка при отправке рассылки", reply_markup=admin_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=admin_menu())
    finally:
        await state.clear()

# ====== УДАЛЕНИЕ ======
@router.callback_query(F.data.startswith("admin_delete_"))
async def admin_delete_file(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен"); return
    file_code = callback.data.split("_", 2)[2]
    try:
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("admin_id", str(callback.from_user.id))
            async with session.delete(f"{BASE_URL}/api/admin/files/{file_code}", data=form) as resp:
                if resp.status == 200:
                    await callback.message.edit_text("✅ Файл удален администратором", reply_markup=admin_menu())
                else:
                    await callback.message.edit_text("❌ Ошибка при удалении файла", reply_markup=admin_menu())
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=admin_menu())
    await callback.answer()
