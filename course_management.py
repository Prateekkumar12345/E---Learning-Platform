# course_management.py
from django.db import models
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from auth_service import User, auth_required
import json
from datetime import datetime

class Course(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_taught')
    thumbnail = models.ImageField(upload_to='course_thumbnails/', blank=True, null=True)
    category = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    duration_hours = models.IntegerField(default=0)
    difficulty_level = models.CharField(max_length=20, choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced')
    ], default='beginner')
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField()
    order = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} - {self.title}"

class Lesson(models.Model):
    CONTENT_TYPE_CHOICES = [
        ('video', 'Video'),
        ('text', 'Text'),
        ('document', 'Document'),
        ('interactive', 'Interactive'),
    ]

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    video_url = models.URLField(blank=True, null=True)
    text_content = models.TextField(blank=True, null=True)
    document_file = models.FileField(upload_to='lesson_documents/', blank=True, null=True)
    duration_minutes = models.IntegerField(default=0)
    order = models.IntegerField()
    is_preview = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.module.title} - {self.title}"

class Quiz(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    description = models.TextField()
    passing_score = models.IntegerField(default=70)  # Percentage
    time_limit_minutes = models.IntegerField(default=30)
    attempts_allowed = models.IntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Question(models.Model):
    QUESTION_TYPE_CHOICES = [
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
    ]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    points = models.IntegerField(default=1)
    order = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.quiz.title} - Question {self.order}"

class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    answer_text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.IntegerField()

    class Meta:
        ordering = ['order']

class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ['student', 'course']

    def __str__(self):
        return f"{self.student.username} - {self.course.title}"

class CourseManagementService:
    """Service class for managing courses"""

    @staticmethod
    def create_course(instructor_id, title, description, category, **kwargs):
        """Create a new course"""
        try:
            instructor = User.objects.get(id=instructor_id, role__in=['instructor', 'admin'])
            course = Course.objects.create(
                title=title,
                description=description,
                instructor=instructor,
                category=category,
                price=kwargs.get('price', 0.00),
                duration_hours=kwargs.get('duration_hours', 0),
                difficulty_level=kwargs.get('difficulty_level', 'beginner')
            )
            return {
                "success": True,
                "message": "Course created successfully",
                "course_id": course.id
            }
        except User.DoesNotExist:
            return {"success": False, "message": "Instructor not found"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def add_module(course_id, title, description, order):
        """Add module to course"""
        try:
            course = Course.objects.get(id=course_id)
            module = Module.objects.create(
                course=course,
                title=title,
                description=description,
                order=order
            )
            return {
                "success": True,
                "message": "Module added successfully",
                "module_id": module.id
            }
        except Course.DoesNotExist:
            return {"success": False, "message": "Course not found"}

    @staticmethod
    def add_lesson(module_id, title, content_type, order, **kwargs):
        """Add lesson to module"""
        try:
            module = Module.objects.get(id=module_id)
            lesson = Lesson.objects.create(
                module=module,
                title=title,
                content_type=content_type,
                order=order,
                video_url=kwargs.get('video_url'),
                text_content=kwargs.get('text_content'),
                duration_minutes=kwargs.get('duration_minutes', 0),
                is_preview=kwargs.get('is_preview', False)
            )
            return {
                "success": True,
                "message": "Lesson added successfully",
                "lesson_id": lesson.id
            }
        except Module.DoesNotExist:
            return {"success": False, "message": "Module not found"}

    @staticmethod
    def create_quiz(lesson_id, title, description, **kwargs):
        """Create quiz for lesson"""
        try:
            lesson = Lesson.objects.get(id=lesson_id)
            quiz = Quiz.objects.create(
                lesson=lesson,
                title=title,
                description=description,
                passing_score=kwargs.get('passing_score', 70),
                time_limit_minutes=kwargs.get('time_limit_minutes', 30),
                attempts_allowed=kwargs.get('attempts_allowed', 3)
            )
            return {
                "success": True,
                "message": "Quiz created successfully",
                "quiz_id": quiz.id
            }
        except Lesson.DoesNotExist:
            return {"success": False, "message": "Lesson not found"}

    @staticmethod
    def add_question(quiz_id, question_text, question_type, points, order, answers=None):
        """Add question to quiz"""
        try:
            quiz = Quiz.objects.get(id=quiz_id)
            question = Question.objects.create(
                quiz=quiz,
                question_text=question_text,
                question_type=question_type,
                points=points,
                order=order
            )

            # Add answers if provided
            if answers:
                for idx, answer_data in enumerate(answers):
                    Answer.objects.create(
                        question=question,
                        answer_text=answer_data['text'],
                        is_correct=answer_data.get('is_correct', False),
                        order=idx + 1
                    )

            return {
                "success": True,
                "message": "Question added successfully",
                "question_id": question.id
            }
        except Quiz.DoesNotExist:
            return {"success": False, "message": "Quiz not found"}

    @staticmethod
    def enroll_student(student_id, course_id):
        """Enroll student in course"""
        try:
            student = User.objects.get(id=student_id, role='student')
            course = Course.objects.get(id=course_id, is_published=True)
            
            enrollment, created = Enrollment.objects.get_or_create(
                student=student,
                course=course
            )
            
            if created:
                return {
                    "success": True,
                    "message": "Student enrolled successfully"
                }
            else:
                return {
                    "success": False,
                    "message": "Student already enrolled"
                }
        except User.DoesNotExist:
            return {"success": False, "message": "Student not found"}
        except Course.DoesNotExist:
            return {"success": False, "message": "Course not found or not published"}

    @staticmethod
    def get_course_content(course_id, user_id=None):
        """Get course content structure"""
        try:
            course = Course.objects.get(id=course_id)
            modules = []
            
            for module in course.modules.all():
                lessons = []
                for lesson in module.lessons.all():
                    lesson_data = {
                        "id": lesson.id,
                        "title": lesson.title,
                        "content_type": lesson.content_type,
                        "duration_minutes": lesson.duration_minutes,
                        "is_preview": lesson.is_preview
                    }
                    
                    # Include content if user is enrolled or lesson is preview
                    if user_id and (lesson.is_preview or 
                                   Enrollment.objects.filter(student_id=user_id, course=course).exists()):
                        lesson_data.update({
                            "video_url": lesson.video_url,
                            "text_content": lesson.text_content,
                        })
                    
                    lessons.append(lesson_data)
                
                modules.append({
                    "id": module.id,
                    "title": module.title,
                    "description": module.description,
                    "lessons": lessons
                })
            
            return {
                "success": True,
                "course": {
                    "id": course.id,
                    "title": course.title,
                    "description": course.description,
                    "instructor": course.instructor.username,
                    "category": course.category,
                    "difficulty_level": course.difficulty_level,
                    "modules": modules
                }
            }
        except Course.DoesNotExist:
            return {"success": False, "message": "Course not found"}

    @staticmethod
    def get_user_courses(user_id, role):
        """Get courses based on user role"""
        try:
            user = User.objects.get(id=user_id)
            
            if role == 'instructor':
                courses = Course.objects.filter(instructor=user)
                course_list = [{
                    "id": course.id,
                    "title": course.title,
                    "description": course.description,
                    "category": course.category,
                    "is_published": course.is_published,
                    "enrollments_count": course.enrollments.count(),
                    "created_at": course.created_at.strftime("%Y-%m-%d")
                } for course in courses]
            
            elif role == 'student':
                enrollments = Enrollment.objects.filter(student=user)
                course_list = [{
                    "id": enrollment.course.id,
                    "title": enrollment.course.title,
                    "description": enrollment.course.description,
                    "instructor": enrollment.course.instructor.username,
                    "progress_percentage": float(enrollment.progress_percentage),
                    "enrolled_at": enrollment.enrolled_at.strftime("%Y-%m-%d")
                } for enrollment in enrollments]
            
            else:  # admin
                courses = Course.objects.all()
                course_list = [{
                    "id": course.id,
                    "title": course.title,
                    "instructor": course.instructor.username,
                    "category": course.category,
                    "enrollments_count": course.enrollments.count(),
                    "is_published": course.is_published
                } for course in courses]
            
            return {
                "success": True,
                "courses": course_list
            }
        except User.DoesNotExist:
            return {"success": False, "message": "User not found"}

# Django Views
@csrf_exempt
@auth_required('create_course')
def create_course_view(request):
    """API endpoint to create course"""
    if request.method == 'POST':
        data = json.loads(request.body)
        result = CourseManagementService.create_course(
            instructor_id=request.user_info['id'],
            title=data.get('title'),
            description=data.get('description'),
            category=data.get('category'),
            price=data.get('price', 0.00),
            difficulty_level=data.get('difficulty_level', 'beginner')
        )
        return JsonResponse(result)

@csrf_exempt
@auth_required()
def enroll_course_view(request, course_id):
    """API endpoint to enroll in course"""
    if request.method == 'POST':
        result = CourseManagementService.enroll_student(
            student_id=request.user_info['id'],
            course_id=course_id
        )
        return JsonResponse(result)

@auth_required()
def get_course_content_view(request, course_id):
    """API endpoint to get course content"""
    result = CourseManagementService.get_course_content(
        course_id=course_id,
        user_id=request.user_info['id']
    )
    return JsonResponse(result)

@auth_required()
def get_user_courses_view(request):
    """API endpoint to get user's courses"""
    result = CourseManagementService.get_user_courses(
        user_id=request.user_info['id'],
        role=request.user_info['role']
    )
    return JsonResponse(result)
