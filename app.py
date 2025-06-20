#!/usr/bin/env python3
"""
Facebook Messenger Bot - Complete Integrated Version
All features in one file with all pages connected
"""

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, send_from_directory
import os
import json
import sqlite3
import requests
import logging
import hashlib
import hmac
import asyncio
import aiohttp
from datetime import datetime, timedelta
from functools import wraps
import random
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
import uuid
from ai_engine_enhanced import EnhancedAIEngine

# Flask app initialization
app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'your-secret-key-here')

# File upload configuration
UPLOAD_FOLDER = 'static/uploads'
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {
    'image': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
    'video': {'mp4', 'avi', 'mov', 'mkv', 'webm'},
    'audio': {'mp3', 'wav', 'ogg', 'aac', 'm4a'},
    'file': {'pdf', 'doc', 'docx', 'txt', 'zip', 'rar'}
}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directories exist
os.makedirs(os.path.join(UPLOAD_FOLDER, 'images'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'videos'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'audio'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'files'), exist_ok=True)

# Database setup
DATABASE_PATH = 'facebook_bot.db'

def allowed_file(filename, file_type):
    """Check if file extension is allowed for the given type"""
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS.get(file_type, set())

def get_file_type_from_extension(filename):
    """Determine file type from extension"""
    if '.' not in filename:
        return 'file'
    extension = filename.rsplit('.', 1)[1].lower()
    
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if extension in extensions:
            return file_type
    return 'file'

def save_uploaded_file(file, file_type):
    """Save uploaded file and return the file path"""
    if not file or not file.filename:
        return None
    
    if not allowed_file(file.filename, file_type):
        return None
    
    # Generate unique filename
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
    
    # Determine subfolder based on file type
    subfolder = f"{file_type}s" if file_type != 'file' else 'files'
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, unique_filename)
    
    try:
        file.save(file_path)
        # Return relative path for URL generation
        return f"uploads/{subfolder}/{unique_filename}"
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        return None

def init_database():
    """Initialize database with all required tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            provider TEXT DEFAULT 'ai',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Custom responses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_type TEXT NOT NULL,
            trigger_value TEXT NOT NULL,
            response_text TEXT NOT NULL,
            confidence REAL DEFAULT 1.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            used_count INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Analytics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            interaction_type TEXT NOT NULL,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Admin users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bot settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default responses
    default_responses = [
        ('text', 'مرحبا', 'مرحباً بك! كيف يمكنني مساعدتك اليوم؟'),
        ('text', 'هلا', 'هلا وغلا! أهلاً وسهلاً بك'),
        ('text', 'السلام عليكم', 'وعليكم السلام ورحمة الله وبركاته، أهلاً وسهلاً'),
        ('text', 'شكرا', 'العفو! سعيد لمساعدتك. هل تحتاج لأي شيء آخر؟'),
        ('text', 'شكراً', 'العفو! سعيد لمساعدتك. هل تحتاج لأي شيء آخر؟'),
        ('text', 'وداعا', 'وداعاً! أتمنى لك يوماً سعيداً'),
        ('text', 'bye', 'Goodbye! Have a great day!'),
        ('pattern', 'help', 'يمكنني مساعدتك في:\n- الإجابة على أسئلتك\n- تقديم المعلومات\n- المحادثة العامة\n\nكيف يمكنني مساعدتك؟'),
        ('pattern', 'مساعدة', 'يمكنني مساعدتك في:\n- الإجابة على أسئلتك\n- تقديم المعلومات\n- المحادثة العامة\n\nكيف يمكنني مساعدتك؟')
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO custom_responses (trigger_type, trigger_value, response_text)
        VALUES (?, ?, ?)
    ''', default_responses)
    
    # Insert default admin user
    cursor.execute('''
        INSERT OR IGNORE INTO admin_users (username, password_hash)
        VALUES (?, ?)
    ''', ('admin', 'admin123'))  # Simple password for demo
    
    # Insert default bot settings
    default_settings = [
        ('bot_name', 'Facebook Messenger Bot'),
        ('welcome_message', 'مرحباً بك! أنا بوت ذكي يمكنني مساعدتك'),
        ('default_language', 'ar'),
        ('max_message_length', '500'),
        ('enable_analytics', '1')
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO bot_settings (setting_key, setting_value)
        VALUES (?, ?)
    ''', default_settings)
    
    conn.commit()
    conn.close()

# Initialize database
init_database()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize Enhanced AI Engine
ai_engine = EnhancedAIEngine()

class DatabaseManager:
    """Database operations manager"""
    
    @staticmethod
    def get_connection():
        return sqlite3.connect(DATABASE_PATH)
    
    @staticmethod
    def get_custom_response(message_text):
        """Get custom response for message"""
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        
        # Direct match
        cursor.execute('''
            SELECT response_text FROM custom_responses 
            WHERE trigger_type = 'text' AND LOWER(trigger_value) = LOWER(?)
            ORDER BY confidence DESC LIMIT 1
        ''', (message_text.strip(),))
        
        result = cursor.fetchone()
        if result:
            cursor.execute('''
                UPDATE custom_responses 
                SET used_count = used_count + 1 
                WHERE trigger_type = 'text' AND LOWER(trigger_value) = LOWER(?)
            ''', (message_text.strip(),))
            conn.commit()
            conn.close()
            return result[0]
        
        # Pattern match
        cursor.execute('''
            SELECT response_text FROM custom_responses 
            WHERE trigger_type = 'pattern' AND LOWER(?) LIKE '%' || LOWER(trigger_value) || '%'
            ORDER BY confidence DESC LIMIT 1
        ''', (message_text,))
        
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    @staticmethod
    def save_conversation(user_id, message, response, provider='ai'):
        """Save conversation"""
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO conversations (user_id, message, response, provider)
            VALUES (?, ?, ?, ?)
        ''', (user_id, message, response, provider))
        conn.commit()
        conn.close()
    
    @staticmethod
    def log_analytics(user_id, interaction_type, content):
        """Log analytics"""
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO analytics (user_id, interaction_type, content)
            VALUES (?, ?, ?)
        ''', (user_id, interaction_type, content))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_stats():
        """Get bot statistics"""
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        
        # Total conversations
        cursor.execute('SELECT COUNT(*) FROM conversations')
        total_conversations = cursor.fetchone()[0]
        
        # Unique users
        cursor.execute('SELECT COUNT(DISTINCT user_id) FROM conversations')
        unique_users = cursor.fetchone()[0]
        
        # Today's conversations
        cursor.execute('''
            SELECT COUNT(*) FROM conversations 
            WHERE DATE(timestamp) = DATE('now')
        ''')
        today_conversations = cursor.fetchone()[0]
        
        # Popular responses
        cursor.execute('''
            SELECT trigger_value, used_count FROM custom_responses 
            WHERE used_count > 0 
            ORDER BY used_count DESC LIMIT 5
        ''')
        popular_responses = cursor.fetchall()
        
        # Recent conversations
        cursor.execute('''
            SELECT user_id, message, response, timestamp 
            FROM conversations 
            ORDER BY timestamp DESC LIMIT 10
        ''')
        recent_conversations = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_conversations': total_conversations,
            'unique_users': unique_users,
            'today_conversations': today_conversations,
            'popular_responses': popular_responses,
            'recent_conversations': recent_conversations
        }
    
    @staticmethod
    def add_custom_response(trigger_type, trigger_value, response_text):
        """Add new custom response"""
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO custom_responses (trigger_type, trigger_value, response_text)
            VALUES (?, ?, ?)
        ''', (trigger_type, trigger_value, response_text))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_all_responses():
        """Get all custom responses"""
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, trigger_type, trigger_value, response_text, used_count, 1 as active
            FROM custom_responses ORDER BY created_at DESC
        ''')
        responses = cursor.fetchall()
        conn.close()
        return responses
    
    @staticmethod
    def delete_response(response_id):
        """Delete custom response"""
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM custom_responses WHERE id = ?', (response_id,))
        conn.commit()
        conn.close()

# Enhanced multimedia message sending functions
def send_multimedia_message(recipient_id, message_data):
    """Send multimedia message via Facebook Graph API"""
    if not PAGE_ACCESS_TOKEN:
        logger.error("PAGE_ACCESS_TOKEN not found")
        return False
    
    url = f"https://graph.facebook.com/v17.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    
    data = {
        "recipient": {"id": recipient_id},
        "message": message_data
    }
    
    try:
        response = requests.post(url, json=data, params=params)
        if response.status_code == 200:
            logger.info(f"Multimedia message sent successfully to {recipient_id}")
            return True
        else:
            logger.error(f"Failed to send multimedia message: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending multimedia message: {str(e)}")
        return False

async def handle_message_with_ai(sender_id, message_text):
    """Handle message using enhanced AI engine"""
    try:
        # Get AI response using enhanced engine
        ai_response = await ai_engine.generate_ai_response(sender_id, message_text)
        
        if ai_response and ai_response.get('text'):
            response_text = ai_response['text']
            
            # Check if we should use a template for certain keywords
            if any(word in message_text.lower() for word in ['مرحبا', 'hello', 'start']):
                template = ai_engine.get_message_template('welcome_buttons')
                if template:
                    template_message = ai_engine.create_multimedia_response('button_template', template['data'])
                    if send_multimedia_message(sender_id, template_message):
                        DatabaseManager.save_conversation(sender_id, message_text, "قالب ترحيب مع أزرار", ai_response.get('source', 'ai'))
                        DatabaseManager.log_analytics(sender_id, 'template_response', message_text)
                        return
            
            elif any(word in message_text.lower() for word in ['منتجات', 'products']):
                template = ai_engine.get_message_template('product_cards')
                if template:
                    template_message = ai_engine.create_multimedia_response('generic_template', template['data'])
                    if send_multimedia_message(sender_id, template_message):
                        DatabaseManager.save_conversation(sender_id, message_text, "بطاقات المنتجات", ai_response.get('source', 'ai'))
                        DatabaseManager.log_analytics(sender_id, 'template_response', message_text)
                        return
            
            # Send regular text response
            if send_message(sender_id, response_text):
                DatabaseManager.save_conversation(sender_id, message_text, response_text, ai_response.get('source', 'ai'))
                DatabaseManager.log_analytics(sender_id, 'ai_response', message_text)
        
    except Exception as e:
        logger.error(f"Error in AI message handling: {str(e)}")
        # Fallback to basic response
        fallback_response = "عذراً، أواجه صعوبة في معالجة رسالتك. الرجاء المحاولة مرة أخرى."
        send_message(sender_id, fallback_response)

def admin_required(f):
    """Admin authentication decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def send_message(recipient_id, message_text):
    """Send message via Facebook Graph API"""
    if not PAGE_ACCESS_TOKEN:
        logger.error("PAGE_ACCESS_TOKEN not found")
        return False
    
    url = f"https://graph.facebook.com/v17.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    try:
        response = requests.post(url, json=data, params=params)
        if response.status_code == 200:
            logger.info(f"Message sent successfully to {recipient_id}")
            return True
        else:
            logger.error(f"Failed to send message: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return False

# Routes
@app.route('/')
def home():
    """Homepage"""
    stats = DatabaseManager.get_stats()
    return render_template('index.html', stats=stats)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0',
        'database': 'connected' if os.path.exists(DATABASE_PATH) else 'disconnected'
    })

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verify webhook"""
    verify_token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if verify_token == VERIFY_TOKEN and challenge:
        return str(challenge)
    
    return "Verification failed", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming messages"""
    try:
        data = request.get_json()
        
        if data['object'] == 'page':
            for entry in data['entry']:
                for messaging_event in entry.get('messaging', []):
                    sender_id = messaging_event['sender']['id']
                    
                    if 'message' in messaging_event:
                        message = messaging_event['message']
                        if 'text' in message:
                            handle_text_message(sender_id, message['text'])
                    
                    elif 'postback' in messaging_event:
                        handle_postback(sender_id, messaging_event['postback'])
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return 'Error', 500

def handle_text_message(sender_id, message_text):
    """Handle text messages with enhanced AI"""
    try:
        # Use async AI handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(handle_message_with_ai(sender_id, message_text))
        loop.close()
        
    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")
        send_message(sender_id, "عذراً، حدث خطأ. الرجاء المحاولة مرة أخرى.")

def handle_postback(sender_id, postback):
    """Handle postback buttons"""
    payload = postback.get('payload')
    
    if payload == 'GET_STARTED':
        send_message(sender_id, "مرحباً بك! أنا بوت ذكي يمكنني مساعدتك في الإجابة على أسئلتك. كيف يمكنني مساعدتك اليوم؟")
    else:
        send_message(sender_id, "شكراً لاختيارك!")

# Admin routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Simple authentication (in production, use proper hashing)
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('home'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    stats = DatabaseManager.get_stats()
    return render_template('admin_dashboard.html', stats=stats)

@app.route('/admin/responses')
@admin_required
def admin_responses():
    """Manage custom responses"""
    responses = DatabaseManager.get_all_responses()
    return render_template('admin_responses.html', responses=responses)

@app.route('/admin/responses/add', methods=['GET', 'POST'])
@admin_required
def add_response():
    """Add new response"""
    if request.method == 'POST':
        trigger_type = request.form.get('trigger_type')
        trigger_value = request.form.get('trigger_value')
        response_text = request.form.get('response_text')
        
        if trigger_value and response_text:
            DatabaseManager.add_custom_response(trigger_type, trigger_value, response_text)
            flash('تم إضافة الرد بنجاح', 'success')
            return redirect(url_for('admin_responses'))
        else:
            flash('الرجاء ملء جميع الحقول', 'error')
    
    return render_template('add_response.html')

@app.route('/admin/responses/delete/<int:response_id>')
@admin_required
def delete_response(response_id):
    """Delete response"""
    DatabaseManager.delete_response(response_id)
    flash('تم حذف الرد بنجاح', 'success')
    return redirect(url_for('admin_responses'))

@app.route('/admin/responses/test/<int:response_id>', methods=['POST'])
@admin_required
def test_response_endpoint(response_id):
    """Test a specific response"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT trigger_value, response_text FROM custom_responses WHERE id = ?', (response_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            trigger, response = result
            return jsonify({
                'success': True,
                'trigger': trigger,
                'response': response,
                'message': 'تم اختبار الرد بنجاح'
            })
        else:
            return jsonify({'success': False, 'error': 'الرد غير موجود'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/responses/toggle/<int:response_id>', methods=['POST'])
@admin_required
def toggle_response(response_id):
    """Toggle response active status"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE custom_responses SET active = 1 - active WHERE id = ?', (response_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'تم تغيير حالة الرد'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/responses/export')
@admin_required
def export_responses():
    """Export responses to JSON"""
    try:
        responses = DatabaseManager.get_all_responses()
        export_data = []
        for response in responses:
            export_data.append({
                'trigger_type': response[1],
                'trigger_value': response[2],
                'response_text': response[3],
                'confidence': response[4],
                'used_count': response[5],
                'active': response[6] if len(response) > 6 else 1
            })
        
        from flask import Response
        import json
        return Response(
            json.dumps(export_data, ensure_ascii=False, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=bot_responses.json'}
        )
    except Exception as e:
        flash(f'خطأ في التصدير: {str(e)}', 'error')
        return redirect(url_for('admin_responses'))

@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    """Analytics page"""
    stats = DatabaseManager.get_stats()
    return render_template('admin_analytics.html', stats=stats)

@app.route('/admin/templates')
@admin_required
def admin_templates():
    """Manage message templates"""
    templates = get_all_templates()
    return render_template('admin_templates.html', templates=templates)

@app.route('/admin/templates/create', methods=['GET', 'POST'])
@admin_required
def create_template():
    """Create new message template"""
    if request.method == 'POST':
        template_name = request.form.get('template_name')
        template_type = request.form.get('template_type')
        template_data = request.form.get('template_data')
        description = request.form.get('description')
        
        if template_name and template_type and template_data:
            # Validate JSON data
            try:
                json.loads(template_data)
                save_template(template_name, template_type, template_data, description)
                flash('تم إنشاء القالب بنجاح', 'success')
                return redirect(url_for('admin_templates'))
            except json.JSONDecodeError:
                flash('خطأ في تنسيق JSON', 'error')
        else:
            flash('الرجاء ملء جميع الحقول المطلوبة', 'error')
    
    return render_template('create_template.html')

@app.route('/admin/templates/edit/<int:template_id>', methods=['GET', 'POST'])
@admin_required
def edit_template(template_id):
    """Edit message template"""
    if request.method == 'POST':
        template_data = request.form.get('template_data')
        description = request.form.get('description')
        
        if template_data:
            try:
                json.loads(template_data)
                update_template(template_id, template_data, description)
                flash('تم تحديث القالب بنجاح', 'success')
                return redirect(url_for('admin_templates'))
            except json.JSONDecodeError:
                flash('خطأ في تنسيق JSON', 'error')
    
    template = get_template_by_id(template_id)
    return render_template('edit_template.html', template=template)

@app.route('/admin/templates/delete/<int:template_id>')
@admin_required
def delete_template(template_id):
    """Delete message template"""
    delete_template_by_id(template_id)
    flash('تم حذف القالب بنجاح', 'success')
    return redirect(url_for('admin_templates'))

@app.route('/admin/templates/test/<template_name>', methods=['POST'])
@admin_required
def test_template(template_name):
    """Test message template"""
    try:
        template = ai_engine.get_message_template(template_name)
        if template:
            return jsonify({
                'success': True,
                'template': template,
                'message': 'تم اختبار القالب بنجاح'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'القالب غير موجود'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/admin/templates/preview/<int:template_id>')
@admin_required
def preview_template(template_id):
    """Preview template"""
    try:
        template = get_template_by_id(template_id)
        if template:
            return jsonify({
                'success': True,
                'template': {
                    'name': template[1],
                    'type': template[2],
                    'data': json.loads(template[3]) if template[3] else {},
                    'description': template[4] or ''
                }
            })
        else:
            return jsonify({'success': False, 'error': 'القالب غير موجود'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/templates/duplicate/<int:template_id>', methods=['POST'])
@admin_required
def duplicate_template(template_id):
    """Duplicate template"""
    try:
        template = get_template_by_id(template_id)
        if template:
            new_name = f"{template[1]}_copy"
            save_template(new_name, template[2], template[3], f"نسخة من {template[4] or template[1]}")
            return jsonify({'success': True, 'message': 'تم نسخ القالب بنجاح'})
        else:
            return jsonify({'success': False, 'error': 'القالب غير موجود'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/openai/status')
def openai_status():
    """Check OpenAI API status"""
    try:
        import openai
        if not OPENAI_API_KEY:
            return jsonify({'success': False, 'error': 'مفتاح API غير موجود'})
        
        # Simple test request
        openai.api_key = OPENAI_API_KEY
        response = openai.Model.list()
        return jsonify({'success': True, 'message': 'متصل بنجاح'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/media', methods=['GET', 'POST'])
@admin_required
def admin_media():
    """Manage multimedia responses"""
    if request.method == 'POST':
        trigger_text = request.form.get('trigger_text')
        response_type = request.form.get('response_type')
        description = request.form.get('description')
        
        # Check if file was uploaded or URL provided
        media_file = request.files.get('media_file')
        media_url = request.form.get('media_url')
        
        final_media_url = None
        media_type = None
        
        if media_file and media_file.filename:
            # Handle file upload
            file_path = save_uploaded_file(media_file, response_type)
            if file_path:
                final_media_url = f"/{file_path}"  # Local file path
                media_type = media_file.filename.rsplit('.', 1)[1].lower() if '.' in media_file.filename else 'unknown'
                flash('تم رفع الملف بنجاح', 'success')
            else:
                flash('خطأ في رفع الملف. تأكد من نوع وحجم الملف.', 'error')
                media_responses = get_all_media_responses()
                return render_template('admin_media.html', media_responses=media_responses)
        elif media_url:
            # Handle URL input
            final_media_url = media_url
            media_type = request.form.get('media_type', 'url')
        else:
            flash('يجب رفع ملف أو إدخال رابط', 'error')
            media_responses = get_all_media_responses()
            return render_template('admin_media.html', media_responses=media_responses)
        
        if trigger_text and final_media_url:
            save_media_response(trigger_text, response_type, final_media_url, media_type, description)
            flash('تم حفظ الرد المتعدد الوسائط بنجاح', 'success')
            return redirect(url_for('admin_media'))
    
    media_responses = get_all_media_responses()
    return render_template('admin_media.html', media_responses=media_responses)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/admin/media/upload', methods=['POST'])
@admin_required
def upload_media_ajax():
    """Handle AJAX file upload"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'لم يتم اختيار ملف'})
        
        file = request.files['file']
        file_type = request.form.get('type', 'file')
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'لم يتم اختيار ملف'})
        
        file_path = save_uploaded_file(file, file_type)
        if file_path:
            return jsonify({
                'success': True,
                'file_path': f"/{file_path}",
                'file_name': file.filename,
                'file_size': file.content_length or 0,
                'message': 'تم رفع الملف بنجاح'
            })
        else:
            return jsonify({'success': False, 'error': 'خطأ في رفع الملف'})
    
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/media/manage')
@admin_required
def manage_uploaded_files():
    """Manage uploaded files"""
    try:
        uploaded_files = []
        upload_base = app.config['UPLOAD_FOLDER']
        
        for subfolder in ['images', 'videos', 'audio', 'files']:
            folder_path = os.path.join(upload_base, subfolder)
            if os.path.exists(folder_path):
                for filename in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, filename)
                    if os.path.isfile(file_path):
                        stat = os.stat(file_path)
                        uploaded_files.append({
                            'name': filename,
                            'path': f"uploads/{subfolder}/{filename}",
                            'type': subfolder[:-1],  # Remove 's' from folder name
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime)
                        })
        
        # Sort by modification date (newest first)
        uploaded_files.sort(key=lambda x: x['modified'], reverse=True)
        
        return render_template('manage_files.html', files=uploaded_files)
    
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        flash('خطأ في عرض الملفات', 'error')
        return redirect(url_for('admin_media'))

@app.route('/admin/media/delete-file', methods=['POST'])
@admin_required
def delete_uploaded_file():
    """Delete uploaded file"""
    try:
        data = request.get_json()
        file_path = data.get('file_path') if data else None
        if not file_path:
            return jsonify({'success': False, 'error': 'مسار الملف مطلوب'})
        
        # Security check - ensure file is in uploads directory
        if not file_path.startswith('uploads/'):
            return jsonify({'success': False, 'error': 'مسار غير صحيح'})
        
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], file_path.replace('uploads/', ''))
        
        if os.path.exists(full_path):
            os.remove(full_path)
            
            # Also remove from database if it's being used
            conn = DatabaseManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ai_responses WHERE media_url = ?', (f"/{file_path}",))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'تم حذف الملف بنجاح'})
        else:
            return jsonify({'success': False, 'error': 'الملف غير موجود'})
    
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/media/check-usage', methods=['POST'])
@admin_required
def check_file_usage():
    """Check if uploaded file is being used in responses"""
    try:
        data = request.get_json()
        file_path = data.get('file_path') if data else None
        
        if not file_path:
            return jsonify({'used': False, 'error': 'مسار الملف مطلوب'})
        
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM ai_responses WHERE media_url = ?', (file_path,))
        count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({'used': count > 0, 'usage_count': count})
        
    except Exception as e:
        logger.error(f"Error checking file usage: {e}")
        return jsonify({'used': False, 'error': str(e)})

@app.route('/admin/ai-settings', methods=['GET', 'POST'])
@admin_required
def ai_settings():
    """AI engine settings"""
    if request.method == 'POST':
        # Update AI settings
        settings = {
            'model_name': request.form.get('model_name', 'gpt-4o'),
            'max_tokens': int(request.form.get('max_tokens', 500)),
            'temperature': float(request.form.get('temperature', 0.7)),
            'enable_learning': request.form.get('enable_learning') == 'on',
            'fallback_mode': request.form.get('fallback_mode', 'intelligent')
        }
        
        save_ai_settings(settings)
        flash('تم تحديث إعدادات الذكاء الاصطناعي بنجاح', 'success')
        return redirect(url_for('ai_settings'))
    
    current_settings = get_ai_settings()
    return render_template('ai_settings.html', settings=current_settings)

@app.route('/api/stats')
def api_stats():
    """API endpoint for stats"""
    stats = DatabaseManager.get_stats()
    return jsonify(stats)

@app.route('/api/conversation/feedback', methods=['POST'])
def conversation_feedback():
    """Handle conversation feedback for learning"""
    try:
        data = request.get_json()
        conversation_id = data.get('conversation_id')
        feedback = data.get('feedback')
        score = int(data.get('score', 3))
        
        if conversation_id and feedback:
            ai_engine.learn_from_feedback(conversation_id, feedback, score)
            return jsonify({'success': True, 'message': 'تم حفظ التقييم بنجاح'})
        else:
            return jsonify({'success': False, 'error': 'بيانات ناقصة'})
            
    except Exception as e:
        logger.error(f"Error handling feedback: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/test', methods=['POST'])
def test_ai_engine():
    """Test AI engine with a message"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        test_mode = data.get('test_mode', False)
        
        if not message:
            return jsonify({'success': False, 'error': 'لا توجد رسالة للاختبار'})
        
        # Generate AI response
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ai_response = loop.run_until_complete(
            ai_engine.generate_ai_response('test_user_' + str(datetime.now().timestamp()), message)
        )
        loop.close()
        
        if ai_response:
            return jsonify({
                'success': True,
                'response': ai_response.get('text', 'لا يوجد رد'),
                'source': ai_response.get('source', 'unknown'),
                'confidence': ai_response.get('confidence', 0.0),
                'model': ai_response.get('model', 'default')
            })
        else:
            return jsonify({'success': False, 'error': 'فشل في توليد الرد'})
            
    except Exception as e:
        logger.error(f"Error testing AI: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/clear-learning', methods=['POST'])
@admin_required
def clear_learning_data():
    """Clear AI learning data"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        
        # Clear learning tables
        cursor.execute('DELETE FROM learning_feedback')
        cursor.execute('DELETE FROM ai_responses WHERE confidence_score < 1.0')
        cursor.execute('UPDATE ai_responses SET usage_count = 0, success_rate = 0.0')
        
        conn.commit()
        conn.close()
        
        # Reinitialize AI engine
        ai_engine._load_conversation_history()
        
        return jsonify({'success': True, 'message': 'تم مسح بيانات التعلم بنجاح'})
        
    except Exception as e:
        logger.error(f"Error clearing learning data: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/media/test/<int:media_id>', methods=['POST'])
@admin_required
def test_media_response(media_id):
    """Test multimedia response"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT trigger_text, response_type, media_url, media_type 
            FROM ai_responses WHERE id = ?
        ''', (media_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            trigger_text, response_type, media_url, media_type = result
            
            # Create multimedia response
            multimedia_response = ai_engine.create_multimedia_response(response_type, {
                'url': media_url,
                'type': media_type
            })
            
            return jsonify({
                'success': True,
                'response': multimedia_response,
                'trigger': trigger_text,
                'type': response_type
            })
        else:
            return jsonify({'success': False, 'error': 'الرد غير موجود'})
            
    except Exception as e:
        logger.error(f"Error testing media response: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/media/delete/<int:media_id>')
@admin_required
def delete_media_response(media_id):
    """Delete multimedia response"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ai_responses WHERE id = ?', (media_id,))
        conn.commit()
        conn.close()
        
        flash('تم حذف الرد المتعدد الوسائط بنجاح', 'success')
        return redirect(url_for('admin_media'))
        
    except Exception as e:
        logger.error(f"Error deleting media response: {e}")
        flash('خطأ في حذف الرد', 'error')
        return redirect(url_for('admin_media'))

@app.route('/admin/media/preview/<int:media_id>')
@admin_required
def preview_media_response(media_id):
    """Preview multimedia response"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT trigger_text, response_type, media_url, media_type, response_text
            FROM ai_responses WHERE id = ?
        ''', (media_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            trigger_text, response_type, media_url, media_type, description = result
            return jsonify({
                'success': True,
                'media': {
                    'trigger': trigger_text,
                    'type': response_type,
                    'url': media_url,
                    'file_type': media_type,
                    'description': description or ''
                }
            })
        else:
            return jsonify({'success': False, 'error': 'الرد غير موجود'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Helper functions for template management
def get_all_templates():
    """Get all message templates"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, template_name, template_type, template_data, description, usage_count, created_at
            FROM message_templates ORDER BY created_at DESC
        ''')
        templates = cursor.fetchall()
        conn.close()
        return templates
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return []

def save_template(name, template_type, template_data, description):
    """Save new template"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO message_templates (template_name, template_type, template_data, description)
            VALUES (?, ?, ?, ?)
        ''', (name, template_type, template_data, description))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving template: {e}")

def get_template_by_id(template_id):
    """Get template by ID"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, template_name, template_type, template_data, description
            FROM message_templates WHERE id = ?
        ''', (template_id,))
        template = cursor.fetchone()
        conn.close()
        return template
    except Exception as e:
        logger.error(f"Error getting template: {e}")
        return None

def update_template(template_id, template_data, description):
    """Update template"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE message_templates 
            SET template_data = ?, description = ?, updated_at = datetime('now')
            WHERE id = ?
        ''', (template_data, description, template_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating template: {e}")

def delete_template_by_id(template_id):
    """Delete template by ID"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM message_templates WHERE id = ?', (template_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error deleting template: {e}")

def save_media_response(trigger_text, response_type, media_url, media_type, description):
    """Save multimedia response"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ai_responses (trigger_text, response_type, media_url, media_type, confidence_score)
            VALUES (?, ?, ?, ?, 1.0)
        ''', (trigger_text, response_type, media_url, media_type))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving media response: {e}")

def get_all_media_responses():
    """Get all multimedia responses"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, trigger_text, response_type, media_url, media_type, usage_count, created_at
            FROM ai_responses WHERE response_type != 'text'
            ORDER BY created_at DESC
        ''')
        responses = cursor.fetchall()
        conn.close()
        return responses
    except Exception as e:
        logger.error(f"Error getting media responses: {e}")
        return []

def save_ai_settings(settings):
    """Save AI engine settings"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        
        for key, value in settings.items():
            cursor.execute('''
                INSERT OR REPLACE INTO bot_settings (setting_key, setting_value, updated_at)
                VALUES (?, ?, datetime('now'))
            ''', (f'ai_{key}', json.dumps(value)))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving AI settings: {e}")

def get_ai_settings():
    """Get AI engine settings"""
    try:
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT setting_key, setting_value FROM bot_settings 
            WHERE setting_key LIKE 'ai_%'
        ''')
        
        settings_data = cursor.fetchall()
        conn.close()
        
        settings = {
            'model_name': 'gpt-4o',
            'max_tokens': 500,
            'temperature': 0.7,
            'enable_learning': True,
            'fallback_mode': 'intelligent'
        }
        
        for key, value in settings_data:
            clean_key = key.replace('ai_', '')
            try:
                settings[clean_key] = json.loads(value)
            except:
                settings[clean_key] = value
        
        return settings
    except Exception as e:
        logger.error(f"Error getting AI settings: {e}")
        return {}

if __name__ == '__main__':
    print("🚀 Starting Facebook Messenger Bot...")
    print("📱 Homepage: http://localhost:5000")
    print("🔧 Admin Panel: http://localhost:5000/admin/login")
    print("🔑 Admin Login: admin / admin123")
    print("🔍 Health Check: http://localhost:5000/health")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
    app.run(debug=True, host='0.0.0.0', port=5000)