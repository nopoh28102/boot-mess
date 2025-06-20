#!/usr/bin/env python3
"""
Enhanced AI Engine with OpenAI Integration and Learning Capabilities
Supports multimedia responses and intelligent conversation learning
"""

import os
import json
import openai
import aiohttp
import asyncio
import sqlite3
import logging
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re
from typing import Dict, List, Optional, Tuple, Any

# Configure logging
logger = logging.getLogger(__name__)

class EnhancedAIEngine:
    """Advanced AI Engine with learning capabilities and multimedia support"""
    
    def __init__(self, db_path='facebook_bot.db'):
        self.db_path = db_path
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.huggingface_api_key = os.getenv('HUGGINGFACE_API_KEY')
        self.model_name = os.getenv('MODEL_NAME', 'gpt-4o')
        self.max_tokens = int(os.getenv('MAX_TOKENS', '500'))
        self.temperature = float(os.getenv('TEMPERATURE', '0.7'))
        
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        openai.api_key = self.openai_api_key
        
        # Initialize vectorizer for similarity matching
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        self.conversation_vectors = None
        self.conversation_texts = []
        
        # Initialize database tables for learning
        self._init_learning_tables()
        
        # Load conversation history for learning
        self._load_conversation_history()

    def _init_learning_tables(self):
        """Initialize tables for AI learning and multimedia responses"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enhanced responses table with multimedia support
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_text TEXT NOT NULL,
                response_text TEXT,
                response_type TEXT DEFAULT 'text',
                media_url TEXT,
                media_type TEXT,
                confidence_score REAL DEFAULT 0.5,
                success_rate REAL DEFAULT 0.0,
                usage_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Learning feedback table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learning_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                user_feedback TEXT,
                feedback_score INTEGER,
                ai_response_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                FOREIGN KEY (ai_response_id) REFERENCES ai_responses(id)
            )
        ''')
        
        # Templates table for cards and buttons
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT UNIQUE NOT NULL,
                template_type TEXT NOT NULL,
                template_data TEXT NOT NULL,
                description TEXT,
                usage_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Context learning table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                context_key TEXT NOT NULL,
                context_value TEXT NOT NULL,
                expiry_date DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default templates
        default_templates = [
            ('welcome_buttons', 'button_template', json.dumps({
                'text': 'مرحباً بك! كيف يمكنني مساعدتك؟',
                'buttons': [
                    {'type': 'postback', 'title': 'المنتجات', 'payload': 'PRODUCTS'},
                    {'type': 'postback', 'title': 'الدعم', 'payload': 'SUPPORT'},
                    {'type': 'postback', 'title': 'معلومات', 'payload': 'INFO'}
                ]
            }), 'قالب ترحيب مع أزرار'),
            
            ('product_cards', 'generic_template', json.dumps({
                'elements': [
                    {
                        'title': 'منتج رقم 1',
                        'subtitle': 'وصف المنتج الأول',
                        'image_url': 'https://via.placeholder.com/300x200',
                        'buttons': [
                            {'type': 'postback', 'title': 'تفاصيل', 'payload': 'PRODUCT_1'},
                            {'type': 'web_url', 'title': 'شراء', 'url': 'https://example.com/product1'}
                        ]
                    },
                    {
                        'title': 'منتج رقم 2',
                        'subtitle': 'وصف المنتج الثاني',
                        'image_url': 'https://via.placeholder.com/300x200',
                        'buttons': [
                            {'type': 'postback', 'title': 'تفاصيل', 'payload': 'PRODUCT_2'},
                            {'type': 'web_url', 'title': 'شراء', 'url': 'https://example.com/product2'}
                        ]
                    }
                ]
            }), 'قالب بطاقات المنتجات')
        ]
        
        cursor.executemany('''
            INSERT OR IGNORE INTO message_templates (template_name, template_type, template_data, description)
            VALUES (?, ?, ?, ?)
        ''', default_templates)
        
        conn.commit()
        conn.close()

    def _load_conversation_history(self):
        """Load conversation history for learning"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT message, response FROM conversations 
                WHERE length(message) > 3 AND length(response) > 3
                ORDER BY timestamp DESC LIMIT 1000
            ''')
            
            conversations = cursor.fetchall()
            conn.close()
            
            if conversations:
                self.conversation_texts = [f"{conv[0]} {conv[1]}" for conv in conversations]
                if len(self.conversation_texts) > 1:
                    self.conversation_vectors = self.vectorizer.fit_transform(self.conversation_texts)
                
            logger.info(f"Loaded {len(self.conversation_texts)} conversations for learning")
            
        except Exception as e:
            logger.error(f"Error loading conversation history: {e}")
            self.conversation_texts = []
            self.conversation_vectors = None

    async def generate_ai_response(self, user_id: str, message: str, context: Dict = None) -> Dict:
        """Generate intelligent response using multiple AI providers"""
        try:
            # Get user context
            user_context = self._get_user_context(user_id)
            if context:
                user_context.update(context)
            
            # Try to find similar conversations first
            learned_response = self._find_similar_conversation(message)
            if learned_response and learned_response['confidence'] > 0.8:
                return {
                    'text': learned_response['response'],
                    'type': 'learned',
                    'confidence': learned_response['confidence'],
                    'source': 'conversation_learning'
                }
            
            # Generate response using OpenAI
            if self.openai_api_key:
                openai_response = await self._get_openai_response(user_id, message, user_context or {})
                if openai_response:
                    return openai_response
            
            # Fallback to HuggingFace
            if self.huggingface_api_key:
                hf_response = await self._get_huggingface_response(message, user_context or {})
                if hf_response:
                    return hf_response
            
            # Ultimate fallback
            return {
                'text': self._get_fallback_response(message),
                'type': 'fallback',
                'confidence': 0.3,
                'source': 'fallback'
            }
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return {
                'text': 'عذراً، حدث خطأ. الرجاء المحاولة مرة أخرى.',
                'type': 'error',
                'confidence': 0.1,
                'source': 'error'
            }

    async def _get_openai_response(self, user_id: str, message: str, context: Dict) -> Optional[Dict]:
        """Get response from OpenAI GPT"""
        try:
            # Build conversation context
            conversation_history = self._get_recent_conversation(user_id, limit=5)
            
            system_prompt = """أنت مساعد ذكي ومفيد في خدمة العملاء. 
            - اجب باللغة العربية بشكل ودود ومهني
            - كن مفيداً ومساعداً قدر الإمكان
            - إذا لم تعرف الإجابة، اعترف بذلك واقترح البدائل
            - حافظ على طول الرد مناسب (أقل من 500 حرف)
            - استخدم نبرة دافئة وودودة"""
            
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history
            for conv in conversation_history:
                messages.append({"role": "user", "content": conv['message']})
                messages.append({"role": "assistant", "content": conv['response']})
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            response = openai.ChatCompletion.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                presence_penalty=0.6,
                frequency_penalty=0.6
            )
            
            if hasattr(response, 'choices') and len(response.choices) > 0:
                ai_text = response.choices[0].message.content.strip()
            else:
                return None
            
            # Save successful response for learning
            self._save_ai_response(message, ai_text, 'openai', 0.9)
            
            return {
                'text': ai_text,
                'type': 'ai_generated',
                'confidence': 0.9,
                'source': 'openai',
                'model': self.model_name
            }
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return None

    async def _get_huggingface_response(self, message: str, context: Dict) -> Optional[Dict]:
        """Get response from HuggingFace"""
        try:
            url = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium"
            headers = {"Authorization": f"Bearer {self.huggingface_api_key}"}
            
            payload = {
                "inputs": message,
                "parameters": {
                    "max_length": 200,
                    "temperature": 0.7,
                    "return_full_text": False
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        if isinstance(result, list) and len(result) > 0:
                            hf_text = result[0].get('generated_text', '').strip()
                            
                            # Translate to Arabic if needed
                            if hf_text and self._is_english(hf_text):
                                hf_text = self._translate_to_arabic(hf_text)
                            
                            if hf_text:
                                self._save_ai_response(message, hf_text, 'huggingface', 0.7)
                                return {
                                    'text': hf_text,
                                    'type': 'ai_generated',
                                    'confidence': 0.7,
                                    'source': 'huggingface'
                                }
            
            return None
            
        except Exception as e:
            logger.error(f"HuggingFace API error: {e}")
            return None

    def _find_similar_conversation(self, message: str) -> Optional[Dict]:
        """Find similar conversation using ML similarity"""
        try:
            if not self.conversation_vectors or len(self.conversation_texts) == 0:
                return None
            
            # Vectorize the new message
            message_vector = self.vectorizer.transform([message])
            
            # Calculate similarities
            similarities = cosine_similarity(message_vector, self.conversation_vectors).flatten()
            
            # Find best match
            best_match_idx = np.argmax(similarities)
            best_similarity = similarities[best_match_idx]
            
            if best_similarity > 0.6:  # Threshold for similarity
                # Get the corresponding response
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT message, response FROM conversations 
                    WHERE length(message) > 3 AND length(response) > 3
                    ORDER BY timestamp DESC LIMIT 1000
                ''')
                
                conversations = cursor.fetchall()
                conn.close()
                
                if best_match_idx < len(conversations):
                    return {
                        'response': conversations[best_match_idx][1],
                        'confidence': float(best_similarity),
                        'similar_message': conversations[best_match_idx][0]
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding similar conversation: {e}")
            return None

    def _get_user_context(self, user_id: str) -> Dict:
        """Get user context for personalized responses"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get unexpired context
            cursor.execute('''
                SELECT context_key, context_value FROM conversation_context 
                WHERE user_id = ? AND (expiry_date IS NULL OR expiry_date > datetime('now'))
            ''', (user_id,))
            
            context_data = cursor.fetchall()
            conn.close()
            
            context = {}
            for key, value in context_data:
                try:
                    context[key] = json.loads(value)
                except:
                    context[key] = value
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting user context: {e}")
            return {}

    def _get_recent_conversation(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Get recent conversation history for context"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT message, response FROM conversations 
                WHERE user_id = ? 
                ORDER BY timestamp DESC LIMIT ?
            ''', (user_id, limit))
            
            conversations = cursor.fetchall()
            conn.close()
            
            return [{'message': conv[0], 'response': conv[1]} for conv in reversed(conversations)]
            
        except Exception as e:
            logger.error(f"Error getting recent conversation: {e}")
            return []

    def _save_ai_response(self, trigger_text: str, response_text: str, source: str, confidence: float):
        """Save AI response for future learning"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO ai_responses (trigger_text, response_text, confidence_score, usage_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(trigger_text) DO UPDATE SET
                usage_count = usage_count + 1,
                updated_at = datetime('now')
            ''', (trigger_text, response_text, confidence))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving AI response: {e}")

    def learn_from_feedback(self, conversation_id: int, feedback: str, score: int):
        """Learn from user feedback"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Save feedback
            cursor.execute('''
                INSERT INTO learning_feedback (conversation_id, user_feedback, feedback_score)
                VALUES (?, ?, ?)
            ''', (conversation_id, feedback, score))
            
            # Update success rates based on feedback
            if score >= 4:  # Positive feedback
                cursor.execute('''
                    UPDATE ai_responses 
                    SET success_rate = (success_rate * usage_count + 1.0) / (usage_count + 1)
                    WHERE id IN (
                        SELECT ai_response_id FROM learning_feedback 
                        WHERE conversation_id = ?
                    )
                ''', (conversation_id,))
            elif score <= 2:  # Negative feedback
                cursor.execute('''
                    UPDATE ai_responses 
                    SET success_rate = (success_rate * usage_count) / (usage_count + 1)
                    WHERE id IN (
                        SELECT ai_response_id FROM learning_feedback 
                        WHERE conversation_id = ?
                    )
                ''', (conversation_id,))
            
            conn.commit()
            conn.close()
            
            # Retrain if needed
            if score <= 2:
                self._retrain_from_feedback()
                
        except Exception as e:
            logger.error(f"Error learning from feedback: {e}")

    def _retrain_from_feedback(self):
        """Retrain the model based on feedback"""
        try:
            # Reload conversation history with updated feedback
            self._load_conversation_history()
            logger.info("Model retrained based on user feedback")
            
        except Exception as e:
            logger.error(f"Error retraining model: {e}")

    def get_message_template(self, template_name: str) -> Optional[Dict]:
        """Get message template for cards/buttons"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT template_type, template_data FROM message_templates 
                WHERE template_name = ?
            ''', (template_name,))
            
            result = cursor.fetchone()
            
            if result:
                # Update usage count
                cursor.execute('''
                    UPDATE message_templates 
                    SET usage_count = usage_count + 1 
                    WHERE template_name = ?
                ''', (template_name,))
                
                conn.commit()
                conn.close()
                
                return {
                    'type': result[0],
                    'data': json.loads(result[1])
                }
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Error getting message template: {e}")
            return None

    def create_multimedia_response(self, response_type: str, content: Dict) -> Dict:
        """Create multimedia response"""
        try:
            if response_type == 'image':
                return {
                    'attachment': {
                        'type': 'image',
                        'payload': {
                            'url': content.get('url'),
                            'is_reusable': True
                        }
                    }
                }
            
            elif response_type == 'video':
                return {
                    'attachment': {
                        'type': 'video',
                        'payload': {
                            'url': content.get('url'),
                            'is_reusable': True
                        }
                    }
                }
            
            elif response_type == 'audio':
                return {
                    'attachment': {
                        'type': 'audio',
                        'payload': {
                            'url': content.get('url'),
                            'is_reusable': True
                        }
                    }
                }
            
            elif response_type == 'file':
                return {
                    'attachment': {
                        'type': 'file',
                        'payload': {
                            'url': content.get('url'),
                            'is_reusable': True
                        }
                    }
                }
            
            elif response_type == 'button_template':
                return {
                    'attachment': {
                        'type': 'template',
                        'payload': {
                            'template_type': 'button',
                            'text': content.get('text'),
                            'buttons': content.get('buttons', [])
                        }
                    }
                }
            
            elif response_type == 'generic_template':
                return {
                    'attachment': {
                        'type': 'template',
                        'payload': {
                            'template_type': 'generic',
                            'elements': content.get('elements', [])
                        }
                    }
                }
            
            else:
                return {'text': content.get('text', 'رسالة غير مدعومة')}
                
        except Exception as e:
            logger.error(f"Error creating multimedia response: {e}")
            return {'text': 'خطأ في إنشاء الرد'}

    def _is_english(self, text: str) -> bool:
        """Check if text is in English"""
        return bool(re.search(r'[a-zA-Z]', text))

    def _translate_to_arabic(self, text: str) -> str:
        """Simple translation fallback (in production, use proper translation API)"""
        simple_translations = {
            'hello': 'مرحبا',
            'hi': 'مرحبا',
            'how are you': 'كيف حالك',
            'thank you': 'شكرا',
            'goodbye': 'وداعا',
            'yes': 'نعم',
            'no': 'لا'
        }
        
        text_lower = text.lower().strip()
        return simple_translations.get(text_lower, text)

    def _get_fallback_response(self, message: str) -> str:
        """Get fallback response based on message analysis"""
        message_lower = message.lower()
        
        # Greetings
        if any(word in message_lower for word in ['مرحبا', 'اهلا', 'هلا', 'السلام عليكم', 'hello', 'hi']):
            return 'مرحباً بك! أنا مساعد ذكي جاهز لمساعدتك. كيف يمكنني خدمتك؟'
        
        # Questions
        elif any(word in message_lower for word in ['كيف', 'ماذا', 'متى', 'أين', 'لماذا', 'من', '؟']):
            return 'سؤال ممتاز! أحاول فهم استفسارك بشكل أفضل. هل يمكنك توضيح المزيد من التفاصيل؟'
        
        # Thanks
        elif any(word in message_lower for word in ['شكرا', 'شكراً', 'thanks', 'thank you']):
            return 'العفو! سعيد لمساعدتك. هل تحتاج لأي شيء آخر؟'
        
        # Default
        else:
            return 'أقدر تواصلك معي. دعني أساعدك بأفضل طريقة ممكنة. ما الذي تريد معرفته؟'