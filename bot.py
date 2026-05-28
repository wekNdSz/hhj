import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart, Command
import os

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7899575088

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

submissions = {}
sub_counter = [0]

def esc(text: str) -> str:
    """Экранирует спецсимволы Markdown v1"""
    if not text:
        return ""
    for ch in ["*", "_", "`", "["]:
        text = text.replace(ch, f"\\{ch}")
    return text

class ProgramForm(StatesGroup):
    name = State()
    file = State()
    description = State()
    photo = State()
    source = State()
    threats = State()

class MusicForm(StatesGroup):
    name = State()
    file = State()
    description = State()
    photo = State()
    source = State()

class AdminState(StatesGroup):
    waiting_channel = State()

# ─────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    rows = [
        [InlineKeyboardButton(text="💾  Программа", callback_data="cat_program")],
        [InlineKeyboardButton(text="🎵  Музыка",    callback_data="cat_music")],
    ]
    if message.from_user.id == ADMIN_ID:
        rows.append([InlineKeyboardButton(text="⚙️  Админ панель", callback_data="open_admin")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer("👋 Привет!\nВыбери категорию:", reply_markup=kb)

# ─────────────────────────────────────────────
#  Админ панель (кнопка + команда)
# ─────────────────────────────────────────────
async def show_admin_panel(target):
    """target — Message или CallbackQuery"""
    msg = target if isinstance(target, Message) else target.message

    if not submissions:
        await msg.answer("📭 Нет заявок.")
        return

    text = "📋 *Все заявки:*\n\n"
    buttons = []
    for sid, d in submissions.items():
        cat = "💾" if d.get("category") == "program" else "🎵"
        text += f"{cat} `#{sid}` — {esc(d['name'])} от @{esc(d['username'])}\n"
        buttons.append([
            InlineKeyboardButton(text=f"{cat} #{sid} {d['name']}", callback_data=f"view_{sid}")
        ])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await msg.answer(text, parse_mode="Markdown", reply_markup=kb)

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await show_admin_panel(message)

@dp.callback_query(F.data == "open_admin")
async def cb_admin(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True)
        return
    await show_admin_panel(call)
    await call.answer()

# ─────────────────────────────────────────────
#  Просмотр заявки
# ─────────────────────────────────────────────
@dp.callback_query(F.data.startswith("view_"))
async def view_submission(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True)
        return

    sid = int(call.data.split("_")[1])
    d = submissions.get(sid)
    if not d:
        await call.answer("Не найдено", show_alert=True)
        return

    cat_emoji = "💾" if d.get("category") == "program" else "🎵"
    threats_line = f"⚠️ Угрозы: {esc(d['threats'])}\n" if d.get("threats") else ""
    source_btn = []
    if d.get("source") and d["source"].startswith("http"):
        source_btn = [InlineKeyboardButton(text="🔗 Источник", url=d["source"])]

    text = (
        f"🖕 Превью:\n\n"
        f"{cat_emoji} *{esc(d['name'])}*\n"
        f"━═━═━═━═━═━═━═━═━\n"
        f"⚡ Описание: {esc(d.get('description','—'))}\n"
        f"{threats_line}"
        f"💥 Отправитель: @{esc(d['username'])} (#{d['user_id']})\n"
        f"━═━═━═━═━═━═━═━═━\n"
        f"👉 Кто слил:\n@ТУТ\_ТГ\_КАНАЛ"
    )

    kb_rows = []
    if source_btn:
        kb_rows.append(source_btn)
    kb_rows.append([InlineKeyboardButton(text="📢 Опубликовать", callback_data=f"post_{sid}")])
    kb_rows.append([InlineKeyboardButton(text="🗑 Удалить",      callback_data=f"del_{sid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    if d.get("photo_id"):
        await call.message.answer_photo(photo=d["photo_id"], caption=text,
                                        parse_mode="Markdown", reply_markup=kb)
    else:
        await call.message.answer(text, parse_mode="Markdown", reply_markup=kb)
    await call.answer()

# ─────────────────────────────────────────────
#  Удалить
# ─────────────────────────────────────────────
@dp.callback_query(F.data.startswith("del_"))
async def delete_sub(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True)
        return
    sid = int(call.data.split("_")[1])
    submissions.pop(sid, None)
    await call.message.edit_text("🗑 Удалено.")
    await call.answer()

# ─────────────────────────────────────────────
#  Публикация
# ─────────────────────────────────────────────
@dp.callback_query(F.data.startswith("post_"))
async def post_ask_channel(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True)
        return
    sid = int(call.data.split("_")[1])
    await state.set_state(AdminState.waiting_channel)
    await state.update_data(post_sid=sid)
    await call.message.answer("📢 Введи @username канала:")
    await call.answer()

@dp.message(AdminState.waiting_channel, F.from_user.id == ADMIN_ID)
async def do_post(message: Message, state: FSMContext):
    data = await state.get_data()
    sid = data.get("post_sid")
    await state.clear()

    channel = message.text.strip()
    d = submissions.get(sid)
    if not d:
        await message.answer("⚠️ Заявка не найдена")
        return

    cat_emoji = "💾" if d.get("category") == "program" else "🎵"
    threats_line = f"⚠️ Угрозы: {esc(d['threats'])}\n" if d.get("threats") else ""
    source_btn = []
    if d.get("source") and d["source"].startswith("http"):
        source_btn = [InlineKeyboardButton(text="🔗 Источник", url=d["source"])]

    post_text = (
        f"🖕 Превью:\n\n"
        f"{cat_emoji} *{esc(d['name'])}*\n"
        f"━═━═━═━═━═━═━═━═━\n"
        f"⚡ Описание: {esc(d.get('description','—'))}\n"
        f"{threats_line}"
        f"💥 Отправитель: @{esc(d['username'])} (#{d['user_id']})\n"
        f"━═━═━═━═━═━═━═━═━\n"
        f"👉 Кто слил:\n{channel}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[source_btn]) if source_btn else None

    try:
        if d.get("photo_id"):
            await bot.send_photo(channel, photo=d["photo_id"],
                                 caption=post_text, parse_mode="Markdown", reply_markup=kb)
        else:
            await bot.send_message(channel, post_text, parse_mode="Markdown", reply_markup=kb)
        if d.get("file_id"):
            await bot.send_document(channel, document=d["file_id"])
        await message.answer(f"✅ Опубликовано в {channel}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ─────────────────────────────────────────────
#  PROGRAM FLOW
# ─────────────────────────────────────────────
@dp.callback_query(F.data == "cat_program")
async def cat_program(call: CallbackQuery, state: FSMContext):
    await state.set_state(ProgramForm.name)
    await state.update_data(category="program")
    await call.message.edit_text("💾 *Программа*\n\nНазвание:", parse_mode="Markdown")

@dp.message(ProgramForm.name)
async def prog_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ProgramForm.file)
    await message.answer("📎 Прикрепи файл:")

@dp.message(ProgramForm.file)
async def prog_file(message: Message, state: FSMContext):
    if message.document:
        await state.update_data(file_id=message.document.file_id,
                                file_name=message.document.file_name)
    else:
        await message.answer("⚠️ Нужен файл:")
        return
    await state.set_state(ProgramForm.description)
    await message.answer("📝 Описание:")

@dp.message(ProgramForm.description)
async def prog_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(ProgramForm.photo)
    await message.answer("🖼 Фото (или /skip):")

@dp.message(ProgramForm.photo)
async def prog_photo(message: Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text and "/skip" in message.text:
        await state.update_data(photo_id=None)
    else:
        await message.answer("⚠️ Фото или /skip:")
        return
    await state.set_state(ProgramForm.source)
    await message.answer("🔗 Источник — ссылка (или /skip):")

@dp.message(ProgramForm.source)
async def prog_source(message: Message, state: FSMContext):
    await state.update_data(source=message.text if "/skip" not in message.text else None)
    await state.set_state(ProgramForm.threats)
    await message.answer("⚠️ Угрозы (или /skip):")

@dp.message(ProgramForm.threats)
async def prog_threats(message: Message, state: FSMContext):
    await state.update_data(threats=message.text if "/skip" not in message.text else None)
    data = await state.get_data()
    await state.clear()
    await finish_submission(message, data)

# ─────────────────────────────────────────────
#  MUSIC FLOW
# ─────────────────────────────────────────────
@dp.callback_query(F.data == "cat_music")
async def cat_music(call: CallbackQuery, state: FSMContext):
    await state.set_state(MusicForm.name)
    await state.update_data(category="music")
    await call.message.edit_text("🎵 *Музыка*\n\nНазвание:", parse_mode="Markdown")

@dp.message(MusicForm.name)
async def music_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(MusicForm.file)
    await message.answer("🎵 Прикрепи аудио/файл:")

@dp.message(MusicForm.file)
async def music_file(message: Message, state: FSMContext):
    if message.audio:
        await state.update_data(file_id=message.audio.file_id,
                                file_name=message.audio.file_name or "audio")
    elif message.document:
        await state.update_data(file_id=message.document.file_id,
                                file_name=message.document.file_name)
    else:
        await message.answer("⚠️ Нужен аудио-файл:")
        return
    await state.set_state(MusicForm.description)
    await message.answer("📝 Описание:")

@dp.message(MusicForm.description)
async def music_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(MusicForm.photo)
    await message.answer("🖼 Обложка (или /skip):")

@dp.message(MusicForm.photo)
async def music_photo(message: Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text and "/skip" in message.text:
        await state.update_data(photo_id=None)
    else:
        await message.answer("⚠️ Фото или /skip:")
        return
    await state.set_state(MusicForm.source)
    await message.answer("🔗 Источник (или /skip):")

@dp.message(MusicForm.source)
async def music_source(message: Message, state: FSMContext):
    await state.update_data(source=message.text if "/skip" not in message.text else None)
    data = await state.get_data()
    await state.clear()
    await finish_submission(message, data)

# ─────────────────────────────────────────────
#  FINISH
# ─────────────────────────────────────────────
async def finish_submission(message: Message, data: dict):
    sub_counter[0] += 1
    sid = sub_counter[0]
    username = message.from_user.username or str(message.from_user.id)

    submissions[sid] = {
        **data,
        "user_id":  message.from_user.id,
        "username": username,
    }

    cat_emoji = "💾" if data.get("category") == "program" else "🎵"
    threats_line = f"⚠️ Угрозы: {esc(data['threats'])}\n" if data.get("threats") else ""
    source_line = ""
    source_btn = []
    if data.get("source") and data["source"].startswith("http"):
        source_line = "🔗 Источник: *(ссылка)*\n"
        source_btn = [InlineKeyboardButton(text="🔗 Источник", url=data["source"])]
    elif data.get("source"):
        source_line = f"🔗 Источник: {esc(data['source'])}\n"

    preview = (
        f"🖕 Превью:\n\n"
        f"{cat_emoji} *{esc(data['name'])}*\n"
        f"━═━═━═━═━═━═━═━═━\n"
        f"⚡ Описание: {esc(data.get('description','—'))}\n"
        f"{threats_line}"
        f"{source_line}"
        f"💥 Отправитель: @{esc(username)} (#{message.from_user.id})\n"
        f"━═━═━═━═━═━═━═━═━\n"
        f"👉 Кто слил:\n@ТУТ\_ТГ\_КАНАЛ"
    )

    # ── Превью пользователю ──
    if data.get("photo_id"):
        await message.answer_photo(photo=data["photo_id"],
                                   caption=f"✅ Отправлено!\n\n{preview}",
                                   parse_mode="Markdown")
    else:
        await message.answer(f"✅ Отправлено!\n\n{preview}", parse_mode="Markdown")

    # ── Уведомление админу ──
    admin_kb_rows = []
    if source_btn:
        admin_kb_rows.append(source_btn)
    admin_kb_rows.append([InlineKeyboardButton(text="📢 Опубликовать", callback_data=f"post_{sid}")])
    admin_kb_rows.append([InlineKeyboardButton(text="🗑 Удалить",      callback_data=f"del_{sid}")])
    admin_kb = InlineKeyboardMarkup(inline_keyboard=admin_kb_rows)

    notify = f"🔔 *Новая заявка \\#{sid}*\n\n{preview}"

    try:
        if data.get("photo_id"):
            await bot.send_photo(ADMIN_ID, photo=data["photo_id"],
                                 caption=notify, parse_mode="Markdown", reply_markup=admin_kb)
        else:
            await bot.send_message(ADMIN_ID, notify, parse_mode="Markdown", reply_markup=admin_kb)

        if data.get("file_id"):
            await bot.send_document(ADMIN_ID, document=data["file_id"],
                                    caption=f"📎 {esc(data.get('file_name','файл'))}")
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")

# ─────────────────────────────────────────────
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
