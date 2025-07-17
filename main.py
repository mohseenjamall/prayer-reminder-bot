import os
import logging
import schedule
import time
import threading
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import random
import json
import asyncio

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token البوت (احصل عليه من BotFather)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7476661316:AAE3JO7zSVogD7kmgDakrxxj5WyzfOTTBvk')

# تخزين بيانات المستخدمين في الذاكرة
users_data = {}
# تخزين المهام المجدولة
scheduled_jobs = {}
# الفترة الافتراضية (10 دقائق)
DEFAULT_INTERVAL = 10
# queue للرسائل
message_queue = []

# رسائل الصلاة على النبي
prayer_messages = [
    "🌹 اللهم صل وسلم وبارك على نبينا محمد ﷺ",
    "🤲 صلى الله عليه وسلم",
    "💫 اللهم صل على محمد وعلى آل محمد",
    "🌟 اللهم صل وسلم على سيدنا محمد الحبيب المصطفى ﷺ",
    "🕊️ عليه أفضل الصلاة وأتم التسليم",
    "🌙 اللهم صل على من أرسلته رحمة للعالمين ﷺ",
    "⭐ صلوا على النبي المختار ﷺ",
    "🌺 اللهم صل وسلم على الرسول الكريم ﷺ"
]

def get_keyboard():
    """لوحة مفاتيح مخصصة"""
    keyboard = [
        [KeyboardButton("⏰ تغيير الفترة"), KeyboardButton("📋 إعداداتي")],
        [KeyboardButton("⏹️ إيقاف التذكيرات"), KeyboardButton("▶️ تشغيل التذكيرات")],
        [KeyboardButton("ℹ️ المساعدة")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البدء"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    # تسجيل المستخدم
    if user_id not in users_data:
        users_data[user_id] = {
            'username': username,
            'interval': DEFAULT_INTERVAL,  # الفترة الافتراضية
            'is_active': True,
            'created_at': datetime.now().isoformat(),
            'last_reminder': None
        }
        # بدء التذكيرات للمستخدم الجديد
        start_user_reminders(user_id)
    else:
        # إذا كان المستخدم موجود وتم إيقاف التذكيرات، نعيد تشغيلها
        if users_data[user_id]['is_active'] and user_id not in scheduled_jobs:
            start_user_reminders(user_id)
    
    welcome_message = f"""
🌟 أهلاً وسهلاً {username}!

🤲 هذا بوت تذكير الصلاة على النبي محمد ﷺ

📱 الميزات المتاحة:
• تذكير كل {DEFAULT_INTERVAL} دقائق (افتراضي)
• يمكن تغيير الفترة من 1 دقيقة إلى 60 دقيقة
• رسائل تذكير متنوعة
• تحكم كامل في التذكيرات

🎯 استخدم الأزرار بالأسفل أو الأوامر:
/set_interval - تغيير فترة التذكير
/my_settings - عرض إعداداتي
/help - المساعدة

بارك الله فيك! 🌹
"""
    await update.message.reply_text(welcome_message, reply_markup=get_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر المساعدة"""
    help_text = """
📖 دليل استخدام البوت:

🔹 الأوامر الأساسية:
• /set_interval - تغيير فترة التذكير
• /my_settings - عرض إعداداتي الحالية
• /stop - إيقاف التذكيرات
• /start_reminders - تشغيل التذكيرات

🔹 فترات التذكير المتاحة:
• من 1 دقيقة إلى 60 دقيقة
• الافتراضي: 10 دقائق
• أمثلة: 5 دقائق، 15 دقيقة، 30 دقيقة

🔹 مثال على الاستخدام:
1. اضغط "تغيير الفترة"
2. اكتب رقم من 1 إلى 60
3. سيتم التذكير كل هذا العدد من الدقائق

🤲 بارك الله فيك!
"""
    await update.message.reply_text(help_text, reply_markup=get_keyboard())

async def set_interval_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء تغيير فترة التذكير"""
    await update.message.reply_text(
        "⏰ أرسل فترة التذكير بالدقائق\n\n"
        "🔹 الحد الأدنى: 1 دقيقة\n"
        "🔹 الحد الأقصى: 60 دقيقة\n"
        "🔹 الافتراضي: 10 دقائق\n\n"
        "📝 أمثلة: 5 أو 15 أو 30\n\n"
        "اكتب الرقم فقط:"
    )
    # تسجيل أن المستخدم في حالة تغيير الفترة
    users_data[update.effective_user.id]['awaiting_interval'] = True

async def handle_interval_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال فترة التذكير"""
    user_id = update.effective_user.id
    interval_text = update.message.text.strip()
    
    try:
        interval = int(interval_text)
        
        # التحقق من صحة الفترة
        if 1 <= interval <= 60:
            # تحديث الفترة
            users_data[user_id]['interval'] = interval
            users_data[user_id]['awaiting_interval'] = False
            
            # إعادة جدولة التذكيرات
            if users_data[user_id]['is_active']:
                restart_user_reminders(user_id)
            
            await update.message.reply_text(
                f"✅ تم تغيير فترة التذكير بنجاح!\n"
                f"⏰ الفترة الجديدة: كل {interval} دقيقة\n\n"
                f"🔄 إذا كانت التذكيرات مفعلة، ستعمل بالفترة الجديدة\n\n"
                f"🤲 بارك الله فيك!",
                reply_markup=get_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ الفترة خارج النطاق المسموح!\n\n"
                "🔹 الحد الأدنى: 1 دقيقة\n"
                "🔹 الحد الأقصى: 60 دقيقة\n\n"
                "💡 جرب رقم آخر:",
                reply_markup=get_keyboard()
            )
            
    except ValueError:
        await update.message.reply_text(
            "❌ يرجى إدخال رقم صحيح!\n\n"
            "🔹 مثال: 5 أو 10 أو 15\n"
            "🔹 من 1 إلى 60 دقيقة\n\n"
            "💡 جرب مرة أخرى:",
            reply_markup=get_keyboard()
        )

async def my_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إعدادات المستخدم"""
    user_id = update.effective_user.id
    
    if user_id not in users_data:
        await update.message.reply_text(
            "❌ استخدم /start أولاً",
            reply_markup=get_keyboard()
        )
        return
    
    user_data = users_data[user_id]
    interval = user_data['interval']
    status = "🟢 مفعل" if user_data['is_active'] else "🔴 متوقف"
    last_reminder = user_data.get('last_reminder', 'لم يتم إرسال تذكير بعد')
    
    if last_reminder and last_reminder != 'لم يتم إرسال تذكير بعد':
        last_reminder = datetime.fromisoformat(last_reminder).strftime('%Y-%m-%d %H:%M')
    
    message = f"""
📋 إعداداتك الحالية:

⏰ فترة التذكير: كل {interval} دقيقة
📊 الحالة: {status}
🕐 آخر تذكير: {last_reminder}

🔹 لتغيير الفترة استخدم /set_interval
🔹 لإيقاف التذكيرات استخدم /stop
🔹 لتشغيل التذكيرات استخدم /start_reminders
"""
    
    await update.message.reply_text(message, reply_markup=get_keyboard())

async def stop_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إيقاف التذكيرات"""
    user_id = update.effective_user.id
    
    if user_id in users_data:
        users_data[user_id]['is_active'] = False
        
        # إلغاء المهمة المجدولة للمستخدم
        if user_id in scheduled_jobs:
            schedule.cancel_job(scheduled_jobs[user_id])
            del scheduled_jobs[user_id]
        
        await update.message.reply_text(
            "⏹️ تم إيقاف التذكيرات\n\n"
            "🔹 إعداداتك محفوظة ويمكنك إعادة تشغيلها\n"
            "🔹 استخدم /start_reminders لإعادة التشغيل",
            reply_markup=get_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ استخدم /start أولاً",
            reply_markup=get_keyboard()
        )

async def start_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تشغيل التذكيرات"""
    user_id = update.effective_user.id
    
    if user_id in users_data:
        users_data[user_id]['is_active'] = True
        
        # بدء التذكيرات بالفترة المحددة
        start_user_reminders(user_id)
        
        interval = users_data[user_id]['interval']
        await update.message.reply_text(
            f"▶️ تم تشغيل التذكيرات بنجاح!\n\n"
            f"⏰ الفترة: كل {interval} دقيقة\n"
            f"📋 استخدم /my_settings لعرض إعداداتك",
            reply_markup=get_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ استخدم /start أولاً",
            reply_markup=get_keyboard()
        )

def start_user_reminders(user_id: int):
    """بدء تذكيرات المستخدم"""
    if user_id not in users_data:
        return
    
    # إيقاف أي تذكيرات سابقة أولاً
    if user_id in scheduled_jobs:
        schedule.cancel_job(scheduled_jobs[user_id])
        del scheduled_jobs[user_id]
    
    interval = users_data[user_id]['interval']
    
    def send_reminder():
        """إرسال التذكير"""
        try:
            # تحديث وقت آخر تذكير
            users_data[user_id]['last_reminder'] = datetime.now().isoformat()
            
            # اختيار رسالة عشوائية
            message = random.choice(prayer_messages)
            
            # إضافة الرسالة للـ queue بدلاً من الإرسال المباشر
            message_queue.append({
                'user_id': user_id,
                'message': f"{message}\n\n💫 تذكير من بوت الصلاة على النبي ﷺ"
            })
            
        except Exception as e:
            logger.error(f"خطأ في إرسال التذكير للمستخدم {user_id}: {e}")
    
    # إنشاء المهمة المجدولة
    job = schedule.every(interval).minutes.do(send_reminder)
    
    # حفظ المهمة
    scheduled_jobs[user_id] = job

def restart_user_reminders(user_id: int):
    """إعادة تشغيل تذكيرات المستخدم بفترة جديدة"""
    # إيقاف التذكيرات الحالية
    if user_id in scheduled_jobs:
        schedule.cancel_job(scheduled_jobs[user_id])
        del scheduled_jobs[user_id]
    
    # بدء التذكيرات بالفترة الجديدة
    if users_data[user_id]['is_active']:
        start_user_reminders(user_id)

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # التحقق من حالة المستخدم
    if user_id in users_data:
        user_data = users_data[user_id]
        
        # إذا كان ينتظر إدخال فترة
        if user_data.get('awaiting_interval'):
            await handle_interval_input(update, context)
            return
    
    # معالجة الأزرار
    if text == "⏰ تغيير الفترة":
        await set_interval_start(update, context)
    elif text == "📋 إعداداتي":
        await my_settings(update, context)
    elif text == "⏹️ إيقاف التذكيرات":
        await stop_reminders(update, context)
    elif text == "▶️ تشغيل التذكيرات":
        await start_reminders(update, context)
    elif text == "ℹ️ المساعدة":
        await help_command(update, context)
    else:
        # رسالة افتراضية
        await update.message.reply_text(
            "🤔 لم أفهم طلبك\n\n"
            "🔹 استخدم الأزرار بالأسفل\n"
            "🔹 أو اكتب /help للمساعدة",
            reply_markup=get_keyboard()
        )

def main():
    """الدالة الرئيسية"""
    global application
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("set_interval", set_interval_start))
    application.add_handler(CommandHandler("my_settings", my_settings))
    application.add_handler(CommandHandler("stop", stop_reminders))
    application.add_handler(CommandHandler("start_reminders", start_reminders))
    
    # معالج الرسائل النصية
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    
    # تشغيل المهام المجدولة في خيط منفصل
    schedule_thread = threading.Thread(target=run_schedule, daemon=True)
    schedule_thread.start()
    
    # تشغيل البوت
    logger.info("🚀 بدء تشغيل البوت...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
