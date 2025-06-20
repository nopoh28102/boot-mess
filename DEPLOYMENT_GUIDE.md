# دليل النشر - Facebook Messenger Bot

## المشروع النهائي جاهز للنشر

تم تنظيف المشروع بالكامل وإنشاء تطبيق متكامل مع جميع الصفحات والوظائف.

## الملفات النهائية:

### الملفات الأساسية
- `app.py` - التطبيق الرئيسي المتكامل
- `wsgi.py` - ملف WSGI للنشر
- `requirements_clean.txt` - المكتبات المطلوبة
- `.env` - متغيرات البيئة

### القوالب (templates/)
- `base.html` - القالب الأساسي
- `index.html` - الصفحة الرئيسية
- `admin_login.html` - صفحة تسجيل دخول الإدارة
- `admin_dashboard.html` - لوحة تحكم الإدارة
- `admin_responses.html` - إدارة الردود المخصصة
- `add_response.html` - إضافة رد جديد
- `admin_analytics.html` - صفحة التحليلات

### قاعدة البيانات
- `facebook_bot.db` - قاعدة بيانات SQLite مع البيانات الأساسية

## خطوات النشر على PythonAnywhere:

### 1. تحضير الملفات
```bash
# ارفع هذه الملفات:
- app.py
- wsgi.py
- requirements_clean.txt
- .env
- templates/ (المجلد كاملاً)
- facebook_bot.db
```

### 2. تثبيت المكتبات
```bash
pip3.10 install --user -r requirements_clean.txt
```

### 3. إعداد Web App
في لوحة تحكم PythonAnywhere:
1. اذهب إلى Web
2. أنشئ web app جديد
3. اختر "Manual configuration"
4. اختر Python 3.10

### 4. إعداد WSGI
في ملف WSGI configuration، ضع:
```python
import sys
import os

# استبدل yourusername باسم المستخدم الخاص بك
project_home = '/home/yourusername/mysite'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# تحميل متغيرات البيئة
def load_environment():
    env_file = os.path.join(project_home, '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value.strip('"\'')

load_environment()
from app import app as application
```

### 5. تحديث ملف .env
```bash
# Facebook Configuration
PAGE_ACCESS_TOKEN=رمز_الصفحة_الحقيقي_من_فيسبوك
VERIFY_TOKEN=رمز_التحقق_الذي_اخترته
APP_SECRET=سر_التطبيق_من_فيسبوك

# OpenAI Configuration (اختياري)
OPENAI_API_KEY=مفتاح_OpenAI_إذا_أردت

# Security
SESSION_SECRET=مفتاح_سري_قوي_للجلسات

# Database
DATABASE_URL=sqlite:///facebook_bot.db

# Admin
ADMIN_PASSWORD=admin123

# Server Configuration
FLASK_ENV=production
DEBUG=False
```

### 6. إعداد Facebook Webhook
1. في Facebook Developers Console
2. اذهب إلى Messenger -> Settings
3. أضف Webhook URL: `https://yourusername.pythonanywhere.com/webhook`
4. أضف Verify Token (نفس القيمة في .env)
5. اختر Events: messages, messaging_postbacks

## الصفحات المتاحة:

### الصفحات العامة:
- `/` - الصفحة الرئيسية مع الإحصائيات
- `/health` - فحص حالة النظام
- `/webhook` - نقطة نهاية Facebook
- `/api/stats` - API للإحصائيات

### صفحات الإدارة:
- `/admin/login` - تسجيل دخول الإدارة
- `/admin/dashboard` - لوحة التحكم الرئيسية
- `/admin/responses` - إدارة الردود المخصصة
- `/admin/responses/add` - إضافة رد جديد
- `/admin/analytics` - تحليلات مفصلة
- `/admin/logout` - تسجيل الخروج

## بيانات الدخول الافتراضية:
- **اسم المستخدم:** admin
- **كلمة المرور:** admin123

## الميزات المتاحة:

### الوظائف الأساسية:
✅ استقبال ومعالجة رسائل الماسنجر
✅ ردود تلقائية ذكية باللغة العربية والإنجليزية
✅ نظام ردود مخصصة قابل للإدارة
✅ حفظ وتتبع جميع المحادثات
✅ واجهة إدارة كاملة وسهلة الاستخدام

### الأمان والحماية:
✅ التحقق من Facebook webhook signatures
✅ نظام تسجيل دخول آمن للإدارة
✅ حماية جلسات المستخدمين
✅ تشفير البيانات الحساسة

### التحليلات والإحصائيات:
✅ إحصائيات شاملة للمحادثات
✅ تتبع الردود الأكثر استخداماً
✅ تحليلات يومية ومرحلية
✅ تقارير مفصلة قابلة للطباعة

### واجهة المستخدم:
✅ تصميم عصري ومتجاوب
✅ دعم كامل للغة العربية
✅ سهولة في الاستخدام والتنقل
✅ رسائل تنبيه واضحة

## الاختبار:
للتأكد من عمل التطبيق، زر هذه الروابط بعد النشر:
- `https://yourusername.pythonanywhere.com/` - الصفحة الرئيسية
- `https://yourusername.pythonanywhere.com/health` - فحص الحالة
- `https://yourusername.pythonanywhere.com/admin/login` - لوحة الإدارة

## الدعم:
- جميع الملفات محسنة ومختبرة
- دليل مفصل لكل خطوة
- بيانات افتراضية للاختبار
- نظام أخطاء واضح ومفيد

المشروع جاهز بنسبة 100% للنشر والاستخدام الفوري!