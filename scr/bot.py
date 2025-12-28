import telebot
from telebot import types
from datetime import datetime, timedelta
import config
from logic import BotLogic

bot = telebot.TeleBot(config.TOKEN)
logic = BotLogic()

def is_admin(user_id):
    return user_id in config.ADMIN_IDS

def extract_user_info(message):
    if message.reply_to_message:
        user = message.reply_to_message.from_user
        return user.id, user.username or user.first_name
    
    parts = message.text.split()
    if len(parts) > 1:
        for part in parts[1:]:
            if part.startswith('@'):
                return None, part[1:]
            elif part.isdigit():
                return int(part), None
    
    return None, None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = """🤖 Админ-бот

Для админов:
/warn - выдать предупреждение
/mute [время] - замьютить
/ban [время] - забанить
/unmute - снять мут
/unban - разбанить
/warns - проверить варны
/reset_warns - сбросить варны
/reports - показать репорты
/welcome - вкл/выкл приветствие

Для всех:
/report [причина] - пожаловаться (ответом)
/mywarns - мои варны

Примеры:
/warn id_user
/mute 2h id_user
/ban 1d id_user
/report спам

Форматы времени:
30m - 30 минут
2h - 2 часа
1d - 1 день
permanent - навсегда"""
    
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['warn'])
def warn_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Нужны права администратора")
        return
    
    user_id, username = extract_user_info(message)
    if not user_id and not username:
        bot.reply_to(message, "❌ Укажите пользователя (ответом или @username)")
        return
    
    if username and not user_id:
        bot.reply_to(message, "❌ Укажите ID пользователя или ответьте на сообщение")
        return
    
    warns = logic.add_warn(user_id, message.chat.id)
    bot.reply_to(message, f"⚠️ Предупреждение выдано. Всего: {warns}/{config.MAX_WARNS}")
    
    if warns >= config.MAX_WARNS:
        logic.ban_user(user_id, message.chat.id)
        bot.ban_chat_member(message.chat.id, user_id)
        bot.reply_to(message, f"🚫 Пользователь забанен за {config.MAX_WARNS} предупреждения!")

@bot.message_handler(commands=['warns'])
def warns_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Нужны права администратора")
        return
    
    user_id, username = extract_user_info(message)
    if not user_id and not username:
        bot.reply_to(message, "❌ Укажите пользователя")
        return
    
    if username and not user_id:
        bot.reply_to(message, "❌ Укажите ID пользователя")
        return
    
    user = logic.get_user(user_id, message.chat.id)
    if user:
        warns = user[4]
        bot.reply_to(message, f"📊 Варнов: {warns}/{config.MAX_WARNS}")
    else:
        bot.reply_to(message, "❌ Пользователь не найден")

@bot.message_handler(commands=['mywarns'])
def my_warns_command(message):
    user = logic.get_user(message.from_user.id, message.chat.id)
    if user:
        warns = user[4]
        bot.reply_to(message, f"📊 Ваши варны: {warns}/{config.MAX_WARNS}")
    else:
        logic.add_user(message.from_user.id, message.chat.id, 
                      message.from_user.username, message.from_user.first_name)
        bot.reply_to(message, "📊 У вас нет варнов")

@bot.message_handler(commands=['reset_warns'])
def reset_warns_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Нужны права администратора")
        return
    
    user_id, username = extract_user_info(message)
    if not user_id and not username:
        bot.reply_to(message, "❌ Укажите пользователя")
        return
    
    if username and not user_id:
        bot.reply_to(message, "❌ Укажите ID пользователя")
        return
    
    logic.reset_warns(user_id, message.chat.id)
    bot.reply_to(message, "✅ Варны сброшены")

@bot.message_handler(commands=['mute'])
def mute_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Нужны права администратора")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используйте: /mute [время] [пользователь]\nПример: /mute 1h user_id")
        return
    
    time_str = parts[1]
    seconds = logic.parse_time(time_str)
    if not seconds:
        seconds = 3600
    
    user_id, username = extract_user_info(message)
    if not user_id and not username:
        if len(parts) > 2 and parts[2].startswith('@'):
            username = parts[2][1:]
            bot.reply_to(message, f"❌ Нужен ID пользователя {username}")
            return
        else:
            bot.reply_to(message, "❌ Укажите пользователя")
            return
    
    if username and not user_id:
        bot.reply_to(message, f"❌ Нужен ID пользователя {username}")
        return
    
    logic.mute_user(user_id, message.chat.id, seconds)
    
    if seconds >= 315360000:
        until_date = None
    else:
        until_date = datetime.now() + timedelta(seconds=seconds)
    
    bot.restrict_chat_member(
        message.chat.id,
        user_id,
        until_date=until_date,
        permissions=types.ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
    )
    
    duration = logic.format_time(seconds)
    bot.reply_to(message, f"🔇 Пользователь замьючен на {duration}")

@bot.message_handler(commands=['unmute'])
def unmute_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Нужны права администратора")
        return
    
    user_id, username = extract_user_info(message)
    if not user_id and not username:
        bot.reply_to(message, "❌ Укажите пользователя")
        return
    
    if username and not user_id:
        bot.reply_to(message, "❌ Укажите ID пользователя")
        return
    
    logic.unmute_user(user_id, message.chat.id)
    
    bot.restrict_chat_member(
        message.chat.id,
        user_id,
        permissions=types.ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
    )
    
    bot.reply_to(message, "🔊 Мут снят")

@bot.message_handler(commands=['ban'])
def ban_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Нужны права администратора")
        return
    
    parts = message.text.split()
    time_str = 'permanent' if len(parts) < 2 else parts[1]
    seconds = logic.parse_time(time_str) or 86400
    
    user_id, username = extract_user_info(message)
    if not user_id and not username:
        if len(parts) > 2 and parts[2].startswith('@'):
            username = parts[2][1:]
            bot.reply_to(message, f"❌ Нужен ID пользователя {username}")
            return
        else:
            bot.reply_to(message, "❌ Укажите пользователя")
            return
    
    if username and not user_id:
        bot.reply_to(message, f"❌ Нужен ID пользователя {username}")
        return
    
    logic.ban_user(user_id, message.chat.id)
    
    if seconds >= 315360000:
        bot.ban_chat_member(message.chat.id, user_id)
    else:
        until_date = datetime.now() + timedelta(seconds=seconds)
        bot.ban_chat_member(message.chat.id, user_id, until_date=until_date)
    
    duration = logic.format_time(seconds)
    bot.reply_to(message, f"🚫 Пользователь забанен на {duration}")

@bot.message_handler(commands=['unban'])
def unban_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Нужны права администратора")
        return
    
    user_id, username = extract_user_info(message)
    if not user_id and not username:
        bot.reply_to(message, "❌ Укажите ID пользователя")
        return
    
    if username and not user_id:
        bot.reply_to(message, "❌ Укажите ID пользователя")
        return
    
    logic.unban_user(user_id, message.chat.id)
    bot.unban_chat_member(message.chat.id, user_id)
    bot.reply_to(message, "✅ Пользователь разбанен")

@bot.message_handler(commands=['report'])
def report_command(message):
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответьте на сообщение пользователя")
        return
    
    reported_user = message.reply_to_message.from_user
    reporter_user = message.from_user
    
    reason = ' '.join(message.text.split()[1:]) or "Причина не указана"
    
    report_id = logic.add_report(
        message.chat.id,
        reporter_user.id,
        reported_user.id,
        reason
    )
    
    for admin_id in config.ADMIN_IDS:
        bot.send_message(
            admin_id,
            f"🚨 Новый репорт #{report_id}\nЧат: {message.chat.title or message.chat.id}\nНа кого: {reported_user.first_name} (ID: {reported_user.id})\nПричина: {reason}"
        )
    
    bot.reply_to(message, f"✅ Репорт #{report_id} отправлен")

@bot.message_handler(commands=['reports'])
def reports_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Нужны права администратора")
        return
    
    reports = logic.get_pending_reports(message.chat.id)
    if not reports:
        bot.reply_to(message, "📭 Нет репортов")
        return
    
    text = "📋 Репорты:\n\n"
    for report in reports[:5]:
        report_id, chat_id, reporter_id, reported_id, reason, status, created_at = report
        text += f"ID: {report_id}\n"
        text += f"На кого: {reported_id}\n"
        text += f"Причина: {reason[:30]}...\n"
        text += f"———\n"
    
    bot.reply_to(message, text)

@bot.message_handler(regexp=r'^/resolve_(\d+)$')
def resolve_command(message):
    if not is_admin(message.from_user.id):
        return
    
    report_id = int(message.text.split('_')[1])
    logic.mark_report_resolved(report_id)
    bot.reply_to(message, f"✅ Репорт #{report_id} решен")

@bot.message_handler(commands=['welcome'])
def welcome_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Нужны права администратора")
        return
    
    logic.toggle_welcome(message.chat.id)
    chat = logic.get_chat(message.chat.id)
    
    if chat and chat[1] == 1:
        bot.reply_to(message, "✅ Приветствие включено")
    else:
        bot.reply_to(message, "❌ Приветствие выключено")

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    logic.add_chat(message.chat.id)
    
    chat = logic.get_chat(message.chat.id)
    if not chat or chat[1] != 1:
        return
    
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            continue
        
        logic.add_user(
            member.id,
            message.chat.id,
            member.username,
            member.first_name
        )
        
        welcome = config.WELCOME_MESSAGE.format(
            username=f"@{member.username}" if member.username else member.first_name
        )
        bot.reply_to(message, welcome)

@bot.message_handler(func=lambda message: True)
def check_mute(message):
    if message.from_user.id == bot.get_me().id:
        return
    
    if logic.is_muted(message.from_user.id, message.chat.id):
        bot.delete_message(message.chat.id, message.message_id)
        bot.send_message(
            message.chat.id,
            f"⚠️ Вы замьючены и не можете писать",
            reply_to_message_id=message.message_id
        )

if __name__ == '__main__':
    bot.infinity_polling()