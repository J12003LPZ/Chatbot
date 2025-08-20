# ChatBot Premium

A premium ChatGPT clone with a full-screen interface built with Flask and powered by Google's Gemma 3n 2B multimodal model through OpenRouter API. Features include persistent conversation storage with NeonDB, multimodal file support (PDFs, images, text), and a modern ChatGPT-like dark interface.

## ✨ Features

- 🤖 **AI Chat Interface** - Powered by Google's Gemma 3n 2B multilingual multimodal model
- 🎨 **Full-Screen ChatGPT Interface** - Dark theme with sidebar navigation and main chat area
- 📁 **Multimodal File Support** - Upload and analyze PDFs, images (optimized for Gemma 3n), and text files
- 💾 **Persistent Storage** - NeonDB PostgreSQL integration with automatic fallback to in-memory storage
- 💬 **Chat History** - Cross-session conversation persistence with database storage
- 📱 **Responsive Design** - Mobile-first approach with collapsible sidebar
- 🔒 **Secure & Private** - Environment variable configuration, no tracking
- ⚡ **Fast Deployment** - Optimized for Vercel serverless functions
- 🔄 **Robust Architecture** - Database fallback system ensures 100% uptime

## 🛠 Tech Stack

- **Backend**: Flask 3.0 (Python 3.9+)
- **Database**: NeonDB PostgreSQL with SQLAlchemy ORM
- **AI Model**: Google Gemma 3n 2B (free via OpenRouter)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Deployment**: Vercel serverless functions
- **File Processing**: PyPDF2, Pillow (optimized for Gemma 3n resolutions)
- **Security**: python-dotenv, Flask-CORS, input validation

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd chabot
```

### 2. Environment Configuration

Create a `.env` file in the root directory:

```env
# Required: OpenRouter API Key (Free at openrouter.ai)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Required: Flask Secret Key
SECRET_KEY=your_secret_key_here

# Optional: NeonDB PostgreSQL for persistent storage
# If not provided, will use in-memory storage as fallback
DATABASE_URL=postgresql://username:password@your-neon-host.neon.tech/chatbot_db

# Application Configuration
FLASK_ENV=production
DEBUG=False
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Local Development

```bash
python api/index.py
```

Visit `http://localhost:5000` to see the application.

## Deployment to Vercel

### Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **OpenRouter API Key**: Get your free API key at [openrouter.ai](https://openrouter.ai)

### Deployment Steps

#### Method 1: Vercel CLI (Recommended)

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Login to Vercel:
```bash
vercel login
```

3. Deploy:
```bash
vercel
```

4. Set environment variables:
```bash
vercel env add OPENROUTER_API_KEY
vercel env add SECRET_KEY
```

5. Redeploy with environment variables:
```bash
vercel --prod
```

#### Method 2: GitHub Integration

1. Push your code to GitHub
2. Connect your repository to Vercel
3. Add environment variables in Vercel dashboard:
   - `OPENROUTER_API_KEY`: Your OpenRouter API key
   - `SECRET_KEY`: A random secret key for Flask sessions

### Environment Variables Setup

In your Vercel project settings, add these environment variables:

- **OPENROUTER_API_KEY**: Your OpenRouter API key (get it free at openrouter.ai)
- **SECRET_KEY**: A secure random string for Flask session management

## API Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/` | GET | Main chat interface |
| `/api/chat` | POST | Send message to AI |
| `/api/upload` | POST | Upload file for analysis |
| `/api/history/<session_id>` | GET | Get chat history |
| `/api/sessions` | GET | List all chat sessions |
| `/api/health` | GET | Health check |

## File Upload Support

Supported file types:
- **PDFs** (.pdf) - Text extraction and analysis
- **Images** (.png, .jpg, .jpeg, .gif) - Image processing and analysis
- **Text Files** (.txt) - Direct text content analysis

Maximum file size: 16MB

## Architecture

```
chabot/
├── api/
│   └── index.py          # Flask application
├── templates/
│   └── index.html        # Frontend interface
├── static/               # Static assets
├── uploads/              # Temporary file uploads
├── requirements.txt      # Python dependencies
├── vercel.json          # Vercel configuration
├── .env.example         # Environment template
└── .gitignore           # Git ignore rules
```

## Development Guide

### Local Development

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`

4. Run development server:
```bash
python api/index.py
```

### Adding New Features

The application is structured for easy extension:

- **Backend routes**: Add new endpoints in `api/index.py`
- **Frontend**: Modify `templates/index.html`
- **Styling**: Update CSS in the `<style>` section
- **JavaScript**: Add functionality in the `<script>` section

## Security Features

- Environment variable configuration
- File type validation
- File size limits
- CORS protection
- Input sanitization
- Session management

## Performance Optimizations

- Serverless function optimization
- File cleanup after processing
- Efficient message history management
- Responsive design for all devices
- Optimized API calls

## Troubleshooting

### Common Issues

1. **API Key Error**: Ensure OPENROUTER_API_KEY is set correctly
2. **File Upload Fails**: Check file size (<16MB) and type
3. **Deployment Issues**: Verify vercel.json configuration
4. **Chat Not Working**: Check network connection and API status

### Debug Mode

For local debugging, set in `.env`:
```env
FLASK_ENV=development
DEBUG=True
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
- Check the troubleshooting section
- Review the API documentation
- Open an issue on GitHub

---

Built with ❤️ using Flask, OpenRouter, and Vercel.