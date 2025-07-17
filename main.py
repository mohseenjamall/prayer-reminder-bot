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
        [KeyboardButton("⏰ إضافة وقت تذكير"), KeyboardButton("📋 أوقاتي")],
        [KeyboardButton("🗑️ حذف وقت"), KeyboardButton("⏹️ إيقاف التذكيرات")],
        [KeyboardButton("▶️ تشغيل التذكيرات"), KeyboardButton("ℹ️ المساعدة")]
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
            'reminders': [],
            'is_active': True,
            'created_at': datetime.now().isoformat()
        }
    
    welcome_message = f"""
🌟 أهلاً وسهلاً {username}!

🤲 هذا بوت تذكير الصلاة على النبي محمد ﷺ

📱 الميزات المتاحة:
• إضافة أوقات متعددة للتذكير
• رسائل تذكير متنوعة
• تحكم كامل في التذكيرات

🎯 استخدم الأزرار بالأسفل أو الأوامر:
/add_time - إضافة وقت جديد
/my_times - عرض أوقاتي
/help - المساعدة

بارك الله فيك! 🌹
"""
    await update.message.reply_text(welcome_message, reply_markup=get_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر المساعدة"""
    help_text = """
📖 دليل استخدام البوت:

🔹 الأوامر الأساسية:
• /add_time - إضافة وقت تذكير جديد
• /my_times - عرض جميع أوقاتي
• /delete_time - حذف وقت معين
• /stop - إيقاف جميع التذكيرات
• /start_reminders - تشغيل التذكيرات

🔹 تنسيق الوقت:
• 24 ساعة: 14:30
• 12 ساعة: 2:30 PM
• أمثلة: 07:00 أو 7:00 AM

🔹 مثال على الاستخدام:
1. اضغط "إضافة وقت تذكير"
2. اكتب الوقت مثل: 08:00
3. سيتم إرسال التذكير يومياً

🤲 بارك الله فيك!
"""
    await update.message.reply_text(help_text, reply_markup=get_keyboard())

async def add_time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة وقت جديد"""
    await update.message.reply_text(
        "⏰ أرسل الوقت الذي تريد التذكير فيه\n\n"
        "🔹 أمثلة:\n"
        "• 08:00 (الثامنة صباحاً)\n"
        "• 14:30 (الثانية والنصف ظهراً)\n"
        "• 20:00 (الثامنة مساءً)\n\n"
        "📝 اكتب الوقت فقط بالتنسيق المطلوب:"
    )
    # تسجيل أن المستخدم في حالة إضافة وقت
    users_data[update.effective_user.id]['awaiting_time'] = True

async def handle_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال الوقت"""
    user_id = update.effective_user.id
    time_text = update.message.text.strip()
    
    # التحقق من صحة الوقت
    try:
        # محاولة تحويل النص إلى وقت
        time_obj = datetime.strptime(time_text, '%H:%M').time()
        
        # إضافة الوقت للمستخدم
        if user_id in users_data:
            if time_text not in users_data[user_id]['reminders']:
                users_data[user_id]['reminders'].append(time_text)
                users_data[user_id]['awaiting_time'] = False
                
                # جدولة المهمة
                schedule_user_reminder(user_id, time_text)
                
                await update.message.reply_text(
                    f"✅ تم إضافة التذكير بنجاح!\n"
                    f"🕐 الوقت: {time_text}\n"
                    f"📅 سيتم التذكير يومياً في هذا الوقت\n\n"
                    f"🤲 بارك الله فيك!",
                    reply_markup=get_keyboard()
                )
            else:
                await update.message.reply_text(
                    f"⚠️ هذا الوقت ({time_text}) موجود مسبقاً!\n"
                    f"جرب وقت آخر أو استخدم /my_times لعرض أوقاتك",
                    reply_markup=get_keyboard()
                )
        else:
            await update.message.reply_text(
                "❌ حدث خطأ! استخدم /start أولاً",
                reply_markup=get_keyboard()
            )
            
    except ValueError:
        await update.message.reply_text(
            "❌ تنسيق الوقت غير صحيح!\n\n"
            "🔹 استخدم التنسيق: HH:MM\n"
            "🔹 مثال: 08:30 أو 14:15\n\n"
            "💡 جرب مرة أخرى:",
            reply_markup=get_keyboard()
        )

async def my_times(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أوقات المستخدم"""
    user_id = update.effective_user.id
    
    if user_id not in users_data or not users_data[user_id]['reminders']:
        await update.message.reply_text(
            "📋 لم تقم بإضافة أي أوقات تذكير بعد\n\n"
            "🔹 استخدم /add_time لإضافة وقت جديد",
            reply_markup=get_keyboard()
        )
        return
    
    times_list = "\n".join([f"🕐 {time}" for time in users_data[user_id]['reminders']])
    status = "🟢 مفعل" if users_data[user_id]['is_active'] else "🔴 متوقف"
    
    message = f"""
📋 أوقات التذكير الخاصة بك:

{times_list}

📊 الحالة: {status}
🔢 العدد: {len(users_data[user_id]['reminders'])} تذكير

🔹 لحذف وقت معين استخدم /delete_time
🔹 لإيقاف التذكيرات استخدم /stop
"""
    
    await update.message.reply_text(message, reply_markup=get_keyboard())

async def delete_time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء حذف وقت"""
    user_id = update.effective_user.id
    
    if user_id not in users_data or not users_data[user_id]['reminders']:
        await update.message.reply_text(
            "📋 لا توجد أوقات محفوظة للحذف\n\n"
            "🔹 استخدم /add_time لإضافة وقت جديد",
            reply_markup=get_keyboard()
        )
        return
    
    times_list = "\n".join([f"🕐 {time}" for time in users_data[user_id]['reminders']])
    
    await update.message.reply_text(
        f"🗑️ اختر الوقت الذي تريد حذفه:\n\n{times_list}\n\n"
        f"📝 اكتب الوقت بالضبط كما هو موضح أعلاه:"
    )
    
    users_data[user_id]['awaiting_delete'] = True

async def handle_delete_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة حذف الوقت"""
    user_id = update.effective_user.id
    time_text = update.message.text.strip()
    
    if user_id in users_data and time_text in users_data[user_id]['reminders']:
        users_data[user_id]['reminders'].remove(time_text)
        users_data[user_id]['awaiting_delete'] = False
        
        # إلغاء المهمة المجدولة
        cancel_user_reminder(user_id, time_text)
        
        await update.message.reply_text(
            f"✅ تم حذف التذكير بنجاح!\n"
            f"🕐 الوقت المحذوف: {time_text}\n\n"
            f"📋 استخدم /my_times لعرض الأوقات المتبقية",
            reply_markup=get_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ الوقت المدخل غير موجود!\n\n"
            "📋 استخدم /my_times لعرض أوقاتك الصحيحة",
            reply_markup=get_keyboard()
        )

async def stop_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إيقاف جميع التذكيرات"""
    user_id = update.effective_user.id
    
    if user_id in users_data:
        users_data[user_id]['is_active'] = False
        
        # إلغاء جميع المهام المجدولة للمستخدم
        if user_id in scheduled_jobs:
            for job in scheduled_jobs[user_id]:
                schedule.cancel_job(job)
            del scheduled_jobs[user_id]
        
        await update.message.reply_text(
            "⏹️ تم إيقاف جميع التذكيرات\n\n"
            "🔹 أوقاتك محفوظة ويمكنك إعادة تشغيلها\n"
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
        
        # إعادة جدولة جميع التذكيرات
        for reminder_time in users_data[user_id]['reminders']:
            schedule_user_reminder(user_id, reminder_time)
        
        count = len(users_data[user_id]['reminders'])
        await update.message.reply_text(
            f"▶️ تم تشغيل التذكيرات بنجاح!\n\n"
            f"🔢 عدد التذكيرات: {count}\n"
            f"📋 استخدم /my_times لعرض أوقاتك",
            reply_markup=get_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ استخدم /start أولاً",
            reply_markup=get_keyboard()
        )

def schedule_user_reminder(user_id: int, reminder_time: str):
    """جدولة تذكير للمستخدم"""
    def send_reminder():
        """إرسال التذكير"""
        try:
            # اختيار رسالة عشوائية
            message = random.choice(prayer_messages)
            
            # إرسال الرسالة (سيتم تنفيذها بواسطة الـ job scheduler)
            application.create_task(send_reminder_message(user_id, message))
            
        except Exception as e:
            logger.error(f"خطأ في إرسال التذكير للمستخدم {user_id}: {e}")
    
    # إنشاء المهمة المجدولة
    job = schedule.every().day.at(reminder_time).do(send_reminder)
    
    # حفظ المهمة
    if user_id not in scheduled_jobs:
        scheduled_jobs[user_id] = []
    scheduled_jobs[user_id].append(job)

def cancel_user_reminder(user_id: int, reminder_time: str):
    """إلغاء تذكير معين"""
    if user_id in scheduled_jobs:
        # البحث عن المهمة وإلغاؤها
        for job in scheduled_jobs[user_id][:]:
            if hasattr(job, 'at_time') and str(job.at_time) == reminder_time:
                schedule.cancel_job(job)
                scheduled_jobs[user_id].remove(job)
                break

async def send_reminder_message(user_id: int, message: str):
    """إرسال رسالة التذكير"""
    try:
        await application.bot.send_message(
            chat_id=user_id,
            text=f"{message}\n\n💫 تذكير من بوت الصلاة على النبي ﷺ"
        )
    except Exception as e:
        logger.error(f"فشل إرسال التذكير للمستخدم {user_id}: {e}")

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # التحقق من حالة المستخدم
    if user_id in users_data:
        user_data = users_data[user_id]
        
        # إذا كان ينتظر إدخال وقت
        if user_data.get('awaiting_time'):
            await handle_time_input(update, context)
            return
        
        # إذا كان ينتظر حذف وقت
        if user_data.get('awaiting_delete'):
            await handle_delete_time(update, context)
            return
    
    # معالجة الأزرار
    if text == "⏰ إضافة وقت تذكير":
        await add_time_start(update, context)
    elif text == "📋 أوقاتي":
        await my_times(update, context)
    elif text == "🗑️ حذف وقت":
        await delete_time_start(update, context)
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

def run_schedule():
    """تشغيل المهام المجدولة"""
    while True:
        schedule.run_pending()
        time.sleep(1)

def main():
    """الدالة الرئيسية"""
    global application
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add_time", add_time_start))
    application.add_handler(CommandHandler("my_times", my_times))
    application.add_handler(CommandHandler("delete_time", delete_time_start))
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
