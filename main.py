import logging
import json
import os
import random
import string
from config import API_TOKEN, ADMIN_ID, DB_FILE, COMPLAINTS_FILE
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.dispatcher.router import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Классы состояний
class RegStates(StatesGroup):
    last_name = State()
    first_name = State()
    middle_name = State()
    class_ = State()
    username = State()

class PostStates(StatesGroup):
    text = State()

class CommentStates(StatesGroup):
    post_id = State()
    text = State()

class AnnouncementStates(StatesGroup):
    text = State()

class EditBioStates(StatesGroup):
    text = State()

class SupportStates(StatesGroup):
    waiting_support_reply = State()

# Функции работы с базой данных
def init_db():
    return {
        'pending': [],
        'approved': [{
            'user_id': ADMIN_ID,
            'account_code': '000000',
            'last_name': 'Admin',
            'first_name': 'Admin',
            'middle_name': '',
            'class': 'Admin',
            'username': 'admin',
            'bio': 'Администратор системы',
            'posts': [],
            'is_admin': True,
            'banned_until': None
        }],
        'announcements': [],
        'posts': [],
        'comments': [],
        'reactions': {
            'likes': {},
            'dislikes': {}
        }
    }

def load_db():
    if not os.path.exists(DB_FILE):
        db = init_db()
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        return db
    
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            db = json.load(f)
            
            # Добавляем отсутствующие поля для совместимости
            for user in db['approved']:
                if 'banned_until' not in user:
                    user['banned_until'] = None
                if 'is_admin' not in user:
                    user['is_admin'] = (user['user_id'] == ADMIN_ID)
            
            return db
    except (json.JSONDecodeError, FileNotFoundError):
        db = init_db()
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        return db

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def generate_code():
    return ''.join(random.choices(string.digits, k=6))

async def check_ban(user_id: int) -> bool:
    """Проверяет, забанен ли пользователь"""
    db = load_db()
    user = next((u for u in db['approved'] if u['user_id'] == user_id), None)
    
    if not user or not user.get('banned_until'):
        return False
    
    try:
        ban_until = datetime.strptime(user['banned_until'], "%Y-%m-%d %H:%M:%S")
        if datetime.now() < ban_until:
            return True
        else:
            # Если время бана истекло, автоматически разбаниваем
            user['banned_until'] = None
            save_db(db)
            return False
    except:
        # Если возникла ошибка при парсинге даты
        user['banned_until'] = None
        save_db(db)
        return False

# Основные команды
@router.message(Command("start"))
async def cmd_start(message: Message):
    db = load_db()
    if any(u['user_id'] == message.from_user.id for u in db['approved']):
        await message.answer("👋 С возвращением! Используйте /help для списка команд")
    else:
        await message.answer("👋 Добро пожаловать! Для регистрации используйте /reg")

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """📚 Доступные команды:
/start - Начало работы
/help - Справка
/reg - Регистрация
/profile - Ваш профиль
/newpost - Создать пост
/posts - Лента публикаций
/top - топ постов
/comments [номер] - коменты
/comment [номер] - Комментировать
/like [номер] - Лайкнуть
/dislike [номер] - Дизлайкнуть
/editbio - Изменить информацию
/complain [код] [причина] - Пожаловаться
/support [вопрос] - Связь с админом
"""
    
    if message.from_user.id == ADMIN_ID:
        help_text += """\n\n⚙️ Админ-команды:
/ban [код] [время] - Забанить
/unban [код] - Разбанить
/broadcast [текст] - Рассылка
/complaints - Жалобы
/users - Список пользователей
/update - Тех. работы
/adminstart - отправляет всем сообщение о том что техработы закончены"""
    
    await message.answer(help_text)

# Регистрация пользочки у тебя.вателя
@router.message(Command("reg"))
async def reg_start(message: Message, state: FSMContext):
    db = load_db()
    if any(u['user_id'] == message.from_user.id for u in db['approved'] + db['pending']):
        await message.answer("❌ Вы уже зарегистрированы или ваша заявка на рассмотрении")
        return
    
    await message.answer("📝 Введите вашу фамилию:")
    await state.set_state(RegStates.last_name)

@router.message(RegStates.last_name)
async def reg_last_name(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    await message.answer("Теперь введите ваше имя:")
    await state.set_state(RegStates.first_name)

@router.message(RegStates.first_name)
async def reg_first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await message.answer("Введите ваше отчество (если нет, напишите '-'):")
    await state.set_state(RegStates.middle_name)

@router.message(RegStates.middle_name)
async def reg_middle_name(message: Message, state: FSMContext):
    await state.update_data(middle_name=message.text if message.text != '-' else '')
    await message.answer("Введите ваш класс (например, 10А):")
    await state.set_state(RegStates.class_)

@router.message(RegStates.class_)
async def reg_class(message: Message, state: FSMContext):
    await state.update_data(class_=message.text)
    await message.answer("Введите ваш username (без @):")
    await state.set_state(RegStates.username)

@router.message(RegStates.username)
async def reg_username(message: Message, state: FSMContext):
    db = load_db()
    data = await state.get_data()
    
    user_data = {
        'user_id': message.from_user.id,
        'account_code': generate_code(),
        'last_name': data['last_name'],
        'first_name': data['first_name'],
        'middle_name': data['middle_name'],
        'class': data['class_'],
        'username': message.text,
        'bio': "Пока ничего не рассказал о себе",
        'posts': [],
        'is_admin': False
    }
    
    db['pending'].append(user_data)
    save_db(db)
    
    # Уведомление админа
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{message.from_user.id}"),
        types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{message.from_user.id}")
    )
    
    await bot.send_message(
        ADMIN_ID,
        f"📨 Новая заявка на регистрацию:\n\n"
        f"ФИО: {data['last_name']} {data['first_name']} {data['middle_name']}\n"
        f"Класс: {data['class_']}\n"
        f"Username: @{message.text}\n"
        f"Код: {user_data['account_code']}",
        reply_markup=builder.as_markup()
    )
    
    await message.answer(f"✅ Заявка отправлена! Ваш код: {user_data['account_code']}")
    await state.clear()

@router.message(Command("profile"))
async def profile(message: Message):
    db = load_db()
    user = next((u for u in db['approved'] if u['user_id'] == message.from_user.id), None)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы!")
        return
    
    full_name = f"{user['last_name']} {user['first_name']} {user['middle_name']}".strip()
    text = f"""👤 Ваш профиль:
ФИО: {full_name}
Класс: {user['class']}
Код: {user['account_code']}
О себе: {user['bio']}"""
    
    # Для админа: просмотр любого профиля
    if message.from_user.id == ADMIN_ID and len(message.text.split()) > 1:
        target = next((u for u in db['approved'] if u['account_code'] == message.text.split()[1]), None)
        if target:
            full_name = f"{target['last_name']} {target['first_name']} {target['middle_name']}".strip()
            text = f"""👤 Профиль (админ):
ФИО: {full_name}
Класс: {target['class']}
Username: @{target['username']}
Код: {target['account_code']}
Telegram ID: {target['user_id']}"""
    
    await message.answer(text)

@router.message(RegStates.username)
async def reg_username(message: Message, state: FSMContext):
    db = load_db()
    data = await state.get_data()
    
    user_data = {
        'user_id': message.from_user.id,
        'account_code': generate_code(),
        'last_name': data['last_name'],
        'first_name': data['first_name'],
        'middle_name': data['middle_name'],
        'class': data['class_'],
        'username': message.text,
        'bio': "Пока ничего не рассказал о себе",
        'posts': [],
        'is_admin': False,
        'banned_until': None
    }
    
    db['pending'].append(user_data)
    save_db(db)
    
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{message.from_user.id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{message.from_user.id}")
    )
    
    await bot.send_message(
        ADMIN_ID,
        f"📨 Новая заявка:\nФИО: {data['last_name']} {data['first_name']}\nКласс: {data['class_']}\nUsername: @{message.text}\nКод: {user_data['account_code']}",
        reply_markup=builder.as_markup()
    )
    
    await message.answer(f"✅ Заявка отправлена! Ваш код: {user_data['account_code']}")
    await state.clear()

# Команды для работы с постами
@router.message(Command("comments"))
async def cmd_comments(message: Message):
    """Просмотр комментариев под постом"""
    try:
        post_id = int(message.text.split()[1])
        db = load_db()
        
        if post_id < 1 or post_id > len(db['posts']):
            await message.answer("❌ Неверный номер поста")
            return
        
        post = db['posts'][post_id-1]
        
        if not post['comments']:
            await message.answer(f"📭 Нет комментариев под постом #{post_id}")
            return
        
        # Формируем заголовок
        text = f"💬 Комментарии к посту #{post_id}:\n{'='*20}\n"
        text += f"{post['text'][:100]}{'...' if len(post['text']) > 100 else ''}\n{'='*20}\n\n"
        
        # Добавляем комментарии
        for i, comment in enumerate(post['comments'], 1):
            text += f"{i}. {comment['author_name']}:\n{comment['text']}\n\n"
        
        # Добавляем статистику
        text += f"📊 Всего комментариев: {len(post['comments'])}"
        
        await message.answer(text)
    except (IndexError, ValueError):
        await message.answer("ℹ️ Используйте: /comments [номер_поста]\nПример: /comments 3")

@router.message(Command("post"))
async def cmd_post(message: Message):
    """Просмотр поста с комментариями (альтернативный вариант)"""
    try:
        post_id = int(message.text.split()[1])
        db = load_db()
        
        if post_id < 1 or post_id > len(db['posts']):
            await message.answer("❌ Неверный номер поста")
            return
        
        post = db['posts'][post_id-1]
        
        # Формируем основное сообщение
        text = f"📝 Пост #{post_id} от {post['author_name']}:\n{'='*30}\n"
        text += f"{post['text']}\n{'='*30}\n"
        text += f"❤️ {post.get('likes', 0)} | 👎 {post.get('dislikes', 0)} | 💬 {len(post['comments'])}\n\n"
        
        # Добавляем 3 последних комментария
        if post['comments']:
            text += "💬 Последние комментарии:\n"
            for comment in post['comments'][-3:]:
                text += f"- {comment['author_name']}: {comment['text'][:50]}"
                text += "..." if len(comment['text']) > 50 else ""
                text += "\n"
            text += f"\n👉 Полный список: /comments {post_id}"
        else:
            text += "📭 Комментариев пока нет"
        
        # Кнопка "Комментировать"
        builder = InlineKeyboardBuilder()
        builder.add(
            types.InlineKeyboardButton(
                text="💬 Комментировать",
                callback_data=f"comment_{post_id}"
            )
        )
        
        await message.answer(
            text,
            reply_markup=builder.as_markup()
        )
    except (IndexError, ValueError):
        await message.answer("ℹ️ Используйте: /post [номер_поста]\nПример: /post 3")

@router.callback_query(F.data.startswith("comment_"))
async def start_commenting(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки комментария"""
    post_id = int(callback.data.split('_')[1])
    await state.update_data(post_id=post_id)
    await callback.message.answer(f"💬 Введите ваш комментарий к посту #{post_id}:")
    await state.set_state(CommentStates.text)
    await callback.answer()
@router.message(Command("top"))
async def cmd_top(message: Message):
    db = load_db()
    top_posts = sorted(db['posts'], key=lambda x: x['likes'] - x.get('dislikes', 0), reverse=True)[:5]
    
    if not top_posts:
        await message.answer("📭 Пока нет постов для рейтинга")
        return
    
    text = "🏆 Топ постов:\n\n"
    for i, post in enumerate(top_posts, 1):
        rating = post['likes'] - post.get('dislikes', 0)
        text += f"{i}. #{post['id']} ({rating} баллов)\n"
        text += f"{post['text'][:50]}...\n\n"
    
    await message.answer(text)

@router.message(Command("newpost"))
async def cmd_newpost(message: Message, state: FSMContext):
    if await check_ban(message.from_user.id):
        await message.answer("⛔ Вы заблокированы и не можете создавать посты")
        return
    
    db = load_db()
    if not any(u['user_id'] == message.from_user.id for u in db['approved']):
        await message.answer("❌ Вы не зарегистрированы!")
        return
    
    await message.answer("📝 Напишите текст поста:")
    await state.set_state(PostStates.text)

@router.message(PostStates.text)
async def newpost_finish(message: Message, state: FSMContext):
    db = load_db()
    user = next(u for u in db['approved'] if u['user_id'] == message.from_user.id)
    
    post = {
        'id': len(db['posts']) + 1,
        'author_id': message.from_user.id,
        'author_name': f"{user['last_name']} {user['first_name']}",
        'text': message.text,
        'likes': 0,
        'dislikes': 0,
        'liked_by': [],
        'disliked_by': [],
        'comments': [],
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    db['posts'].append(post)
    save_db(db)
    await message.answer("✅ Пост опубликован!")
    await state.clear()

@router.message(Command("posts"))
async def cmd_posts(message: Message):
    db = load_db()
    if not db['posts']:
        await message.answer("📭 Пока нет ни одного поста")
        return
    
    text = "📜 Последние посты:\n\n"
    for post in db['posts'][-10:][::-1]:  # Последние 10 постов (новые сверху)
        text += f"#{post['id']} {post['author_name']}:\n{post['text']}\n"
        text += f"❤️ {post['likes']} | 👎 {post['dislikes']} | 💬 {len(post['comments'])}\n\n"
    
    await message.answer(text)

# Лайки/дизлайки
@router.message(Command("like"))
async def cmd_like(message: Message):
    if await check_ban(message.from_user.id):
        await message.answer("⛔ Вы заблокированы и не можете ставить лайки")
        return
    
    try:
        post_id = int(message.text.split()[1])
        db = load_db()
        
        if post_id < 1 or post_id > len(db['posts']):
            await message.answer("❌ Неверный номер поста")
            return
        
        post = db['posts'][post_id-1]
        
        if message.from_user.id in post['liked_by']:
            await message.answer("❌ Вы уже ставили лайк этому посту")
            return
        
        if message.from_user.id in post['disliked_by']:
            post['dislikes'] -= 1
            post['disliked_by'].remove(message.from_user.id)
        
        post['likes'] += 1
        post['liked_by'].append(message.from_user.id)
        save_db(db)
        await message.answer("❤️ Ваш лайк учтен!")
    except (IndexError, ValueError):
        await message.answer("❌ Используйте: /like [номер_поста]")

@router.message(Command("dislike"))
async def cmd_dislike(message: Message):
    if await check_ban(message.from_user.id):
        await message.answer("⛔ Вы заблокированы и не можете ставить дизлайки")
        return
    
    try:
        post_id = int(message.text.split()[1])
        db = load_db()
        
        if post_id < 1 or post_id > len(db['posts']):
            await message.answer("❌ Неверный номер поста")
            return
        
        post = db['posts'][post_id-1]
        
        if message.from_user.id in post['disliked_by']:
            await message.answer("❌ Вы уже ставили дизлайк этому посту")
            return
        
        if message.from_user.id in post['liked_by']:
            post['likes'] -= 1
            post['liked_by'].remove(message.from_user.id)
        
        post['dislikes'] += 1
        post['disliked_by'].append(message.from_user.id)
        save_db(db)
        await message.answer("👎 Ваш дизлайк учтен!")
    except (IndexError, ValueError):
        await message.answer("❌ Используйте: /dislike [номер_поста]")

# Комментарии
@router.message(Command("comment"))
async def cmd_comment(message: Message, state: FSMContext):
    if await check_ban(message.from_user.id):
        await message.answer("⛔ Вы заблокированы и не можете оставлять комментарии")
        return
    
    try:
        post_id = int(message.text.split()[1])
        await state.update_data(post_id=post_id)
        await message.answer("💬 Напишите ваш комментарий:")
        await state.set_state(CommentStates.text)
    except (IndexError, ValueError):
        await message.answer("❌ Используйте: /comment [номер_поста]")

@router.message(CommentStates.text)
async def comment_finish(message: Message, state: FSMContext):
    db = load_db()
    data = await state.get_data()
    post_id = data['post_id']
    user = next(u for u in db['approved'] if u['user_id'] == message.from_user.id)
    
    if post_id < 1 or post_id > len(db['posts']):
        await message.answer("❌ Неверный номер поста")
        await state.clear()
        return
    
    comment = {
        'author_id': message.from_user.id,
        'author_name': f"{user['last_name']} {user['first_name']}",
        'text': message.text,
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    db['posts'][post_id-1]['comments'].append(comment)
    save_db(db)
    await message.answer("✅ Комментарий добавлен!")
    await state.clear()

# Система жалоб
@router.message(Command("complain"))
async def cmd_complain(message: Message):
    if await check_ban(message.from_user.id):
        await message.answer("⛔ Вы заблокированы и не можете отправлять жалобы")
        return
    
    try:
        _, target, *reason_parts = message.text.split(maxsplit=2)
        reason = ' '.join(reason_parts)
        
        db = load_db()
        user = next((u for u in db['approved'] if u['user_id'] == message.from_user.id), None)
        target_user = next((u for u in db['approved'] if u['account_code'] == target or u['username'] == target), None)
        
        if not user:
            await message.answer("❌ Вы не зарегистрированы!")
            return
            
        if not target_user:
            await message.answer("❌ Пользователь не найден")
            return
            
        if target_user['user_id'] == message.from_user.id:
            await message.answer("❌ Нельзя жаловаться на себя")
            return
            
        complaint = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'target_id': target_user['user_id'],
            'target_name': f"{target_user['last_name']} {target_user['first_name']}",
            'target_code': target_user['account_code'],
            'complainant_id': message.from_user.id,
            'complainant_name': f"{user['last_name']} {user['first_name']}",
            'reason': reason,
            'status': 'new'
        }
        
        # Сохраняем жалобу в отдельный файл
        complaints = []
        if os.path.exists(COMPLAINTS_FILE):
            with open(COMPLAINTS_FILE, 'r', encoding='utf-8') as f:
                complaints = json.load(f)
        
        complaints.append(complaint)
        with open(COMPLAINTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(complaints, f, ensure_ascii=False, indent=2)
        
        # Уведомление админа
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text="✉️ Ответить",
                callback_data=f"reply_to_{message.from_user.id}"
            ),
            InlineKeyboardButton(
                text="🔨 Забанить",
                callback_data=f"ban_from_{message.from_user.id}_{target_user['account_code']}"
            )
        )
        
        await bot.send_message(
            ADMIN_ID,
            f"🚨 Новая жалоба:\nОт: {user['last_name']} {user['first_name']}\nНа: {target_user['last_name']} {target_user['first_name']}\nПричина: {reason}",
            reply_markup=builder.as_markup()
        )
        
        await message.answer("✅ Жалоба отправлена администратору")
    except:
        await message.answer("❌ Формат: /complain [код/username] [причина]")

# Система поддержки
@router.message(Command("support"))
async def cmd_support(message: Message):
    if await check_ban(message.from_user.id):
        await message.answer("⛔ Вы заблокированы и не можете обращаться в поддержку")
        return
    
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("ℹ️ Укажите ваш вопрос после команды /support")
            return
        
        db = load_db()
        user = next((u for u in db['approved'] if u['user_id'] == message.from_user.id), None)
        
        if not user:
            await message.answer("❌ Вы не зарегистрированы!")
            return
        
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text="✉️ Ответить",
                callback_data=f"reply_to_{message.from_user.id}"
            )
        )
        
        await bot.send_message(
            ADMIN_ID,
            f"🆘 Запрос в поддержку:\nОт: {user['last_name']} {user['first_name']}\nКод: {user['account_code']}\nВопрос: {args[1]}",
            reply_markup=builder.as_markup()
        )
        
        await message.answer("✅ Ваш запрос отправлен администратору")
    except Exception as e:
        logging.error(f"Ошибка поддержки: {e}")
        await message.answer("❌ Произошла ошибка при отправке запроса")

# Админ-команды
class SupportStates(StatesGroup):
    waiting_support_reply = State()

@router.message(Command("support"))
async def cmd_support(message: Message):
    """Обработчик команды /support"""
    db = load_db()
    
    # Проверка регистрации
    if not any(user['user_id'] == message.from_user.id for user in db['approved']):
        await message.answer("❌ Для использования этой команды нужно зарегистрироваться (/reg)")
        return
    
    # Получаем текст сообщения
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("ℹ️ Пожалуйста, укажите ваш вопрос:\nПример: /support Как создать пост?")
        return
    
    user = next(u for u in db['approved'] if u['user_id'] == message.from_user.id)
    user_name = f"{user['last_name']} {user['first_name']}"
    
    # Формируем сообщение для админа
    admin_msg = (
        f"🆘 Новая заявка в поддержку:\n\n"
        f"От: {user_name} (@{user['username']})\n"
        f"Код: {user['account_code']}\n"
        f"Сообщение:\n{args[1]}"
    )
    
    # Кнопка "Ответить" для админа
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(
            text="✉️ Ответить",
            callback_data=f"reply_to_{message.from_user.id}"
        )
    )
    
    try:
        await bot.send_message(
            ADMIN_ID,
            admin_msg,
            reply_markup=builder.as_markup()
        )
        await message.answer("✅ Ваше сообщение отправлено администратору")
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")
        await message.answer("❌ Произошла ошибка при отправке")

@router.callback_query(F.data.startswith("reply_to_"))
async def process_support_reply(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки ответа"""
    user_id = int(callback.data.split('_')[-1])
    await callback.message.edit_reply_markup()  # Убираем кнопку
    
    await state.update_data(support_user_id=user_id)
    await callback.message.answer(f"💬 Введите ответ для пользователя (ID: {user_id}):")
    await state.set_state(SupportStates.waiting_support_reply)

@router.message(SupportStates.waiting_support_reply)
async def send_support_reply(message: Message, state: FSMContext):
    """Отправка ответа пользователю"""
    data = await state.get_data()
    user_id = data.get('support_user_id')
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    try:
        await bot.send_message(
            user_id,
            f"📩 Ответ от поддержки:\n\n{message.text}"
        )
        await message.answer(f"✅ Ответ отправлен пользователю (ID: {user_id})")
    except Exception as e:
        logging.error(f"Ошибка отправки ответа: {e}")
        await message.answer("❌ Не удалось отправить ответ")
    
    await state.clear()

@router.message(Command("adminstart"))
async def cmd_adminstart(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав для этой команды!")
        return

    db = load_db()
    sent_count = 0
    
    for user in db['approved']:
        try:
            await bot.send_message(user['user_id'], "Технические работы завершены! Теперь соцсеть снова работает! ")
            sent_count += 1
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {user['user_id']}: {e}")
    
    await message.answer(f"✅ Сообщение отправлено {sent_count} пользователям!")

@router.message(Command("users"))
async def users_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступно только администраторам")
        return
    
    db = load_db()
    text = "👥 Список пользователей:\n\n"
    for user in db['approved']:
        text += f"{user['last_name']} {user['first_name']} - {user['class']}\n"
        text += f"Код: {user['account_code']} | @{user['username']}\n\n"
    
    await message.answer(text)

@router.message(Command("broadcast"))
async def broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступно только администраторам")
        return
    
    if len(message.text.split()) < 2:
        await message.answer("❌ Формат: /broadcast [текст]")
        return
    
    db = load_db()
    text = ' '.join(message.text.split()[1:])
    sent = 0
    
    for user in db['approved']:
        try:
            await bot.send_message(user['user_id'], f"📢 Сообщение от администратора:\n\n{text}")
            sent += 1
        except:
            continue
    
    await message.answer(f"✅ Сообщение отправлено {sent} пользователям")

@router.message(Command("update"))
async def update_bot(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступно только администраторам")
        return
    
    db = load_db()
    sent = 0
    
    for user in db['approved']:
        try:
            await bot.send_message(
                user['user_id'],
                "🔧 Технические работы\n\n"
                "Соцсеть будет временно недоступна из-за обновлений. "
                "Приносим извинения за неудобства!"
            )
            sent += 1
        except:
            continue
    
    await message.answer(f"✅ Уведомление отправлено {sent} пользователям. Бот завершает работу...")
    save_db(db)  # Сохраняем данные перед выходом
    exit(0)

# ========== ОБРАБОТКА КНОПОК ==========
@router.callback_query(F.data.startswith("approve_") | F.data.startswith("reject_"))
async def process_registration(callback: CallbackQuery):
    db = load_db()
    action, user_id = callback.data.split('_')
    user_id = int(user_id)
    
    user = next((u for u in db['pending'] if u['user_id'] == user_id), None)
    if not user:
        await callback.answer("Пользователь не найден")
        return
    
    if action == "approve":
        db['approved'].append(user)
        await bot.send_message(
            user_id,
            "🎉 Ваша заявка одобрена! Теперь вы можете пользоваться всеми функциями."
        )
        await callback.message.edit_text(
            f"✅ Заявка {user['last_name']} {user['first_name']} одобрена"
        )
    else:
        await bot.send_message(
            user_id,
            "😕 Ваша заявка была отклонена администратором."
        )
        await callback.message.edit_text(
            f"❌ Заявка {user['last_name']} {user['first_name']} отклонена"
        )
    
    db['pending'].remove(user)
    save_db(db)
    await callback.answer()

@router.message(Command("adminstart"))
async def cmd_adminstart(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав для этой команды!")
        return

    db = load_db()
    sent_count = 0
    
    for user in db['approved']:
        try:
            await bot.send_message(user['user_id'], "Технические работы завершены! Теперь соцсеть снова работает! ")
            sent_count += 1
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {user['user_id']}: {e}")
    cmd_help
    await message.answer(f"✅ Сообщение отправлено {sent_count} пользователям!")

@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда только для администраторов")
        return
    
    try:
        args = message.text.split()
        if len(args) < 3:
            await message.answer("ℹ️ Формат: /ban [код] [время] [причина]\nПример: /ban 123456 7d Нарушение правил")
            return
        
        target_code = args[1]
        ban_duration = args[2]
        reason = ' '.join(args[3:]) if len(args) > 3 else "Не указана"
        db = load_db()
        
        target_user = next((u for u in db['approved'] if u['account_code'] == target_code), None)
        if not target_user:
            await message.answer("❌ Пользователь с таким кодом не найден")
            return
        
        if ban_duration.endswith('d'):
            days = int(ban_duration[:-1])
            ban_until = datetime.now() + timedelta(days=days)
        elif ban_duration.endswith('h'):
            hours = int(ban_duration[:-1])
            ban_until = datetime.now() + timedelta(hours=hours)
        else:
            await message.answer("❌ Укажите время бана в формате: 7d (7 дней) или 24h (24 часа)")
            return
        
        target_user['banned_until'] = ban_until.strftime("%Y-%m-%d %H:%M:%S")
        save_db(db)
        
        try:
            await bot.send_message(
                target_user['user_id'],
                f"⛔ Вы были заблокированы до {ban_until.strftime('%d.%m.%Y %H:%M')}\nПричина: {reason}"
            )
        except:
            pass  # Пользователь мог заблокировать бота
        
        await message.answer(f"✅ Пользователь {target_user['last_name']} {target_user['first_name']} заблокирован до {ban_until.strftime('%d.%m.%Y %H:%M')}")
    except Exception as e:
        logging.error(f"Ошибка бана: {e}")
        await message.answer("❌ Произошла ошибка при блокировке пользователя")

@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда только для администраторов")
        return
    
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("ℹ️ Формат: /unban [код]")
            return
        
        target_code = args[1]
        db = load_db()
        
        target_user = next((u for u in db['approved'] if u['account_code'] == target_code), None)
        if not target_user:
            await message.answer("❌ Пользователь с таким кодом не найден")
            return
        
        target_user['banned_until'] = None
        save_db(db)
        
        try:
            await bot.send_message(
                target_user['user_id'],
                "✅ Ваша блокировка снята администратором. Теперь вы снова можете пользоваться всеми функциями."
            )
        except:
            pass  # Пользователь мог заблокировать бота
        
        await message.answer(f"✅ Пользователь {target_user['last_name']} {target_user['first_name']} разблокирован")
    except Exception as e:
        logging.error(f"Ошибка разбана: {e}")
        await message.answer("❌ Произошла ошибка при разблокировке пользователя")

@router.message(Command("complaints"))
async def cmd_complaints(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда только для администраторов")
        return
    
    if not os.path.exists(COMPLAINTS_FILE):
        await message.answer("ℹ️ Жалоб нет")
        return
    
    try:
        with open(COMPLAINTS_FILE, 'r', encoding='utf-8') as f:
            complaints = json.load(f)
        
        if not complaints:
            await message.answer("ℹ️ Жалоб нет")
            return
        
        text = "📜 Список жалоб:\n\n"
        for i, comp in enumerate(complaints[-10:][::-1], 1):  # Последние 10 жалоб
            text += f"{i}. От: {comp['complainant_name']}\nНа: {comp['target_name']}\nПричина: {comp['reason']}\nДата: {comp['timestamp']}\n\n"
        
        await message.answer(text)
    except Exception as e:
        logging.error(f"Ошибка загрузки жалоб: {e}")
        await message.answer("❌ Произошла ошибка при загрузке жалоб")

@router.message(Command("users"))
async def cmd_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда только для администраторов")
        return
    
    db = load_db()
    text = "👥 Список пользователей:\n\n"
    for user in db['approved']:
        status = "🛑 Заблокирован" if user.get('banned_until') else "✅ Активен"
        text += f"{user['last_name']} {user['first_name']} ({status})\n"
        text += f"Код: {user['account_code']} | @{user['username']}\n\n"
    
    await message.answer(text)

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда только для администраторов")
        return
    
    if len(message.text.split()) < 2:
        await message.answer("ℹ️ Формат: /broadcast [текст]")
        return
    
    db = load_db()
    text = ' '.join(message.text.split()[1:])
    sent = 0
    
    for user in db['approved']:
        try:
            await bot.send_message(user['user_id'], f"📢 Важное объявление:\n\n{text}")
            sent += 1
        except:
            continue
    
    await message.answer(f"✅ Сообщение отправлено {sent} пользователям")

# Обработчики callback-кнопок
@router.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery):
    db = load_db()
    user_id = int(callback.data.split('_')[1])
    user = next((u for u in db['pending'] if u['user_id'] == user_id), None)
    
    if user:
        db['approved'].append(user)
        db['pending'].remove(user)
        save_db(db)
        
        try:
            await bot.send_message(user_id, "🎉 Ваша заявка одобрена! Теперь вы можете пользоваться всеми функциями.")
        except:
            pass
        
        await callback.message.edit_text(f"✅ Пользователь {user['last_name']} {user['first_name']} одобрен")
    else:
        await callback.answer("Пользователь не найден")

@router.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery):
    db = load_db()
    user_id = int(callback.data.split('_')[1])
    user = next((u for u in db['pending'] if u['user_id'] == user_id), None)
    
    if user:
        db['pending'].remove(user)
        save_db(db)
        
        try:
            await bot.send_message(user_id, "😕 Ваша заявка была отклонена администратором.")
        except:
            pass
        
        await callback.message.edit_text(f"❌ Заявка {user['last_name']} {user['first_name']} отклонена")
    else:
        await callback.answer("Пользователь не найден")

@router.callback_query(F.data.startswith("reply_to_"))
async def reply_to_user(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split('_')[2])
    await callback.message.edit_reply_markup()
    await state.update_data(support_user_id=user_id)
    await callback.message.answer(f"💬 Введите ответ для пользователя (ID: {user_id}):")
    await state.set_state(SupportStates.waiting_support_reply)

@router.callback_query(F.data.startswith("ban_from_"))
async def ban_from_complaint(callback: CallbackQuery):
    parts = callback.data.split('_')
    user_id = int(parts[2])  # ID жалобщика
    target_code = parts[3]   # Код пользователя для бана
    
    db = load_db()
    target_user = next((u for u in db['approved'] if u['account_code'] == target_code), None)
    
    if target_user:
        # Бан на 3 дня по умолчанию
        ban_until = datetime.now() + timedelta(days=3)
        target_user['banned_until'] = ban_until.strftime("%Y-%m-%d %H:%M:%S")
        save_db(db)
        
        try:
            await bot.send_message(
                target_user['user_id'],
                f"⛔ Вы были заблокированы до {ban_until.strftime('%d.%m.%Y %H:%M')} по жалобе пользователя"
            )
        except:
            pass
        
        await callback.message.edit_text(
            f"✅ Пользователь {target_user['last_name']} {target_user['first_name']} заблокирован до {ban_until.strftime('%d.%m.%Y %H:%M')}"
        )
        
        # Уведомляем жалобщика
        try:
            await bot.send_message(
                user_id,
                f"ℹ️ Пользователь {target_user['last_name']} {target_user['first_name']} был заблокирован по вашей жалобе"
            )
        except:
            pass
    else:
        await callback.answer("Пользователь не найден")

@router.message(SupportStates.waiting_support_reply)
async def send_support_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('support_user_id')
    
    if not user_id:
        await message.answer("❌ Не удалось определить получателя")
        await state.clear()
        return
    
    try:
        await bot.send_message(
            user_id,
            f"📩 Ответ от поддержки:\n\n{message.text}"
        )
        await message.answer(f"✅ Ответ отправлен пользователю (ID: {user_id})")
    except Exception as e:
        logging.error(f"Ошибка отправки ответа: {e}")
        await message.answer("❌ Не удалось отправить ответ. Пользователь возможно заблокировал бота.")
    
    await state.clear()

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
