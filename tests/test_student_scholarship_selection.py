"""Tests for student scholarship selection and admin confirmation functionality."""

import pytest
from unittest.mock import patch, MagicMock, call
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
import json

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

# Mock external connections before importing modules
with patch('redis.Redis'):
    with patch('pymysql.connect'):
        from routes.evaluation import evaluations_bp


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = 'test-secret-key'
    app.config['TESTING'] = True
    JWTManager(app)
    app.register_blueprint(evaluations_bp)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def student_token(app):
    """Create a JWT token for a student."""
    with app.app_context():
        return create_access_token(identity=1, additional_claims={'role': 'student'})


@pytest.fixture
def admin_token(app):
    """Create a JWT token for an admin."""
    with app.app_context():
        return create_access_token(identity=100, additional_claims={'role': 'admin'})


class TestStudentSelectScholarship:
    """Test cases for student scholarship selection endpoint."""

    @patch('routes.evaluation.get_connection')
    @patch('routes.evaluation.notify_admin_student_selection')
    def test_student_select_scholarship_success(self, mock_notify, mock_get_connection, client, student_token):
        """Test successful student scholarship selection."""
        # Mock database cursor and connection
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        # Mock database responses
        # Application query
        mock_cursor.fetchone.side_effect = [
            {'id': 1, 'status': 'evaluated', 'student_id': 1, 'first_name': 'John', 'last_name': 'Doe'},  # Application
            {'id': 1},  # Recommendation check
            None,  # No existing selection
            {'name': 'Merit Scholarship', 'grant_amount': 5000.00}  # Scholarship details
        ]
        mock_cursor.lastrowid = 1
        
        response = client.post(
            '/api/evaluations/1/student-select-scholarship',
            headers={'Authorization': f'Bearer {student_token}'},
            json={
                'scholarship_id': 1,
                'selection_reason': 'This scholarship best fits my needs'
            }
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['status'] == 'student_selected'
        assert data['scholarship_name'] == 'Merit Scholarship'
        assert data['awarded_amount'] == 5000.00
        assert 'Awaiting admin confirmation' in data['message']
        
        # Verify notification was sent
        mock_notify.assert_called_once()

    @patch('routes.evaluation.get_connection')
    def test_student_select_scholarship_wrong_student(self, mock_get_connection, client, student_token):
        """Test student trying to select scholarship for another student's application."""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        # Application belongs to student_id 999, not 1
        mock_cursor.fetchone.return_value = {
            'id': 1, 'status': 'evaluated', 'student_id': 999, 
            'first_name': 'Jane', 'last_name': 'Smith'
        }
        
        response = client.post(
            '/api/evaluations/1/student-select-scholarship',
            headers={'Authorization': f'Bearer {student_token}'},
            json={'scholarship_id': 1}
        )
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert 'Unauthorized' in data['error']

    @patch('routes.evaluation.get_connection')
    def test_student_select_scholarship_not_evaluated(self, mock_get_connection, client, student_token):
        """Test student trying to select scholarship before application is evaluated."""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        # Application is pending, not evaluated
        mock_cursor.fetchone.return_value = {
            'id': 1, 'status': 'pending', 'student_id': 1,
            'first_name': 'John', 'last_name': 'Doe'
        }
        
        response = client.post(
            '/api/evaluations/1/student-select-scholarship',
            headers={'Authorization': f'Bearer {student_token}'},
            json={'scholarship_id': 1}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'evaluated' in data['error']

    @patch('routes.evaluation.get_connection')
    def test_student_select_scholarship_not_recommended(self, mock_get_connection, client, student_token):
        """Test student trying to select scholarship not in recommendations."""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.side_effect = [
            {'id': 1, 'status': 'evaluated', 'student_id': 1, 'first_name': 'John', 'last_name': 'Doe'},
            None  # No recommendation found
        ]
        
        response = client.post(
            '/api/evaluations/1/student-select-scholarship',
            headers={'Authorization': f'Bearer {student_token}'},
            json={'scholarship_id': 999}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'not in your recommendations' in data['error']

    @patch('routes.evaluation.get_connection')
    def test_student_select_scholarship_already_selected(self, mock_get_connection, client, student_token):
        """Test student trying to select when they already have a selection."""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.side_effect = [
            {'id': 1, 'status': 'evaluated', 'student_id': 1, 'first_name': 'John', 'last_name': 'Doe'},
            {'id': 1},  # Recommendation exists
            {'id': 1, 'status': 'student_selected'}  # Already selected
        ]
        
        response = client.post(
            '/api/evaluations/1/student-select-scholarship',
            headers={'Authorization': f'Bearer {student_token}'},
            json={'scholarship_id': 1}
        )
        
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'already made a selection' in data['error']


class TestAdminConfirmSelection:
    """Test cases for admin confirmation endpoint."""

    @patch('routes.evaluation.get_connection')
    @patch('routes.evaluation.notify_student_selection_confirmed')
    def test_admin_confirm_selection_success(self, mock_notify, mock_get_connection, client, admin_token):
        """Test successful admin confirmation of student selection."""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        # Mock pending student selection
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'scholarship_id': 1,
            'awarded_amount': 5000.00,
            'scholarship_name': 'Merit Scholarship',
            'student_id': 1
        }
        
        response = client.put(
            '/api/evaluations/1/confirm-selection',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={
                'action': 'confirm',
                'awarded_amount': 4500.00,
                'remarks': 'Approved with adjusted amount'
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'selected'
        assert data['awarded_amount'] == 4500.00
        assert 'confirmed successfully' in data['message']
        
        # Verify notification was sent
        mock_notify.assert_called_once_with(
            student_id=1,
            application_id=1,
            scholarship_name='Merit Scholarship',
            awarded_amount=4500.00,
            remarks='Approved with adjusted amount'
        )

    @patch('routes.evaluation.get_connection')
    @patch('routes.evaluation.notify_student_selection_rejected')
    def test_admin_reject_selection_success(self, mock_notify, mock_get_connection, client, admin_token):
        """Test successful admin rejection of student selection."""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        # Mock pending student selection
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'scholarship_id': 1,
            'awarded_amount': 5000.00,
            'scholarship_name': 'Merit Scholarship',
            'student_id': 1
        }
        
        response = client.put(
            '/api/evaluations/1/confirm-selection',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={
                'action': 'reject',
                'remarks': 'Does not meet requirements'
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'rejected'
        assert 'remains in evaluated status' in data['message']
        
        # Verify notification was sent
        mock_notify.assert_called_once_with(
            student_id=1,
            application_id=1,
            scholarship_name='Merit Scholarship',
            remarks='Does not meet requirements'
        )

    @patch('routes.evaluation.get_connection')
    def test_admin_confirm_no_pending_selection(self, mock_get_connection, client, admin_token):
        """Test admin confirmation when no pending selection exists."""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        # No pending selection
        mock_cursor.fetchone.return_value = None
        
        response = client.put(
            '/api/evaluations/1/confirm-selection',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={'action': 'confirm'}
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'No pending student selection' in data['error']

    def test_admin_confirm_invalid_action(self, client, admin_token):
        """Test admin confirmation with invalid action."""
        response = client.put(
            '/api/evaluations/1/confirm-selection',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={'action': 'invalid'}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'confirm' in data['error'] or 'reject' in data['error']


class TestGetSelection:
    """Test cases for get selection endpoint."""

    @patch('routes.evaluation.get_connection')
    def test_get_selection_with_student_selected(self, mock_get_connection, client, student_token):
        """Test getting selection with student_selected status."""
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        from datetime import datetime
        now = datetime.now()
        
        # Mock selection with student_selected status
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'scholarship_id': 1,
            'scholarship_name': 'Merit Scholarship',
            'selection_reason': 'Best fit',
            'status': 'student_selected',
            'awarded_amount': 5000.00,
            'created_at': now,
            'updated_at': now,
            'final_score': 85.5
        }
        
        response = client.get(
            '/api/evaluations/1/selection',
            headers={'Authorization': f'Bearer {student_token}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'student_selected'
        assert data['scholarship_name'] == 'Merit Scholarship'


class TestProfileScholarshipRecommendations:
    """Test cases for profile scholarship recommendations endpoint."""

    @patch('routes.profile.get_connection')
    def test_get_recommendations_success(self, mock_get_connection, client, student_token):
        """Test successful retrieval of recommendations."""
        from routes.profile import profile_bp
        
        # Create app with profile blueprint
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'test-secret-key'
        app.config['TESTING'] = True
        JWTManager(app)
        app.register_blueprint(profile_bp)
        test_client = app.test_client()
        
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        from datetime import datetime
        now = datetime.now()
        
        # Mock responses
        mock_cursor.fetchone.side_effect = [
            {'id': 1, 'status': 'evaluated', 'student_id': 1},  # Application
            None  # No selection
        ]
        
        # Mock recommendations
        mock_cursor.fetchall.return_value = [
            {
                'recommendation_id': 1,
                'scholarship_id': 1,
                'scholarship_name': 'Merit Scholarship',
                'description': 'For merit students',
                'grant_amount': 5000.00,
                'score': 95.0,
                'classification': 'Eligible',
                'eligibility_reasons': '{"gwa": "High GWA"}',
                'notes': 'Top recommendation',
                'created_at': now
            }
        ]
        
        response = test_client.get(
            '/api/profile/scholarship-recommendations/1',
            headers={'Authorization': f'Bearer {student_token}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['application_id'] == 1
        assert len(data['recommendations']) == 1
        assert data['recommendations'][0]['scholarship_name'] == 'Merit Scholarship'
        assert data['selection'] is None
