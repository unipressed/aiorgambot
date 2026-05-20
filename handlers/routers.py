'''
Модуль для работы с командами и обработки с запрещённый слов

@author: Сазанаков Владимир, Стогов Константин
@version: 1.2
@dateOfBeginning: 27.02.2026
@dateOfRelease: 30.05.2026
'''
import time
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ChatPermissions
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

### Классы состояний для работы с админом в ЛС
class SetListStates(StatesGroup):
    chat_id = State()
    category = State()
    words = State()

class AddWordsStates(StatesGroup):
    chat_id = State()
    category = State()
    words = State()

class ShowListStates(StatesGroup):
    chat_id = State()

class DeleteWordsStates(StatesGroup):
    chat_id = State()
    words = State()


router = Router()

# Обновленная структура: { chat_id: {'delete': [], 'mute': [], 'ban': []} }
badWordsByChat = {}
badChars = "!@#$%^&*{}[]:;<>,.?"

# ==========================================
# БАЗОВЫЕ КОМАНДЫ
# ==========================================

@router.message(Command("start"))
async def start(message: Message):
    await message.answer("Привет! Я простой бот для тебя\n\nНапиши <b>/help</b> для помощи", parse_mode="HTML")

@router.message(Command("help"))
async def help(message: Message):
    await message.answer("Команды:\n<b>/start</b> - запустить бот\n<b>/help</b> для помощи\n<b>/about</b> для информации"
                         "\n<b>/my_handler</b> информация о юзере\n<b>/get_chatID</b> получить ID чата в ЛС"
                         "\n<b>/set_list</b> задать список запрещенных слов (только в ЛС)"
                         "\n<b>/add_words</b> добавить слова в список (только в ЛС)"
                         "\n<b>/show_list</b> посмотреть список слов (только в ЛС)"
                         "\n<b>/delete_words</b> удалить слова из списка (только в ЛС)",
                         parse_mode="HTML")

@router.message(Command("about"))
async def about(message: Message):
    await message.answer("Это команда про бота.\nБот разрабатывается командой БИТТ.\nСрок реализации - 30.05.2026")

@router.message(Command("my_handler"))
async def my_handler(message: Message):
    name = message.from_user.first_name
    user_id = message.from_user.id
    username = message.from_user.username
    await message.answer(f"firstname: <i>{name}</i>\nuserid: <i>{user_id}</i>\nusername: <i>{username}</i>", parse_mode="HTML")


# ==========================================
# КОМАНДА ДЛЯ ГРУППЫ (ПОЛУЧЕНИЕ ID)
# ==========================================

@router.message(Command("get_chatID"))
async def get_chatID(message: Message):
    if message.chat.type == "private":
        await message.answer("Эта команда работает только в группах.")
        return

    chat_member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status not in ["administrator", "creator", "owner"]:
        await message.answer("Вы не имеете достаточно прав")
        return

    chatID = message.chat.id
    try:
        await message.bot.send_message(
            message.from_user.id, 
            f"ID чата {message.chat.title or message.chat.first_name}: <b>{chatID}</b>", 
            parse_mode="HTML"
        )
        await message.answer("Отправил ID чата вам в личные сообщения.")
    except Exception:
        await message.answer("Не удалось отправить сообщение. Пожалуйста, сначала напишите мне в личные сообщения.")


@router.message(Command("set_list", "add_words", "show_list", "delete_words"), F.chat.type.in_({"group", "supergroup"}))
async def warn_group_commands(message: Message):
    await message.answer("Эта команда доступна только в личных сообщениях со мной.\nПожалуйста, напишите мне в ЛС.")
    await message.delete()


# ==========================================
# УПРАВЛЕНИЕ СПИСКАМИ (ТОЛЬКО В ЛС)
# ==========================================

# --- 1. SET LIST ---
@router.message(Command("set_list"), F.chat.type == "private")
async def set_list_start(message: Message, state: FSMContext):
    await message.answer("Введите ID чата, для которого хотите задать список слов:")
    await state.set_state(SetListStates.chat_id)

@router.message(SetListStates.chat_id, F.chat.type == "private")
async def set_list_chat_id(message: Message, state: FSMContext):
    try:
        chat_id = int(message.text)
        chat_member = await message.bot.get_chat_member(chat_id, message.from_user.id)
        if chat_member.status not in ["administrator", "creator", "owner"]:
            await message.answer("Вы не являетесь администратором в этом чате.")
            await state.clear()
            return
    except Exception:
        await message.answer("Ошибка доступа. Проверьте ID и наличие бота в группе.")
        await state.clear()
        return

    await state.update_data(chat_id=chat_id)
    await message.answer("Выберите наказание для этих слов.\nНапишите одно из слов: <b>delete</b>, <b>mute</b> или <b>ban</b>", parse_mode="HTML")
    await state.set_state(SetListStates.category)

@router.message(SetListStates.category, F.chat.type == "private")
async def set_list_category(message: Message, state: FSMContext):
    category = message.text.lower()
    if category not in ["delete", "mute", "ban"]:
        await message.answer("Ошибка! Напишите строго одно из слов: delete, mute или ban")
        return
    
    await state.update_data(category=category)
    await message.answer(f"Категория {category} выбрана.\nВведите список запрещенных слов через пробел:\nФормат: слово1 слово2")
    await state.set_state(SetListStates.words)

@router.message(SetListStates.words, F.chat.type == "private")
async def set_list_words(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data['chat_id']
    category = data['category']
    
    if chat_id not in badWordsByChat:
        badWordsByChat[chat_id] = {"delete": [], "mute": [], "ban": []}
        
    badWordsByChat[chat_id][category] = message.text.lower().split()
    await state.clear()
    await message.answer(f"Список успешно сохранен в категорию {category}!")

# --- 2. ADD WORDS ---
@router.message(Command("add_words"), F.chat.type == "private")
async def add_words_start(message: Message, state: FSMContext):
    await message.answer("Введите ID чата, для которого хотите добавить слова:")
    await state.set_state(AddWordsStates.chat_id)

@router.message(AddWordsStates.chat_id, F.chat.type == "private")
async def add_words_chat_id(message: Message, state: FSMContext):
    try:
        chat_id = int(message.text)
        chat_member = await message.bot.get_chat_member(chat_id, message.from_user.id)
        if chat_member.status not in ["administrator", "creator", "owner"]:
            await message.answer("Вы не являетесь администратором в этом чате.")
            await state.clear()
            return
    except Exception:
        await message.answer("Ошибка доступа. Проверьте ID.")
        await state.clear()
        return

    if chat_id not in badWordsByChat:
        badWordsByChat[chat_id] = {"delete": [], "mute": [], "ban": []}

    await state.update_data(chat_id=chat_id)
    await message.answer("В какую категорию добавить слова?\nНапишите: <b>delete</b>, <b>mute</b> или <b>ban</b>", parse_mode="HTML")
    await state.set_state(AddWordsStates.category)

@router.message(AddWordsStates.category, F.chat.type == "private")
async def add_words_category(message: Message, state: FSMContext):
    category = message.text.lower()
    if category not in ["delete", "mute", "ban"]:
        await message.answer("Ошибка! Напишите строго одно из слов: delete, mute или ban")
        return
    
    await state.update_data(category=category)
    await message.answer(f"Введите слова для добавления в {category}:\nФормат: слово1 слово2")
    await state.set_state(AddWordsStates.words)

@router.message(AddWordsStates.words, F.chat.type == "private")
async def add_words_words(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data['chat_id']
    category = data['category']
    userWords = message.text.lower().split()

    for word in userWords:
        if word not in badWordsByChat[chat_id][category]:
            badWordsByChat[chat_id][category].append(word)
    
    await state.clear()
    await message.answer(f"Слова успешно добавлены в категорию {category}!")

# --- 3. SHOW LIST ---
@router.message(Command("show_list"), F.chat.type == "private")
async def show_list_start(message: Message, state: FSMContext):
    await message.answer("Введите ID чата, список которого хотите посмотреть:")
    await state.set_state(ShowListStates.chat_id)

@router.message(ShowListStates.chat_id, F.chat.type == "private")
async def show_list_chat_id(message: Message, state: FSMContext):
    try:
        chat_id = int(message.text)
        chat_member = await message.bot.get_chat_member(chat_id, message.from_user.id)
        if chat_member.status not in ["administrator", "creator", "owner"]:
            await message.answer("Вы не являетесь администратором в этом чате.")
            await state.clear()
            return
    except Exception:
        await message.answer("Ошибка доступа. Проверьте ID.")
        await state.clear()
        return

    lists = badWordsByChat.get(chat_id)
    if not lists:
        await message.answer("Списки запрещённых слов для этого чата пусты.")
    else:
        text = "<b>Текущие списки слов:</b>\n\n"
        text += f"Удаление (delete): {', '.join(lists['delete']) if lists['delete'] else 'пусто'}\n"
        text += f"Мут (mute): {', '.join(lists['mute']) if lists['mute'] else 'пусто'}\n"
        text += f"Бан (ban): {', '.join(lists['ban']) if lists['ban'] else 'пусто'}"
        await message.answer(text, parse_mode="HTML")
    await state.clear()

# --- 4. DELETE WORDS ---
@router.message(Command("delete_words"), F.chat.type == "private")
async def delete_words_start(message: Message, state: FSMContext):
    await message.answer("Введите ID чата, из которого хотите удалить слова:")
    await state.set_state(DeleteWordsStates.chat_id)

@router.message(DeleteWordsStates.chat_id, F.chat.type == "private")
async def delete_words_chat_id(message: Message, state: FSMContext):
    try:
        chat_id = int(message.text)
        chat_member = await message.bot.get_chat_member(chat_id, message.from_user.id)
        if chat_member.status not in ["administrator", "creator", "owner"]:
            await message.answer("Вы не являетесь администратором в этом чате.")
            await state.clear()
            return
    except Exception:
        await message.answer("Ошибка доступа. Проверьте ID.")
        await state.clear()
        return

    if chat_id not in badWordsByChat:
        await message.answer("Списки слов для этого чата пусты.")
        await state.clear()
        return

    await state.update_data(chat_id=chat_id)
    await message.answer("Введите слова, которые вы хотите убрать из ВСЕХ списков:\nФормат: слово1 слово2")
    await state.set_state(DeleteWordsStates.words)

@router.message(DeleteWordsStates.words, F.chat.type == "private")
async def delete_words_words(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data['chat_id']
    words_to_delete = message.text.lower().split()

    # Удаляем слова сразу из всех трех категорий
    for category in ["delete", "mute", "ban"]:
        badWordsByChat[chat_id][category] = [w for w in badWordsByChat[chat_id][category] if w not in words_to_delete]

    await state.clear()
    await message.answer("Выбранные слова успешно удалены из всех списков!")


# ==========================================
# ПРОВЕРКА СООБЩЕНИЙ С ВЫДАЧЕЙ НАКАЗАНИЙ
# ==========================================

@router.message(F.chat.type.in_({"group", "supergroup"}))
async def check_bad_words(message: Message):
    if message.text and message.text.startswith('/'):
        return

    if not message.text:
        return

    clean_text = message.text
    for char in badChars:
        clean_text = clean_text.replace(char, "")

    words = clean_text.lower().split()
    chatId = message.chat.id
    lists = badWordsByChat.get(chatId)

    if not lists:
        return

    ban_words = lists.get("ban", [])
    mute_words = lists.get("mute", [])
    delete_words = lists.get("delete", [])

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    for word in words:
        # 1. Проверка на БАН (самое суровое наказание)
        if word in ban_words:
            await message.delete()
            try:
                await message.chat.ban(user_id=user_id)
                await message.answer(f"Пользователь <i>@{username}</i> был навсегда забанен за недопустимое слово.", parse_mode="HTML")
            except Exception as e:
                await message.answer(f"Не удалось забанить нарушителя. Проверьте, есть ли у бота права администратора.")
            return

        # 2. Проверка на МУТ (выдаем мут на 1 час = 3600 секунд)
        elif word in mute_words:
            await message.delete()
            mute_time = int(time.time()) + 3600
            try:
                await message.chat.restrict(
                    user_id=user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_time
                )
                await message.answer(f"Пользователь <i>@{username}</i> получил мут на 1 час за использование запрещенного слова.", parse_mode="HTML")
            except Exception as e:
                await message.answer(f"Не удалось выдать мут. Проверьте права бота.")
            return

        # 3. Проверка на обычное УДАЛЕНИЕ
        elif word in delete_words:
            await message.delete()
            await message.answer(f"Сообщение пользователя <i>@{username}</i> было удалено (запрещенное слово).", parse_mode="HTML")
            return