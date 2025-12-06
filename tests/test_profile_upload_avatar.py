"""Tests for profile avatar upload functionality."""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
from io import BytesIO

import sys
import os

# Set environment variables before importing modules that use Config
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DB_USER', 'test')
os.environ.setdefault('DB_PASSWORD', 'test')
os.environ.setdefault('DB_NAME', 'test')
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret')
os.environ.setdefault('REDIS_HOST', 'localhost')
os.environ.setdefault('REDIS_PORT', '6379')
os.environ.setdefault('REDIS_PASSWORD', '')
os.environ.setdefault('FERNET_KEY', 'test-key')
os.environ.setdefault('MAIL_SERVER', 'localhost')
os.environ.setdefault('MAIL_PORT', '587')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock external connections before importing profile module
with patch('redis.Redis'):
    with patch('pymysql.connect'):
        from routes.profile import profile_bp


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = 'test-secret-key'
    app.config['TESTING'] = True
    JWTManager(app)
    app.register_blueprint(profile_bp)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestUploadAvatar:
    """Test the upload_avatar endpoint."""

    def test_upload_avatar_no_file(self, app, client):
        """Test upload fails when no file is provided."""
        with app.app_context():
            token = create_access_token(identity="1")
            response = client.post(
                '/api/profile/upload-avatar',
                headers={'Authorization': f'Bearer {token}'},
                content_type='multipart/form-data',
                data={}
            )
            assert response.status_code == 400
            assert response.json['error'] == 'No avatar file provided'

    def test_upload_avatar_empty_filename(self, app, client):
        """Test upload fails when file has empty filename."""
        with app.app_context():
            token = create_access_token(identity="1")
            data = {'avatar': (BytesIO(b''), '')}
            response = client.post(
                '/api/profile/upload-avatar',
                headers={'Authorization': f'Bearer {token}'},
                content_type='multipart/form-data',
                data=data
            )
            assert response.status_code == 400
            assert response.json['error'] == 'No file selected'

    def test_upload_avatar_invalid_file_type(self, app, client):
        """Test upload fails with invalid file type."""
        with app.app_context():
            token = create_access_token(identity="1")
            data = {'avatar': (BytesIO(b'test content'), 'test.txt')}
            response = client.post(
                '/api/profile/upload-avatar',
                headers={'Authorization': f'Bearer {token}'},
                content_type='multipart/form-data',
                data=data
            )
            assert response.status_code == 400
            assert response.json['error'] == 'Invalid file type. Allowed: png, jpg, jpeg, gif'

    def test_upload_avatar_invalid_file_type_exe(self, app, client):
        """Test upload fails with dangerous file type."""
        with app.app_context():
            token = create_access_token(identity="1")
            data = {'avatar': (BytesIO(b'test content'), 'malware.exe')}
            response = client.post(
                '/api/profile/upload-avatar',
                headers={'Authorization': f'Bearer {token}'},
                content_type='multipart/form-data',
                data=data
            )
            assert response.status_code == 400
            assert response.json['error'] == 'Invalid file type. Allowed: png, jpg, jpeg, gif'

    def test_upload_avatar_no_extension(self, app, client):
        """Test upload fails with file without extension."""
        with app.app_context():
            token = create_access_token(identity="1")
            data = {'avatar': (BytesIO(b'test content'), 'noextension')}
            response = client.post(
                '/api/profile/upload-avatar',
                headers={'Authorization': f'Bearer {token}'},
                content_type='multipart/form-data',
                data=data
            )
            assert response.status_code == 400
            assert response.json['error'] == 'Invalid file type. Allowed: png, jpg, jpeg, gif'

    @patch('routes.profile.save_avatar')
    @patch('routes.profile.get_connection')
    def test_upload_avatar_success_student(self, mock_get_conn, mock_save_avatar, app, client):
        """Test successful avatar upload for student."""
        mock_save_avatar.return_value = 'uploads/avatar_1_abc123.jpg'
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'role': 'student'}
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_connection

        with app.app_context():
            token = create_access_token(identity="1")
            # Create a simple PNG image header
            png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
            data = {'avatar': (BytesIO(png_header), 'avatar.png')}
            response = client.post(
                '/api/profile/upload-avatar',
                headers={'Authorization': f'Bearer {token}'},
                content_type='multipart/form-data',
                data=data
            )
            assert response.status_code == 200
            assert response.json['success'] is True
            assert response.json['avatar'] == 'uploads/avatar_1_abc123.jpg'
            assert response.json['message'] == 'Avatar uploaded successfully'
            
            # Verify the correct SQL was executed for students
            mock_cursor.execute.assert_any_call(
                "UPDATE students SET avatar = %s WHERE user_id = %s",
                ('uploads/avatar_1_abc123.jpg', '1')
            )

    @patch('routes.profile.save_avatar')
    @patch('routes.profile.get_connection')
    def test_upload_avatar_success_admin(self, mock_get_conn, mock_save_avatar, app, client):
        """Test successful avatar upload for admin."""
        mock_save_avatar.return_value = 'uploads/avatar_1_abc123.jpg'
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'role': 'admin'}
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_connection

        with app.app_context():
            token = create_access_token(identity="1")
            data = {'avatar': (BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100), 'avatar.png')}
            response = client.post(
                '/api/profile/upload-avatar',
                headers={'Authorization': f'Bearer {token}'},
                content_type='multipart/form-data',
                data=data
            )
            assert response.status_code == 200
            assert response.json['success'] is True
            
            # Verify the correct SQL was executed for admins
            mock_cursor.execute.assert_any_call(
                "UPDATE user_details SET avatar = %s WHERE user_id = %s",
                ('uploads/avatar_1_abc123.jpg', '1')
            )

    @patch('routes.profile.save_avatar')
    @patch('routes.profile.get_connection')
    def test_upload_avatar_success_faculty(self, mock_get_conn, mock_save_avatar, app, client):
        """Test successful avatar upload for faculty."""
        mock_save_avatar.return_value = 'uploads/avatar_1_abc123.jpg'
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'role': 'faculty'}
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_connection

        with app.app_context():
            token = create_access_token(identity="1")
            data = {'avatar': (BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100), 'avatar.jpg')}
            response = client.post(
                '/api/profile/upload-avatar',
                headers={'Authorization': f'Bearer {token}'},
                content_type='multipart/form-data',
                data=data
            )
            assert response.status_code == 200
            
            # Verify the correct SQL was executed for faculty (uses user_details)
            mock_cursor.execute.assert_any_call(
                "UPDATE user_details SET avatar = %s WHERE user_id = %s",
                ('uploads/avatar_1_abc123.jpg', '1')
            )

    @patch('routes.profile.save_avatar')
    def test_upload_avatar_save_fails(self, mock_save_avatar, app, client):
        """Test upload fails when save_avatar returns None."""
        mock_save_avatar.return_value = None

        with app.app_context():
            token = create_access_token(identity="1")
            data = {'avatar': (BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100), 'avatar.png')}
            response = client.post(
                '/api/profile/upload-avatar',
                headers={'Authorization': f'Bearer {token}'},
                content_type='multipart/form-data',
                data=data
            )
            assert response.status_code == 500
            assert response.json['error'] == 'Failed to save avatar'

    @patch('routes.profile.save_avatar')
    @patch('routes.profile.get_connection')
    def test_upload_avatar_user_not_found(self, mock_get_conn, mock_save_avatar, app, client):
        """Test upload fails when user not found in database."""
        mock_save_avatar.return_value = 'uploads/avatar_1_abc123.jpg'
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # User not found
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_connection

        with app.app_context():
            token = create_access_token(identity="999")
            data = {'avatar': (BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100), 'avatar.png')}
            response = client.post(
                '/api/profile/upload-avatar',
                headers={'Authorization': f'Bearer {token}'},
                content_type='multipart/form-data',
                data=data
            )
            assert response.status_code == 404
            assert response.json['error'] == 'User not found'

    def test_upload_avatar_requires_auth(self, app, client):
        """Test upload fails without authentication."""
        data = {'avatar': (BytesIO(b'\x89PNG\r\n\x1a\n'), 'avatar.png')}
        response = client.post(
            '/api/profile/upload-avatar',
            content_type='multipart/form-data',
            data=data
        )
        assert response.status_code == 401

    def test_upload_avatar_accepts_jpeg(self, app, client):
        """Test upload accepts jpeg extension."""
        with app.app_context():
            token = create_access_token(identity="1")
            data = {'avatar': (BytesIO(b'\xff\xd8\xff\xe0'), 'avatar.jpeg')}
            with patch('routes.profile.save_avatar') as mock_save:
                with patch('routes.profile.get_connection') as mock_conn:
                    mock_save.return_value = 'uploads/avatar_1_abc.jpeg'
                    mock_cursor = MagicMock()
                    mock_cursor.fetchone.return_value = {'role': 'student'}
                    mock_conn.return_value.cursor.return_value = mock_cursor
                    
                    response = client.post(
                        '/api/profile/upload-avatar',
                        headers={'Authorization': f'Bearer {token}'},
                        content_type='multipart/form-data',
                        data=data
                    )
                    assert response.status_code == 200

    def test_upload_avatar_accepts_gif(self, app, client):
        """Test upload accepts gif extension."""
        with app.app_context():
            token = create_access_token(identity="1")
            data = {'avatar': (BytesIO(b'GIF89a'), 'avatar.gif')}
            with patch('routes.profile.save_avatar') as mock_save:
                with patch('routes.profile.get_connection') as mock_conn:
                    mock_save.return_value = 'uploads/avatar_1_abc.gif'
                    mock_cursor = MagicMock()
                    mock_cursor.fetchone.return_value = {'role': 'student'}
                    mock_conn.return_value.cursor.return_value = mock_cursor
                    
                    response = client.post(
                        '/api/profile/upload-avatar',
                        headers={'Authorization': f'Bearer {token}'},
                        content_type='multipart/form-data',
                        data=data
                    )
                    assert response.status_code == 200

    @patch('routes.profile.save_avatar')
    @patch('routes.profile.get_connection')
    def test_upload_avatar_db_exception(self, mock_get_conn, mock_save_avatar, app, client):
        """Test upload handles database exceptions gracefully."""
        mock_save_avatar.return_value = 'uploads/avatar_1_abc123.jpg'
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'role': 'student'}
        mock_cursor.execute.side_effect = [None, Exception('Database error')]
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_connection

        with app.app_context():
            token = create_access_token(identity="1")
            data = {'avatar': (BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100), 'avatar.png')}
            response = client.post(
                '/api/profile/upload-avatar',
                headers={'Authorization': f'Bearer {token}'},
                content_type='multipart/form-data',
                data=data
            )
            assert response.status_code == 500
            assert response.json['error'] == 'Failed to update avatar in database'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
