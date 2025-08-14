# progress_tracking.py
from django.db import models
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Avg, Count, Sum
from auth_service import User, auth_required
from course_management import Course, Lesson, Quiz, Enrollment, Question
import json
from datetime import datetime, timedelta

class LessonProgress(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='student_progress')
    is_completed = models.BooleanField(default=False)
    time_spent_minutes = models.IntegerField(default=0)
    completion_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_accessed = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'lesson']

    def __str__(self):
        return f"{self.student.username} - {self.lesson.title}"

class QuizAttempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    total_points = models.IntegerField(default=0)
    is_passed = models.BooleanField(default=False)
    time_taken_minutes = models.IntegerField(default=0)
    attempt_number = models.IntegerField(default=1)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title} (Attempt {self.attempt_number})"

class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.TextField()
    is_correct = models.BooleanField(default=False)
    points_earned = models.IntegerField(default=0)

class LearningPath(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learning_paths')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='learning_paths')
    current_lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, null=True, blank=True)
    estimated_completion_date = models.DateField(null=True, blank=True)
    daily_goal_minutes = models.IntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)

class StudySession(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_sessions')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='study_sessions')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, null=True, blank=True)
    duration_minutes = models.IntegerField()
    session_date = models.DateTimeField(auto_now_add=True)
    activities_completed = models.JSONField(default=dict)  # Store activities done in session

class ProgressTrackingService:
    """Service class for tracking student progress and analytics"""

    @staticmethod
    def start_lesson(student_id, lesson_id):
        """Start tracking lesson progress"""
        try:
            student = User.objects.get(id=student_id)
            lesson = Lesson.objects.get(id=lesson_id)
            
            progress, created = LessonProgress.objects.get_or_create(
                student=student,
                lesson=lesson,
                defaults={'started_at': datetime.now()}
            )
            
            return {
                "success": True,
                "message": "Lesson tracking started",
                "progress_id": progress.id
            }
        except (User.DoesNotExist, Lesson.DoesNotExist):
            return {"success": False, "message": "Student or lesson not found"}

    @staticmethod
    def update_lesson_progress(student_id, lesson_id, completion_percentage, time_spent=0):
        """Update lesson progress"""
        try:
            progress = LessonProgress.objects.get(student_id=student_id, lesson_id=lesson_id)
            progress.completion_percentage = completion_percentage
            progress.time_spent_minutes += time_spent
            progress.last_accessed = datetime.now()
            
            if completion_percentage >= 100:
                progress.is_completed = True
                progress.completed_at = datetime.now()
            
            progress.save()
            
            # Update course enrollment progress
            ProgressTrackingService.update_course_progress(student_id, progress.lesson.module.course.id)
            
            return {
                "success": True,
                "message": "Progress updated successfully"
            }
        except LessonProgress.DoesNotExist:
            return {"success": False, "message": "Progress record not found"}

    @staticmethod
    def update_course_progress(student_id, course_id):
        """Update overall course progress base
