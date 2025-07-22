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
            'is_active': True,  # مفعل تلقائياً
            'created_at': datetime.now().isoformat(),
            'last_reminder': None
        }
        # بدء التذكيرات للمستخدم الجديد تلقائياً
        start_user_reminders(user_id)
        logger.info(f"مستخدم جديد {user_id} - تم بدء التذكيرات تلقائياً")
    else:
        # للمستخدمين الموجودين، تحقق من حالة التفعيل
        if users_data[user_id]['is_active'] and user_id not in scheduled_jobs:
            start_user_reminders(user_id)
            logger.info(f"إعادة تفعيل التذكيرات للمستخدم {user_id}")
    
    welcome_message = f"""
🌟 أهلاً وسهلاً {username}!

🤲 هذا بوت تذكير الصلاة على النبي محمد ﷺ

📱 الميزات المتاحة:
• تذكير كل {DEFAULT_INTERVAL} دقائق (مفعل تلقائياً ✅)
• يمكن تغيير الفترة من 1 دقيقة إلى 60 دقيقة
• رسائل تذكير متنوعة
• تحكم كامل في التذكيرات

🎯 استخدم الأزرار بالأسفل أو الأوامر:
/set_interval - تغيير فترة التذكير
/my_settings - عرض إعداداتي
/help - المساعدة

✨ التذكيرات تعمل الآن! ستصلك رسالة خلال {DEFAULT_INTERVAL} دقائق

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
            "💡 جرب مرة أخرى:")
async def process_message_queue():
    """معالجة رسائل التذكير من الـ queue"""
    processed = 0
    max_batch = 5  # معالجة 5 رسائل كحد أقصى في كل دورة
    
    while message_queue and processed < max_batch:
        try:
            msg_data = message_queue.pop(0)
            
            # تحقق من عمر الرسالة (لا ترسل رسائل قديمة جداً)
            if 'timestamp' in msg_data:
                msg_time = datetime.fromisoformat(msg_data['timestamp'])
                age_minutes = (datetime.now() - msg_time).total_seconds() / 60
                if age_minutes > 10:  # تجاهل الرسائل الأقدم من 10 دقائق
                    logger.warning(f"تجاهل رسالة قديمة للمستخدم {msg_data['user_id']}")
                    continue
            
            await application.bot.send_message(
                chat_id=msg_data['user_id'],
                text=msg_data['message'],
                read_timeout=8,
                write_timeout=8,
                connect_timeout=8
            )
            
            processed += 1
            logger.info(f"تم إرسال تذكير للمستخدم {msg_data['user_id']}")
            
            # انتظار قصير بين الرسائل لتجنب rate limiting
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"فشل إرسال الرسالة: {e}")
            
            # إعادة الرسالة للـ queue إذا كان خطأ مؤقت
            if any(keyword in str(e).lower() for keyword in ["timeout", "pool", "network"]):
                # إعادة في النهاية وليس البداية لتجنب الحلقة المفرغة
                message_queue.append(msg_data)
                logger.info("تم إعادة الرسالة للـ queue للمحاولة لاحقاً")
            
            break  # توقف لهذه الدورة

def run_schedule():
    """تشغيل المهام المجدولة"""
    retry_count = 0
    max_retries = 3
    last_schedule_run = time.time()
    
    logger.info("بدء تشغيل المجدول...")
    
    while True:
        try:
            current_time = time.time()
            
            # تشغيل المهام المجدولة كل ثانية
            schedule.run_pending()
            
            # معالجة الرسائل كل 2 ثانية أو عند وجود رسائل عاجلة
            if message_queue and (current_time - last_schedule_run >= 2 or len(message_queue) > 0):
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(process_message_queue())
                    loop.close()
                    
                    retry_count = 0  # إعادة تعيين العداد عند النجاح
                    last_schedule_run = current_time
                    
                except Exception as e:
                    logger.error(f"خطأ في معالجة الرسائل: {e}")
                    retry_count += 1
                    
                    if retry_count >= max_retries:
                        logger.error(f"تم الوصول للحد الأقصى من المحاولات ({max_retries})")
                        retry_count = 0
                        
                        # تنظيف الـ queue إذا امتلأ (أكثر من 20 رسالة)
                        if len(message_queue) > 20:
                            # احتفظ بأحدث 5 رسائل فقط
                            message_queue[:] = message_queue[-5:]
                            logger.warning("تم تنظيف queue الرسائل - احتفظنا بأحدث 5 رسائل")
                    
                    time.sleep(2)  # انتظار أطول عند وجود خطأ
                    continue
            
            # تنظيف دوري للرسائل القديمة كل 5 دقائق
            if int(current_time) % 300 == 0:  # كل 5 دقائق
                cleanup_old_messages()
                    
        except Exception as e:
            logger.error(f"خطأ عام في run_schedule: {e}")
            time.sleep(3)
            
        # تردد أعلى لمعالجة أسرع
        time.sleep(0.5)  # نصف ثانية بدلاً من ثانية كاملة

def cleanup_old_messages():
    """تنظيف الرسائل القديمة من الـ queue"""
    if not message_queue:
        return
        
    current_time = datetime.now()
    cleaned_queue = []
    
    for msg in message_queue:
        if 'timestamp' in msg:
            try:
                msg_time = datetime.fromisoformat(msg['timestamp'])
                age_minutes = (current_time - msg_time).total_seconds() / 60
                if age_minutes <= 15:  # احتفظ بالرسائل الأحدث من 15 دقيقة
                    cleaned_queue.append(msg)
            except:
                # إذا فشل parsing التوقيت، احتفظ بالرسالة
                cleaned_queue.append(msg)
        else:
            # رسائل بدون timestamp، احتفظ بها
            cleaned_queue.append(msg)
    
    removed_count = len(message_queue) - len(cleaned_queue)
    if removed_count > 0:
        message_queue[:] = cleaned_queue
        logger.info(f"تم حذف {removed_count} رسالة قديمة من الـ queue")

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
        logger.warning(f"محاولة بدء تذكيرات لمستخدم غير موجود: {user_id}")
        return
    
    # إيقاف أي تذكيرات سابقة أولاً
    if user_id in scheduled_jobs:
        schedule.cancel_job(scheduled_jobs[user_id])
        del scheduled_jobs[user_id]
        logger.info(f"تم إلغاء التذكيرات السابقة للمستخدم {user_id}")
    
    interval = users_data[user_id]['interval']
    
    def send_reminder():
        """إرسال التذكير"""
        try:
            # التأكد من أن المستخدم ما زال مفعل
            if user_id not in users_data or not users_data[user_id]['is_active']:
                logger.info(f"تجاهل تذكير للمستخدم {user_id} - غير مفعل")
                return
                
            # تحديث وقت آخر تذكير
            users_data[user_id]['last_reminder'] = datetime.now().isoformat()
            
            # اختيار رسالة عشوائية
            message = random.choice(prayer_messages)
            
            # إضافة الرسالة للـ queue بأولوية عالية
            message_queue.insert(0, {  # إدراج في البداية للأولوية
                'user_id': user_id,
                'message': f"{message}\n\n💫 تذكير من بوت الصلاة على النبي ﷺ",
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"تم جدولة تذكير للمستخدم {user_id}")
            
        except Exception as e:
            logger.error(f"خطأ في إرسال التذكير للمستخدم {user_id}: {e}")
    
    # إنشاء المهمة المجدولة - بدء فوري ثم كل interval
    job = schedule.every(interval).minutes.do(send_reminder)
    
    # إرسال أول تذكير بعد دقيقة واحدة (للاختبار السريع)
    first_reminder_job = schedule.every(1).minutes.do(send_reminder)
    
    # حفظ المهمة
    scheduled_jobs[user_id] = job
    
    # إلغاء المهمة الأولى بعد تنفيذها
    def cancel_first_reminder():
        try:
            schedule.cancel_job(first_reminder_job)
        except:
            pass
    
    # جدولة إلغاء المهمة الأولى بعد دقيقتين
    schedule.every(2).minutes.do(cancel_first_reminder).tag(f'cleanup_{user_id}')
    
    logger.info(f"تم بدء تذكيرات للمستخدم {user_id} كل {interval} دقيقة (أول تذكير خلال دقيقة)")

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
    
    # إنشاء التطبيق مع إعدادات timeout محسنة
    application = Application.builder().token(BOT_TOKEN).read_timeout(15).write_timeout(15).connect_timeout(15).build()
    
    # إضافة معالج الأخطاء العام
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """معالج الأخطاء العام"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # إذا كان timeout، نحاول مرة أخرى
        if "timeout" in str(context.error).lower():
            logger.info("محاولة إعادة الاتصال...")
            await asyncio.sleep(2)
    
    application.add_error_handler(error_handler)
    
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
