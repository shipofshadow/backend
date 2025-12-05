# iScholar API

A comprehensive scholarship management system built with Flask that provides an API for managing scholarship applications, evaluations, and administrative tasks for educational institutions.

## 🚀 Features

### Core Functionality
- **User Authentication & Authorization**: JWT-based authentication with role-based access control
- **Scholarship Management**: Create, update, and manage scholarship programs with customizable eligibility rules
- **Application Processing**: Complete scholarship application workflow with document upload support
- **Fuzzy Logic Evaluation**: Intelligent application evaluation using fuzzy logic algorithms
- **Real-time Notifications**: WebSocket-based real-time notifications system
- **Academic Integration**: Support for academic periods, campuses, departments, and courses
- **OAuth Integration**: Google and Facebook OAuth support for easy registration/login
- **Two-Factor Authentication**: Enhanced security with TOTP-based 2FA
- **Email Services**: Automated email notifications and communications
- **Reporting & Analytics**: Comprehensive reporting and dashboard features

### Advanced Features
- **Document Management**: File upload system supporting PDF, images, and documents
- **Caching**: Redis-based caching for improved performance
- **API Documentation**: Swagger/OpenAPI documentation
- **Admin Management**: Comprehensive admin panel for managing applicants and academic data
- **Prequalification System**: Automated eligibility checking for scholarship applications
- **Draft Applications**: Save application progress with draft functionality

## 🛠️ Technology Stack

### Backend
- **Framework**: Flask (Python)
- **Database**: MySQL with PyMySQL driver
- **Cache**: Redis
- **Authentication**: JWT (Flask-JWT-Extended)
- **Real-time**: Flask-SocketIO
- **Email**: Flask-Mail
- **File Handling**: Pillow for image processing
- **API Documentation**: Flasgger (Swagger)

### Key Dependencies
```
Flask - Web framework
Flask-JWT-Extended - JWT authentication
Flask-SocketIO - WebSocket support
Flask-Mail - Email services
Flask-Caching - Caching support
PyMySQL - MySQL database driver
Redis - Caching and session storage
Authlib - OAuth integration
pyotp - Two-factor authentication
qrcode - QR code generation
Pillow - Image processing
```

## 📁 Project Structure

```
ischolar-api/
├── app.py                 # Main Flask application
├── config.py             # Configuration management
├── extensions.py         # Flask extensions initialization
├── storage.py            # Database and Redis connections
├── requirements.txt      # Python dependencies
├── 2fa.py               # Two-factor authentication utilities
├── email.html           # Email templates
├── models/              # Data models
│   ├── user.py         # User model
│   └── application.py  # Application model
├── routes/              # API route blueprints
│   ├── auth.py         # Authentication routes
│   ├── scholarships.py # Scholarship management
│   ├── application.py  # Application processing
│   ├── applicants.py   # Applicant management
│   ├── dashboard.py    # Dashboard and analytics
│   ├── evaluation.py   # Application evaluation
│   ├── fuzzy_logic.py  # Fuzzy logic evaluation
│   ├── notification.py # Real-time notifications
│   ├── oauth.py        # OAuth integration
│   ├── profile.py      # User profile management
│   └── ...            # Additional route modules
├── services/            # Business logic services
│   ├── auth_service.py      # Authentication logic
│   ├── application_service.py # Application processing
│   ├── email_service.py     # Email handling
│   ├── eligibility_service.py # Eligibility checking
│   ├── notification_service.py # Notification management
│   ├── recommend_service.py    # Recommendation system
│   └── admin/          # Admin-specific services
├── utils/               # Utility functions
│   ├── applications.py # Application utilities
│   ├── decorator.py    # Custom decorators
│   ├── hashing.py      # Password hashing
│   ├── response.py     # API response utilities
│   └── ...            # Additional utilities
├── templates/           # Email templates
├── uploads/            # File upload directory
└── __pycache__/        # Python cache files
```

## 🔧 Installation & Setup

### Prerequisites
- Python 3.8+
- MySQL 5.7+
- Redis 6.0+
- Virtual environment (recommended)

### Environment Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ischolar-api
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

4. **Environment Configuration**
   Create a `.env` file in the project root:
   ```env
   # Database Configuration
   DB_HOST=localhost
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_NAME=ischolar_db

   # JWT Configuration
   JWT_SECRET_KEY=your_jwt_secret_key

   # Redis Configuration
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_PASSWORD=your_redis_password

   # Encryption
   FERNET_KEY=your_fernet_key

   # Email Configuration
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   MAIL_USERNAME=your_email@gmail.com
   MAIL_PASSWORD=your_email_password
   MAIL_DEFAULT_SENDER=your_email@gmail.com

   # Application URL
   APP_URL=http://localhost:8000

   # OAuth Configuration
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   FACEBOOK_APP_ID=your_facebook_app_id
   FACEBOOK_APP_SECRET=your_facebook_app_secret
   ```

5. **Database Setup**
   - Create MySQL database
   - Import database schema (if provided)
   - Ensure database user has proper permissions

   **Required Tables**
   
   For the Potential Applicants feature, create the following table:
   ```sql
   CREATE TABLE `application_reminders` (
     `id` int(11) NOT NULL AUTO_INCREMENT,
     `student_id` int(11) NOT NULL,
     `semester_id` int(11) NOT NULL,
     `sent_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
     `sent_by` int(11) DEFAULT NULL,
     PRIMARY KEY (`id`),
     UNIQUE KEY `unique_reminder` (`student_id`, `semester_id`),
     KEY `idx_semester` (`semester_id`)
   );
   ```

6. **Redis Setup**
   - Start Redis server
   - Configure Redis with password if required

### Running the Application

**Development Mode**
```bash
python app.py
```

**Production Mode**
```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 app:app
```

The API will be available at:
- **API Base URL**: `http://localhost:8000/api`
- **API Documentation**: `http://localhost:8000/apidocs`
- **Health Check**: `http://localhost:8000/api/ping`

## 📚 API Documentation

### Authentication Endpoints
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration
- `POST /api/auth/logout` - User logout
- `POST /api/auth/forgot-password` - Password reset request
- `POST /api/auth/reset-password` - Password reset confirmation
- `POST /api/auth/verify-2fa` - Two-factor authentication verification

### Scholarship Management
- `GET /api/scholarships/` - Get all scholarships
- `POST /api/scholarships/` - Create new scholarship
- `PUT /api/scholarships/{id}` - Update scholarship
- `DELETE /api/scholarships/{id}` - Delete scholarship
- `GET /api/scholarships/{id}/applicants` - Get scholarship applicants

### Application Processing
- `POST /api/applications/` - Submit application
- `GET /api/applications/` - Get user applications
- `PUT /api/applications/{id}` - Update application
- `POST /api/applications/{id}/submit` - Submit application for review
- `GET /api/applications/{id}/status` - Get application status

### Admin Functions
- `GET /api/applicants/` - Get all applicants (admin)
- `PUT /api/applicants/{id}/status` - Update applicant status
- `POST /api/evaluations/` - Create evaluation
- `GET /api/dashboard/stats` - Get dashboard statistics

### Potential Applicants
- `GET /api/students/potential-applicants` - Get students who registered but haven't applied
- `POST /api/students/send-application-reminder` - Send reminder email to a single student
- `POST /api/students/send-bulk-reminders` - Send bulk reminder emails to multiple students

### Real-time Features
- WebSocket connection for real-time notifications
- Connect with JWT token for authenticated users

## 🔐 Security Features

- **JWT Authentication**: Secure token-based authentication
- **Password Hashing**: Argon2-based password hashing
- **Two-Factor Authentication**: TOTP-based 2FA support
- **CORS Configuration**: Properly configured CORS for frontend integration
- **Input Validation**: Comprehensive input validation and sanitization
- **File Upload Security**: Secure file upload with type validation
- **SQL Injection Protection**: Parameterized queries throughout

## 🌐 Integration

### OAuth Providers
- **Google OAuth**: Complete Google sign-in integration
- **Facebook OAuth**: Facebook authentication support

### Email Services
- **SMTP Support**: Configurable SMTP email services
- **Template System**: HTML email templates for notifications
- **Automated Emails**: Registration, password reset, and status updates

### File Management
- **Supported Formats**: PDF, PNG, JPG, JPEG, DOCX
- **Upload Directory**: Organized file storage in `uploads/` folder
- **Image Processing**: Pillow integration for image handling

## 🚀 Deployment

### Production Considerations
- Use environment variables for all sensitive configuration
- Configure proper database connection pooling
- Set up Redis clustering for high availability
- Implement proper logging and monitoring
- Use HTTPS in production
- Configure proper CORS origins for your frontend

### Docker Deployment (Optional)
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:8000", "app:app"]
```

## 📊 Monitoring & Logging

- **Health Check**: `/api/ping` endpoint for service monitoring
- **Error Handling**: Comprehensive error handling with proper HTTP status codes
- **Logging**: Built-in Flask logging for debugging and monitoring

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the API documentation at `/apidocs`
- Review the codebase documentation

---

**iScholar API** - Empowering educational institutions with comprehensive scholarship management solutions.
