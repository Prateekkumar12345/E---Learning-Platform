# auth_service.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password, check_password
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import jwt
from datetime import datetime, timedelta
from django.conf import settings

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('instructor', 'Instructor'),
        ('student', 'Student'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.role})"

class AuthService:
    """Service class for handling authentication operations"""
    
    @staticmethod
    def register_user(username, email, password, role='student', **kwargs):
        """Register a new user"""
        try:
            if User.objects.filter(username=username).exists():
                return {"success": False, "message": "Username already exists"}
            
            if User.objects.filter(email=email).exists():
                return {"success": False, "message": "Email already registered"}
            
            user = User.objects.create(
                username=username,
                email=email,
                password=make_password(password),
                role=role,
                first_name=kwargs.get('first_name', ''),
                last_name=kwargs.get('last_name', ''),
                phone_number=kwargs.get('phone_number', '')
            )
            
            return {
                "success": True,
                "message": "User registered successfully",
                "user_id": user.id,
                "username": user.username,
                "role": user.role
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def login_user(username, password):
        """Authenticate user login"""
        try:
            user = User.objects.get(username=username)
            if check_password(password, user.password):
                # Generate JWT token
                payload = {
                    'user_id': user.id,
                    'username': user.username,
                    'role': user.role,
                    'exp': datetime.utcnow() + timedelta(hours=24)
                }
                token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
                
                return {
                    "success": True,
                    "message": "Login successful",
                    "token": token,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role,
                        "first_name": user.first_name,
                        "last_name": user.last_name
                    }
                }
            else:
                return {"success": False, "message": "Invalid password"}
        except User.DoesNotExist:
            return {"success": False, "message": "User not found"}
    
    @staticmethod
    def verify_token(token):
        """Verify JWT token and return user info"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user = User.objects.get(id=payload['user_id'])
            return {
                "success": True,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "email": user.email
                }
            }
        except jwt.ExpiredSignatureError:
            return {"success": False, "message": "Token expired"}
        except jwt.InvalidTokenError:
            return {"success": False, "message": "Invalid token"}
        except User.DoesNotExist:
            return {"success": False, "message": "User not found"}
    
    @staticmethod
    def change_password(user_id, old_password, new_password):
        """Change user password"""
        try:
            user = User.objects.get(id=user_id)
            if check_password(old_password, user.password):
                user.password = make_password(new_password)
                user.save()
                return {"success": True, "message": "Password changed successfully"}
            else:
                return {"success": False, "message": "Current password is incorrect"}
        except User.DoesNotExist:
            return {"success": False, "message": "User not found"}
    
    @staticmethod
    def update_profile(user_id, **kwargs):
        """Update user profile"""
        try:
            user = User.objects.get(id=user_id)
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            user.save()
            return {"success": True, "message": "Profile updated successfully"}
        except User.DoesNotExist:
            return {"success": False, "message": "User not found"}

class RoleBasedAccessControl:
    """Class for managing role-based access control"""
    
    PERMISSIONS = {
        'admin': [
            'create_course', 'edit_course', 'delete_course',
            'manage_users', 'view_analytics', 'manage_system'
        ],
        'instructor': [
            'create_course', 'edit_own_course', 'view_course_analytics',
            'manage_students', 'create_quiz', 'grade_quiz'
        ],
        'student': [
            'view_course', 'take_quiz', 'view_progress',
            'join_video_conference'
        ]
    }
    
    @classmethod
    def check_permission(cls, user_role, permission):
        """Check if user role has specific permission"""
        return permission in cls.PERMISSIONS.get(user_role, [])
    
    @classmethod
    def get_user_permissions(cls, user_role):
        """Get all permissions for a user role"""
        return cls.PERMISSIONS.get(user_role, [])

# Django Views for API endpoints
@csrf_exempt
def register_view(request):
    """API endpoint for user registration"""
    if request.method == 'POST':
        data = json.loads(request.body)
        result = AuthService.register_user(
            username=data.get('username'),
            email=data.get('email'),
            password=data.get('password'),
            role=data.get('role', 'student'),
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            phone_number=data.get('phone_number', '')
        )
        return JsonResponse(result)

@csrf_exempt
def login_view(request):
    """API endpoint for user login"""
    if request.method == 'POST':
        data = json.loads(request.body)
        result = AuthService.login_user(
            username=data.get('username'),
            password=data.get('password')
        )
        return JsonResponse(result)

@csrf_exempt
def verify_token_view(request):
    """API endpoint for token verification"""
    if request.method == 'POST':
        data = json.loads(request.body)
        result = AuthService.verify_token(data.get('token'))
        return JsonResponse(result)

def logout_view(request):
    """API endpoint for user logout"""
    logout(request)
    return JsonResponse({"success": True, "message": "Logged out successfully"})

# Decorator for checking authentication
def auth_required(permission=None):
    """Decorator to check authentication and permissions"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return JsonResponse({"success": False, "message": "Authentication required"}, status=401)
            
            token = auth_header.split(' ')[1]
            auth_result = AuthService.verify_token(token)
            
            if not auth_result['success']:
                return JsonResponse(auth_result, status=401)
            
            user = auth_result['user']
            
            # Check permission if specified
            if permission and not RoleBasedAccessControl.check_permission(user['role'], permission):
                return JsonResponse({"success": False, "message": "Permission denied"}, status=403)
            
            request.user_info = user
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
