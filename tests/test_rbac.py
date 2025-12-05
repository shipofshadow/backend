"""Tests for RBAC decorators and FACULTY role campus scope enforcement."""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

# Import the decorators
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.decorator import (
    admin_required,
    bitress_required,
    privilegedRoleRequired,
    faculty_required,
    admin_or_faculty_required,
    get_user_campus_scope,
    has_campus_access,
    campus_scope_required,
    enforce_faculty_campus_scope,
)
from models.user import (
    User,
    ROLE_ADMIN,
    ROLE_BITRESS,
    ROLE_FACULTY,
    ROLE_STUDENT,
    UNRESTRICTED_ROLES,
    ADMIN_ROLES
)


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = 'test-secret-key'
    app.config['TESTING'] = True
    JWTManager(app)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestRoleConstants:
    """Test role constants are properly defined."""
    
    def test_role_constants_exist(self):
        assert ROLE_ADMIN == "admin"
        assert ROLE_BITRESS == "bitress"
        assert ROLE_FACULTY == "faculty"
        assert ROLE_STUDENT == "student"
    
    def test_unrestricted_roles(self):
        assert ROLE_ADMIN in UNRESTRICTED_ROLES
        assert ROLE_BITRESS in UNRESTRICTED_ROLES
        assert ROLE_FACULTY not in UNRESTRICTED_ROLES
        assert ROLE_STUDENT not in UNRESTRICTED_ROLES
    
    def test_admin_roles(self):
        assert ROLE_ADMIN in ADMIN_ROLES
        assert ROLE_BITRESS in ADMIN_ROLES
        assert ROLE_FACULTY in ADMIN_ROLES
        assert ROLE_STUDENT not in ADMIN_ROLES


class TestUserModel:
    """Test User model campus-related methods."""
    
    def test_user_with_campus_id(self):
        user = User({
            "id": 1,
            "username": "faculty_user",
            "role": "faculty",
            "campus_id": 5,
            "is_active": 1
        })
        assert user.campus_id == 5
        assert user.role == "faculty"
    
    def test_user_is_unrestricted_admin(self):
        user = User({"id": 1, "role": "admin"})
        assert user.is_unrestricted() is True
    
    def test_user_is_unrestricted_bitress(self):
        user = User({"id": 1, "role": "bitress"})
        assert user.is_unrestricted() is True
    
    def test_user_is_not_unrestricted_faculty(self):
        user = User({"id": 1, "role": "faculty", "campus_id": 5})
        assert user.is_unrestricted() is False
    
    def test_user_is_not_unrestricted_student(self):
        user = User({"id": 1, "role": "student"})
        assert user.is_unrestricted() is False
    
    def test_user_is_faculty(self):
        user = User({"id": 1, "role": "faculty", "campus_id": 5})
        assert user.is_faculty() is True
    
    def test_user_is_not_faculty(self):
        user = User({"id": 1, "role": "admin"})
        assert user.is_faculty() is False
    
    def test_admin_has_campus_access_to_any(self):
        user = User({"id": 1, "role": "admin"})
        assert user.has_campus_access(1) is True
        assert user.has_campus_access(5) is True
        assert user.has_campus_access(99) is True
    
    def test_faculty_has_campus_access_to_own(self):
        user = User({"id": 1, "role": "faculty", "campus_id": 5})
        assert user.has_campus_access(5) is True
    
    def test_faculty_no_campus_access_to_other(self):
        user = User({"id": 1, "role": "faculty", "campus_id": 5})
        assert user.has_campus_access(1) is False
        assert user.has_campus_access(10) is False
    
    def test_faculty_no_campus_access_without_assignment(self):
        user = User({"id": 1, "role": "faculty", "campus_id": None})
        assert user.has_campus_access(5) is False
    
    def test_user_to_dict_includes_campus_id(self):
        user = User({
            "id": 1,
            "username": "faculty_user",
            "role": "faculty",
            "campus_id": 5,
            "is_active": 1
        })
        data = user.to_dict()
        assert "campus_id" in data
        assert data["campus_id"] == 5


class TestAdminRequiredDecorator:
    """Test admin_required decorator."""
    
    def test_admin_allowed(self, app):
        with app.app_context():
            @app.route('/test')
            @admin_required
            def protected():
                return "OK", 200
            
            with app.test_client() as client:
                token = create_access_token(
                    identity="1",
                    additional_claims={"role": "admin"}
                )
                response = client.get('/test', headers={
                    'Authorization': f'Bearer {token}'
                })
                assert response.status_code == 200
    
    def test_faculty_denied(self, app):
        with app.app_context():
            @app.route('/test2')
            @admin_required
            def protected():
                return "OK", 200
            
            with app.test_client() as client:
                token = create_access_token(
                    identity="1",
                    additional_claims={"role": "faculty", "campus_id": 5}
                )
                response = client.get('/test2', headers={
                    'Authorization': f'Bearer {token}'
                })
                assert response.status_code == 403


class TestAdminOrFacultyRequiredDecorator:
    """Test admin_or_faculty_required decorator."""
    
    def test_admin_allowed(self, app):
        with app.app_context():
            @app.route('/test3')
            @admin_or_faculty_required
            def protected():
                return "OK", 200
            
            with app.test_client() as client:
                token = create_access_token(
                    identity="1",
                    additional_claims={"role": "admin"}
                )
                response = client.get('/test3', headers={
                    'Authorization': f'Bearer {token}'
                })
                assert response.status_code == 200
    
    def test_bitress_allowed(self, app):
        with app.app_context():
            @app.route('/test4')
            @admin_or_faculty_required
            def protected():
                return "OK", 200
            
            with app.test_client() as client:
                token = create_access_token(
                    identity="1",
                    additional_claims={"role": "bitress"}
                )
                response = client.get('/test4', headers={
                    'Authorization': f'Bearer {token}'
                })
                assert response.status_code == 200
    
    def test_faculty_allowed(self, app):
        with app.app_context():
            @app.route('/test5')
            @admin_or_faculty_required
            def protected():
                return "OK", 200
            
            with app.test_client() as client:
                token = create_access_token(
                    identity="1",
                    additional_claims={"role": "faculty", "campus_id": 5}
                )
                response = client.get('/test5', headers={
                    'Authorization': f'Bearer {token}'
                })
                assert response.status_code == 200
    
    def test_student_denied(self, app):
        with app.app_context():
            @app.route('/test6')
            @admin_or_faculty_required
            def protected():
                return "OK", 200
            
            with app.test_client() as client:
                token = create_access_token(
                    identity="1",
                    additional_claims={"role": "student"}
                )
                response = client.get('/test6', headers={
                    'Authorization': f'Bearer {token}'
                })
                assert response.status_code == 403


class TestGetUserCampusScope:
    """Test get_user_campus_scope function."""
    
    def test_admin_unrestricted(self, app):
        with app.app_context():
            with app.test_request_context():
                token = create_access_token(
                    identity="1",
                    additional_claims={"role": "admin"}
                )
                from flask_jwt_extended import verify_jwt_in_request, get_jwt
                with app.test_client() as client:
                    client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {token}'
                    with app.test_request_context(headers={'Authorization': f'Bearer {token}'}):
                        verify_jwt_in_request()
                        is_unrestricted, campus_id = get_user_campus_scope()
                        assert is_unrestricted is True
                        assert campus_id is None
    
    def test_faculty_scoped(self, app):
        with app.app_context():
            token = create_access_token(
                identity="1",
                additional_claims={"role": "faculty", "campus_id": 5}
            )
            with app.test_request_context(headers={'Authorization': f'Bearer {token}'}):
                from flask_jwt_extended import verify_jwt_in_request
                verify_jwt_in_request()
                is_unrestricted, campus_id = get_user_campus_scope()
                assert is_unrestricted is False
                assert campus_id == 5


class TestHasCampusAccess:
    """Test has_campus_access function."""
    
    def test_admin_has_access_to_any_campus(self, app):
        with app.app_context():
            token = create_access_token(
                identity="1",
                additional_claims={"role": "admin"}
            )
            with app.test_request_context(headers={'Authorization': f'Bearer {token}'}):
                from flask_jwt_extended import verify_jwt_in_request
                verify_jwt_in_request()
                assert has_campus_access(1) is True
                assert has_campus_access(5) is True
                assert has_campus_access(99) is True
    
    def test_faculty_has_access_to_own_campus(self, app):
        with app.app_context():
            token = create_access_token(
                identity="1",
                additional_claims={"role": "faculty", "campus_id": 5}
            )
            with app.test_request_context(headers={'Authorization': f'Bearer {token}'}):
                from flask_jwt_extended import verify_jwt_in_request
                verify_jwt_in_request()
                assert has_campus_access(5) is True
    
    def test_faculty_no_access_to_other_campus(self, app):
        with app.app_context():
            token = create_access_token(
                identity="1",
                additional_claims={"role": "faculty", "campus_id": 5}
            )
            with app.test_request_context(headers={'Authorization': f'Bearer {token}'}):
                from flask_jwt_extended import verify_jwt_in_request
                verify_jwt_in_request()
                assert has_campus_access(1) is False
                assert has_campus_access(10) is False


class TestEnforceFacultyCampusScope:
    """Test enforce_faculty_campus_scope function."""
    
    def test_faculty_campus_enforced(self):
        claims = {"role": "faculty", "campus_id": 5}
        data = {"name": "Test", "campus_id": 10}
        
        result = enforce_faculty_campus_scope(data, claims)
        
        assert result["campus_id"] == 5
        assert result["name"] == "Test"
    
    def test_admin_campus_not_enforced(self):
        claims = {"role": "admin", "campus_id": None}
        data = {"name": "Test", "campus_id": 10}
        
        result = enforce_faculty_campus_scope(data, claims)
        
        assert result["campus_id"] == 10
        assert result["name"] == "Test"
    
    def test_faculty_without_campus_does_nothing(self):
        claims = {"role": "faculty", "campus_id": None}
        data = {"name": "Test", "campus_id": 10}
        
        result = enforce_faculty_campus_scope(data, claims)
        
        # Should not modify since faculty has no campus assignment
        assert result["campus_id"] == 10


class TestCampusScopeRequiredDecorator:
    """Test campus_scope_required decorator."""
    
    def test_admin_bypasses_scope_check(self, app):
        with app.app_context():
            @app.route('/campus/<int:campus_id>')
            @campus_scope_required('campus_id')
            def protected(campus_id):
                return "OK", 200
            
            with app.test_client() as client:
                token = create_access_token(
                    identity="1",
                    additional_claims={"role": "admin"}
                )
                response = client.get('/campus/99', headers={
                    'Authorization': f'Bearer {token}'
                })
                assert response.status_code == 200
    
    def test_faculty_allowed_own_campus(self, app):
        with app.app_context():
            @app.route('/campus2/<int:campus_id>')
            @campus_scope_required('campus_id')
            def protected(campus_id):
                return "OK", 200
            
            with app.test_client() as client:
                token = create_access_token(
                    identity="1",
                    additional_claims={"role": "faculty", "campus_id": 5}
                )
                response = client.get('/campus2/5', headers={
                    'Authorization': f'Bearer {token}'
                })
                assert response.status_code == 200
    
    def test_faculty_denied_other_campus(self, app):
        with app.app_context():
            @app.route('/campus3/<int:campus_id>')
            @campus_scope_required('campus_id')
            def protected(campus_id):
                return "OK", 200
            
            with app.test_client() as client:
                token = create_access_token(
                    identity="1",
                    additional_claims={"role": "faculty", "campus_id": 5}
                )
                response = client.get('/campus3/10', headers={
                    'Authorization': f'Bearer {token}'
                })
                assert response.status_code == 403
    
    def test_student_denied(self, app):
        with app.app_context():
            @app.route('/campus4/<int:campus_id>')
            @campus_scope_required('campus_id')
            def protected(campus_id):
                return "OK", 200
            
            with app.test_client() as client:
                token = create_access_token(
                    identity="1",
                    additional_claims={"role": "student"}
                )
                response = client.get('/campus4/5', headers={
                    'Authorization': f'Bearer {token}'
                })
                assert response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
