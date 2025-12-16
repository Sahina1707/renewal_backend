# Intelipro Insurance Policy Renewal System - Backend

A comprehensive Django REST API backend for the Intelipro Insurance Policy Renewal Management System. This backend provides advanced data management, multi-channel campaign capabilities, real-time analytics, and complete case management for insurance policy renewals.

## 🚀 Features

### 🔐 **Authentication & Authorization**
- **Custom User Model** with email-based authentication
- **Role-Based Access Control (RBAC)** with 20+ configurable permissions
- **JWT Authentication** with refresh token rotation
- **Multi-Factor Authentication** support
- **Session Management** with device tracking
- **Account Security** with login attempt monitoring

### 📊 **Advanced Upload System**
- **Bulk Data Upload** with Excel (.xlsx) and CSV support
- **Real-time Processing** with Celery background tasks
- **Upload Validation** with comprehensive error reporting
- **Campaign Integration** for immediate campaign creation
- **Progress Tracking** with WebSocket updates
- **File Storage** on AWS S3 with secure access

### 🎯 **Multi-Channel Campaign Management**
- **Email Campaigns** with template management
- **WhatsApp Campaigns** via Business API integration
- **SMS Campaigns** with Twilio integration
- **Unified Campaign Creation** across all channels
- **Advanced Scheduling** with timezone support
- **Real-time Analytics** and performance tracking
- **Audience Segmentation** with dynamic filtering

### 📧 **Email Management System**
- **IMAP/SMTP Integration** for existing email accounts
- **Smart Email Categorization** with AI assistance
- **Bulk Email Processing** with queue management
- **Template System** with variable substitution
- **Email Analytics** with engagement tracking
- **Thread Management** for conversation tracking

### 📋 **Survey & Feedback System**
- **Dynamic Survey Builder** with multiple question types
- **Response Collection** with real-time analytics
- **Customer Satisfaction** tracking with NPS scoring
- **Automated Survey Distribution** via multiple channels
- **Sentiment Analysis** with AI integration

### 🔔 **Real-time Notifications**
- **WebSocket Support** via Django Channels
- **Multi-channel Notifications** (in-app, email, SMS)
- **User Preference Management** for notification settings
- **Real-time Dashboard Updates** for campaign metrics
- **System Alerts** for administrators

### 📈 **Analytics & Reporting**
- **Comprehensive Analytics** for all system activities
- **Campaign Performance** metrics and reporting
- **User Activity** tracking and analysis
- **Custom Reports** with export functionality
- **Real-time Dashboards** with live data updates

## 🛠️ Technology Stack

### **Core Framework**
- **Django 4.2** - Web framework
- **Django REST Framework 3.14** - API development
- **PostgreSQL** - Primary database
- **Redis** - Caching and session storage
- **Celery** - Background task processing

### **Real-time Features**
- **Django Channels 4.0** - WebSocket support
- **Redis Channels** - Channel layer backend

### **Third-party Integrations**
- **Twilio** - SMS messaging
- **WhatsApp Business API** - WhatsApp messaging
- **OpenAI API** - AI assistance and analysis
- **AWS S3** - File storage
- **AWS SES** - Email delivery

### **Security & Monitoring**
- **JWT Authentication** - Secure API access
- **Sentry** - Error tracking and monitoring
- **Django Security** - Built-in security features

## 🚀 Getting Started

### Prerequisites
- **Python 3.11+**
- **PostgreSQL 14+**
- **Redis 6+**
- **Virtual Environment** (venv or conda)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd renewal_backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp env.example .env
# Edit .env with your configuration
```

5. **Set up database**
```bash
# Create PostgreSQL database
createdb intelipro_renewal

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

6. **Load initial data**
```bash
python manage.py loaddata fixtures/initial_data.json
```

7. **Start development server**
```bash
python manage.py runserver
```

8. **Start Celery worker (in another terminal)**
```bash
celery -A renewal_backend worker -l info
```

9. **Start Celery beat (in another terminal)**
```bash
celery -A renewal_backend beat -l info
```

### Access Points
- **API Base URL**: http://localhost:8000/api/
- **Admin Interface**: http://localhost:8000/admin/
- **API Documentation**: http://localhost:8000/api/docs/
- **Health Check**: http://localhost:8000/health/

## 📁 Project Structure

```
renewal_backend/
├── apps/                          # Django applications
│   ├── authentication/           # Authentication & JWT
│   ├── users/                    # User management & RBAC
│   ├── customers/               # Customer management
│   ├── policies/                # Policy management
│   ├── uploads/                 # File upload system
│   ├── campaigns/               # Campaign management
│   ├── communications/          # Multi-channel messaging
│   ├── emails/                  # Email management
│   ├── surveys/                 # Survey & feedback
│   ├── claims/                  # Claims processing
│   ├── notifications/           # Real-time notifications
│   ├── analytics/               # Analytics & reporting
│   ├── files/                   # File management
│   └── core/                    # Core utilities
├── renewal_backend/             # Main project directory
│   ├── settings/               # Environment-specific settings
│   │   ├── base.py            # Base settings
│   │   ├── development.py     # Development settings
│   │   └── production.py      # Production settings
│   ├── urls.py                # Main URL configuration
│   ├── wsgi.py                # WSGI configuration
│   ├── asgi.py                # ASGI configuration (WebSocket)
│   └── celery.py              # Celery configuration
├── templates/                  # Django templates
├── static/                     # Static files
├── media/                      # Media files (development)
├── logs/                       # Log files
├── requirements.txt            # Python dependencies
├── manage.py                   # Django management script
└── env.example                 # Environment variables template
```

## 🔧 Configuration

### Environment Variables

Copy `env.example` to `.env` and configure:

```env
# Core Application
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/intelipro_renewal

# Redis
REDIS_URL=redis://localhost:6379/1

# File Storage (AWS S3)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_STORAGE_BUCKET_NAME=your-bucket-name

# Third-party APIs
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
WHATSAPP_ACCESS_TOKEN=your_whatsapp_token
OPENAI_API_KEY=your_openai_key
```

### Database Setup

The system uses PostgreSQL as the primary database. Run the provided SQL script to set up the complete schema:

```bash
# Using the provided database script
psql -d intelipro_renewal -f database/create_database.sql
```

## 📚 API Documentation

### Authentication Endpoints
- `POST /api/auth/login/` - User login
- `POST /api/auth/logout/` - User logout
- `POST /api/auth/refresh/` - Refresh JWT token
- `POST /api/auth/register/` - User registration

### Upload Endpoints
- `POST /api/upload/file/` - Upload policy data file
- `GET /api/upload/status/{id}/` - Get upload status
- `GET /api/upload/history/` - Get upload history
- `GET /api/upload/template/` - Download template

### Campaign Endpoints
- `GET /api/campaigns/` - List campaigns
- `POST /api/campaigns/` - Create campaign
- `GET /api/campaigns/{id}/` - Get campaign details
- `PUT /api/campaigns/{id}/status/` - Update campaign status
- `GET /api/campaigns/{id}/analytics/` - Get campaign analytics

### Communication Endpoints
- `POST /api/communications/whatsapp/send/` - Send WhatsApp message
- `POST /api/communications/sms/send/` - Send SMS message
- `GET /api/communications/delivery-status/{id}/` - Get delivery status

### Complete API documentation is available at `/api/docs/` when running the server.

## 🧪 Testing

### Run Tests
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.campaigns

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

### Test Data
```bash
# Load test fixtures
python manage.py loaddata fixtures/test_data.json
```

## 🚀 Deployment

### Docker Deployment

1. **Build Docker image**
```bash
docker build -t intelipro-backend .
```

2. **Run with Docker Compose**
```bash
docker-compose up -d
```

### Production Deployment

1. **Set environment**
```bash
export DJANGO_SETTINGS_MODULE=renewal_backend.settings.production
```

2. **Collect static files**
```bash
python manage.py collectstatic --noinput
```

3. **Run migrations**
```bash
python manage.py migrate
```

4. **Start with Gunicorn**
```bash
gunicorn renewal_backend.wsgi:application --bind 0.0.0.0:8000
```

5. **Start Celery services**
```bash
celery -A renewal_backend worker -D
celery -A renewal_backend beat -D
```

## 🔒 Security Features

### Authentication Security
- **JWT Tokens** with secure signing
- **Refresh Token Rotation** for enhanced security
- **Account Lockout** after failed login attempts
- **Session Management** with device tracking
- **Password Policies** with complexity requirements

### API Security
- **CORS Configuration** for frontend integration
- **Rate Limiting** to prevent abuse
- **Input Validation** with comprehensive sanitization
- **SQL Injection Protection** via Django ORM
- **XSS Prevention** with proper output encoding

### Data Security
- **Encrypted File Storage** on AWS S3
- **Database Encryption** at rest
- **Secure Communication** via HTTPS/TLS
- **Audit Logging** for compliance tracking
- **GDPR Compliance** with data protection features

## 📊 Monitoring & Logging

### Application Monitoring
- **Health Check Endpoints** for system status
- **Performance Metrics** with detailed logging
- **Error Tracking** via Sentry integration
- **Database Query Monitoring** for optimization
- **Celery Task Monitoring** for background jobs

### Logging Configuration
- **Structured Logging** with JSON format
- **Log Rotation** for disk space management
- **Security Event Logging** for audit trails
- **Performance Logging** for optimization
- **Error Aggregation** for quick issue resolution

## 🤝 Contributing

### Development Workflow
1. **Fork the repository**
2. **Create feature branch** (`git checkout -b feature/amazing-feature`)
3. **Follow coding standards** (PEP 8, Django best practices)
4. **Write comprehensive tests** for new features
5. **Update documentation** as needed
6. **Submit pull request** with detailed description

### Code Quality Standards
- **PEP 8** compliance for Python code
- **Django Best Practices** for model and view design
- **API Design Standards** for REST endpoints
- **Security Guidelines** for all implementations
- **Performance Considerations** for database queries

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation
- **API Documentation**: Available at `/api/docs/`
- **Admin Interface**: Available at `/admin/`
- **Health Monitoring**: Available at `/health/`

### Contact
- **Email**: support@intelipro.com
- **Issues**: GitHub Issues for bug reports
- **Features**: GitHub Discussions for feature requests

---

**Built with ❤️ for efficient insurance policy renewal management**
**© 2024 Intelipro Insurance Solutions. All rights reserved.** 