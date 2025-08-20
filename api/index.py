from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import requests
import os
import json
import uuid
import time
from datetime import datetime
import logging
from werkzeug.utils import secure_filename
import PyPDF2
import base64
from PIL import Image
import io
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import cloudinary.api
# Import database manager
try:
    from database import DatabaseManager
except ImportError:
    from .database import DatabaseManager

# Load environment variables
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

app = Flask(__name__, static_folder='../static', template_folder='../templates')
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database manager
db_manager = DatabaseManager()

# In-memory fallback storage
chat_sessions = {}
max_memory_sessions = 100

# OpenRouter configuration - Using requests
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

if OPENROUTER_API_KEY:
    logger.info("OpenRouter API key found")
else:
    logger.error("OPENROUTER_API_KEY not found in environment variables")

# Configuration
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_stream):
    """Extract text from PDF file stream"""
    try:
        pdf_reader = PyPDF2.PdfReader(file_stream)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting PDF text: {e}")
        return None

def process_image_stream(file_stream):
    """Process image file stream for multimodal input"""
    try:
        img = Image.open(file_stream)
        
        # Convert to base64 for API
        buffer = io.BytesIO()
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        img.save(buffer, format='JPEG', quality=90)
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return img_str, (img.width, img.height)
            
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        return None, None

def save_message_with_fallback(session_id, role, content):
    """Save message to database with in-memory fallback"""
    # Try database first
    if db_manager.connected and db_manager.add_message(session_id, role, content):
        return True
    
    # Fallback to in-memory storage
    logger.warning(f"Using in-memory fallback for session {session_id}")
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    
    chat_sessions[session_id].append({
        'role': role,
        'content': content,
        'timestamp': datetime.now().isoformat()
    })
    
    # Limit memory usage
    if len(chat_sessions) > max_memory_sessions:
        oldest_session = min(chat_sessions.keys(), key=lambda x: len(chat_sessions[x]))
        del chat_sessions[oldest_session]
    
    return True

def get_messages_with_fallback(session_id):
    """Get messages from database with in-memory fallback"""
    # Try database first
    if db_manager.connected:
        messages = db_manager.get_session_messages(session_id)
        if messages:
            return messages
    
    # Fallback to in-memory storage
    return chat_sessions.get(session_id, [])

def create_session_with_fallback(session_id):
    """Create session in database with in-memory fallback"""
    # Try database first
    if db_manager.connected and db_manager.create_session(session_id):
        return session_id
    
    # Fallback to in-memory storage
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    
    return session_id

def format_multimodal_message(content, image_data=None):
    """Format message for Gemma 3n multimodal API via OpenRouter"""
    if image_data:
        # OpenRouter multimodal format for Gemma 3n
        return [
            {
                "type": "text",
                "text": content
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_data}"
                }
            }
        ]
    else:
        return content

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
        
        user_message = data['message']
        session_id = data.get('session_id', str(uuid.uuid4()))
        image_data = data.get('image_data')  # Base64 encoded image from frontend
        
        # Create session if it doesn't exist
        existing_messages = get_messages_with_fallback(session_id)
        if not existing_messages:
            session_id = create_session_with_fallback(session_id)
        
        # Format user message content (handle multimodal if image present)
        if image_data:
            # For storage, we'll save a text description and note about image
            storage_content = f"[IMAGE ATTACHED] {user_message}"
            # For API call, we'll use multimodal format
            api_content = format_multimodal_message(user_message, image_data)
        else:
            storage_content = user_message
            api_content = user_message
        
        # Add user message to session
        if not save_message_with_fallback(session_id, 'user', storage_content):
            return jsonify({'error': 'Failed to save message'}), 500
        
        # Check if API key is available
        if not OPENROUTER_API_KEY:
            return jsonify({'error': 'AI service is currently unavailable. Please check your API configuration.'}), 503
        
        # Get conversation history (last 10 messages)
        all_messages = get_messages_with_fallback(session_id)
        recent_messages = all_messages[-10:] if len(all_messages) > 10 else all_messages
        
        # Prepare messages for API call
        messages = []
        for i, msg in enumerate(recent_messages):
            if msg['role'] in ['user', 'assistant']:
                # For the most recent user message, use multimodal format if image present
                if i == len(recent_messages) - 1 and msg['role'] == 'user' and image_data:
                    messages.append({
                        'role': msg['role'],
                        'content': api_content
                    })
                else:
                    # Clean up image markers for older messages
                    content = msg['content']
                    if content.startswith('[IMAGE ATTACHED] '):
                        content = content.replace('[IMAGE ATTACHED] ', '')
                    
                    messages.append({
                        'role': msg['role'],
                        'content': content
                    })
        
        # Call OpenRouter API using requests
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "ChatBot"
        }
        
        # Use a multimodal-capable model for image inputs, fallback to text-only model
        if any(isinstance(msg.get('content'), list) for msg in messages):
            # Has multimodal content, use a multimodal model
            model_name = "meta-llama/llama-3.2-11b-vision-instruct:free"
        else:
            # Text-only, use the original model
            model_name = "google/gemma-3n-e2b-it:free"
        
        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"OpenRouter API error: {response.status_code} - {error_text}")
            logger.error(f"Used model: {model_name}")
            logger.error(f"Request payload: {payload}")
            return jsonify({'error': f'AI service error: {error_text}'}), 500
        
        response_data = response.json()
        ai_response = response_data['choices'][0]['message']['content']
        
        # Add AI response to session
        if not save_message_with_fallback(session_id, 'assistant', ai_response):
            return jsonify({'error': 'Failed to save AI response'}), 500
        
        # Get updated message count
        updated_messages = get_messages_with_fallback(session_id)
        message_count = len([m for m in updated_messages if m['role'] in ['user', 'assistant']])
        
        return jsonify({
            'response': ai_response,
            'session_id': session_id,
            'message_count': message_count
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({'error': 'An error occurred while processing your request'}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        session_id = request.form.get('session_id', str(uuid.uuid4()))
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': 'File too large'}), 400
        
        # Process file based on type
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        processed_content = None
        image_data = None
        cloudinary_url = None
        
        # Create session if it doesn't exist
        existing_messages = get_messages_with_fallback(session_id)
        if not existing_messages:
            session_id = create_session_with_fallback(session_id)
        
        if file_extension == 'pdf':
            processed_content = extract_text_from_pdf(file)
            if processed_content:
                # Upload PDF to Cloudinary for storage
                try:
                    result = cloudinary.uploader.upload(file, resource_type="raw", folder="chatbot/pdfs")
                    cloudinary_url = result.get('secure_url')
                except Exception as e:
                    logger.error(f"Error uploading PDF to Cloudinary: {e}")
                
                # Add file content to chat session
                content = f"User uploaded a PDF file '{file.filename}'. Content:\n\n{processed_content[:2000]}{'...' if len(processed_content) > 2000 else ''}"
                save_message_with_fallback(session_id, 'system', content)
        
        elif file_extension in ['png', 'jpg', 'jpeg', 'gif']:
            # Process image for API
            file.seek(0)  # Reset file pointer
            image_data, image_size = process_image_stream(file)
            
            if image_data:
                # Upload original image to Cloudinary
                try:
                    file.seek(0)  # Reset file pointer again
                    result = cloudinary.uploader.upload(file, folder="chatbot/images")
                    cloudinary_url = result.get('secure_url')
                except Exception as e:
                    logger.error(f"Error uploading image to Cloudinary: {e}")
                
                # Store image data for potential use in chat
                content = f"User uploaded an image file '{file.filename}' ({image_size[0]}x{image_size[1]}). The image has been processed and is ready for analysis."
                save_message_with_fallback(session_id, 'system', content)
                
                # Return image data for immediate use in frontend
                return jsonify({
                    'success': True,
                    'filename': file.filename,
                    'session_id': session_id,
                    'message': f'Image "{file.filename}" uploaded and processed successfully',
                    'image_data': image_data,
                    'image_size': image_size,
                    'cloudinary_url': cloudinary_url
                })
        
        elif file_extension == 'txt':
            text_content = file.read().decode('utf-8')
            
            # Upload text file to Cloudinary
            try:
                file.seek(0)
                result = cloudinary.uploader.upload(file, resource_type="raw", folder="chatbot/texts")
                cloudinary_url = result.get('secure_url')
            except Exception as e:
                logger.error(f"Error uploading text file to Cloudinary: {e}")
            
            content = f"User uploaded a text file '{file.filename}'. Content:\n\n{text_content[:2000]}{'...' if len(text_content) > 2000 else ''}"
            save_message_with_fallback(session_id, 'system', content)
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'session_id': session_id,
            'message': f'File "{file.filename}" uploaded and processed successfully',
            'cloudinary_url': cloudinary_url
        })
        
    except Exception as e:
        logger.error(f"Error in upload endpoint: {e}")
        return jsonify({'error': 'An error occurred while uploading the file'}), 500

@app.route('/api/history/<session_id>')
def get_chat_history(session_id):
    try:
        # Validate session_id
        if not session_id or session_id.strip() == '' or session_id == 'undefined':
            logger.warning(f"Invalid session_id received: {session_id}")
            return jsonify({'error': 'Invalid session ID'}), 400
        
        messages = get_messages_with_fallback(session_id)
        if messages:
            # Get session creation time (first message timestamp if available)
            created_at = messages[0]['timestamp'] if messages else None
            return jsonify({
                'messages': messages,
                'created_at': created_at
            })
        else:
            return jsonify({'messages': [], 'created_at': None})
    except Exception as e:
        logger.error(f"Error getting chat history for session {session_id}: {e}")
        return jsonify({'error': 'An error occurred while retrieving chat history'}), 500

@app.route('/api/sessions')
def list_sessions():
    try:
        # Try database first
        if db_manager.connected:
            sessions = db_manager.get_recent_sessions()
            if sessions:
                return jsonify({'sessions': sessions})
        
        # Fallback to in-memory sessions
        memory_sessions = []
        for session_id, messages in chat_sessions.items():
            if messages:
                first_user_msg = next((msg for msg in messages if msg['role'] == 'user'), None)
                preview = "New chat"
                if first_user_msg:
                    preview = first_user_msg['content'][:50]
                    if len(first_user_msg['content']) > 50:
                        preview += "..."
                
                message_count = len([m for m in messages if m['role'] in ['user', 'assistant']])
                
                memory_sessions.append({
                    'session_id': session_id,
                    'preview': preview,
                    'created_at': messages[0]['timestamp'],
                    'updated_at': messages[-1]['timestamp'],
                    'message_count': message_count
                })
        
        # Sort by updated_at descending
        memory_sessions.sort(key=lambda x: x['updated_at'], reverse=True)
        
        return jsonify({'sessions': memory_sessions})
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return jsonify({'error': 'An error occurred while retrieving sessions'}), 500

@app.route('/api/delete-session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    try:
        # Validate session_id
        if not session_id or session_id.strip() == '' or session_id == 'undefined':
            logger.warning(f"Invalid session_id received for deletion: {session_id}")
            return jsonify({'error': 'Invalid session ID'}), 400
        
        # Try to delete from database first
        deleted_from_db = False
        if db_manager.connected:
            try:
                deleted_from_db = db_manager.delete_session(session_id)
            except Exception as e:
                logger.error(f"Error deleting session from database: {e}")
        
        # Delete from in-memory storage
        deleted_from_memory = session_id in chat_sessions
        if deleted_from_memory:
            del chat_sessions[session_id]
        
        if deleted_from_db or deleted_from_memory:
            return jsonify({'success': True, 'message': 'Session deleted successfully'})
        else:
            return jsonify({'error': 'Session not found'}), 404
            
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        return jsonify({'error': 'An error occurred while deleting the session'}), 500

@app.route('/api/health')
def health_check():
    db_status = db_manager.health_check() if db_manager else {'status': 'not initialized'}
    
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'database': db_status,
        'fallback_sessions': len(chat_sessions),
        'openrouter_configured': bool(OPENROUTER_API_KEY)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)