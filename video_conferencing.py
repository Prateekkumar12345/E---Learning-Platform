# video_conferencing.py
from django.db import models
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from auth_service import User, auth_required
from course_management import Course
import json
import uuid
from datetime import datetime, timedelta
import requests
from django.conf import settings

class VideoConferenceRoom(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('cancelled', 'Cancelled'),
    ]

    room_id = models.UUIDField(default=uuid.uuid4, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_conferences')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='conferences', null=True, blank=True)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    max_participants = models.IntegerField(default=100)
    is_recorded = models.BooleanField(default=False)
    recording_url = models.URLField(blank=True, null=True)
    meeting_url = models.URLField(blank=True)
    meeting_password = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.scheduled_start.strftime('%Y-%m-%d %H:%M')}"

class ConferenceParticipant(models.Model):
    ROLE_CHOICES = [
        ('host', 'Host'),
        ('presenter', 'Presenter'),
        ('participant', 'Participant'),
    ]

    conference = models.ForeignKey(VideoConferenceRoom, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conference_participations')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='participant')
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(default=0)
    is_invited = models.BooleanField(default=True)
    invitation_sent = models.BooleanField(default=False)

    class Meta:
        unique_together = ['conference', 'user']

    def __str__(self):
        return f"{self.user.username} in {self.conference.title}"

class ConferenceRecording(models.Model):
    conference = models.ForeignKey(VideoConferenceRoom, on_delete=models.CASCADE, related_name='recordings')
    recording_id = models.CharField(max_length=100, unique=True)
    file_url = models.URLField()
    file_size_mb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_minutes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=False)
    download_count = models.IntegerField(default=0)

class ChatMessage(models.Model):
    conference = models.ForeignKey(VideoConferenceRoom, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_private = models.BooleanField(default=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_messages', null=True, blank=True)

class VideoConferencingService:
    """Service class for managing video conferencing functionality"""

    @staticmethod
    def create_conference_room(host_id, title, scheduled_start, scheduled_end, **kwargs):
        """Create a new video conference room"""
        try:
            host = User.objects.get(id=host_id, role__in=['instructor', 'admin'])
            
            # Generate meeting URL and password (In real implementation, integrate with Zoom/WebRTC)
            meeting_url = f"https://meet.example.com/room/{uuid.uuid4()}"
            meeting_password = str(uuid.uuid4())[:8]
            
            room = VideoConferenceRoom.objects.create(
                title=title,
                description=kwargs.get('description', ''),
                host=host,
                course_id=kwargs.get('course_id'),
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                max_participants=kwargs.get('max_participants', 100),
                is_recorded=kwargs.get('is_recorded', False),
                meeting_url=meeting_url,
                meeting_password=meeting_password
            )
            
            # Add host as participant
            ConferenceParticipant.objects.create(
                conference=room,
                user=host,
                role='host'
            )
            
            return {
                "success": True,
                "message": "Conference room created successfully",
                "room_id": str(room.room_id),
                "meeting_url": room.meeting_url,
                "meeting_password": room.meeting_password
            }
        except User.DoesNotExist:
            return {"success": False, "message": "Host not found or not authorized"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def add_participant(room_id, user_id, role='participant'):
        """Add participant to conference room"""
        try:
            room = VideoConferenceRoom.objects.get(room_id=room_id)
            user = User.objects.get(id=user_id)
            
            # Check if room has capacity
            current_participants = room.participants.count()
            if current_participants >= room.max_participants:
                return {"success": False, "message": "Room is at maximum capacity"}
            
            participant, created = ConferenceParticipant.objects.get_or_create(
                conference=room,
                user=user,
                defaults={'role': role}
            )
            
            if not created:
                participant.role = role
                participant.save()
            
            return {
                "success": True,
                "message": "Participant added successfully" if created else "Participant updated"
            }
        except (VideoConferenceRoom.DoesNotExist, User.DoesNotExist):
            return {"success": False, "message": "Room or user not found"}

    @staticmethod
    def start_conference(room_id, host_id):
        """Start a conference room"""
        try:
            room = VideoConferenceRoom.objects.get(room_id=room_id, host_id=host_id)
            
            if room.status != 'scheduled':
                return {"success": False, "message": "Conference cannot be started"}
            
            room.status = 'active'
            room.actual_start = datetime.now()
            room.save()
            
            # In real implementation, call video service API to start room
            # VideoConferencingService._call_video_service_api('start_room', room_id)
            
            return {
                "success": True,
                "message": "Conference started successfully",
                "meeting_url": room.meeting_url
            }
        except VideoConferenceRoom.DoesNotExist:
            return {"success": False, "message": "Room not found or not authorized"}

    @staticmethod
    def end_conference(room_id, host_id):
        """End a conference room"""
        try:
            room = VideoConferenceRoom.objects.get(room_id=room_id, host_id=host_id)
            
            if room.status != 'active':
                return {"success": False, "message": "Conference is not active"}
            
            room.status = 'ended'
            room.actual_end = datetime.now()
            room.save()
            
            # Update all active participants
            active_participants = room.participants.filter(joined_at__isnull=False, left_at__isnull=True)
            for participant in active_participants:
                participant.left_at = datetime.now()
                if participant.joined_at:
                    duration = (participant.left_at - participant.joined_at).total_seconds() / 60
                    participant.duration_minutes = int(duration)
                participant.save()
            
            # In real implementation, call video service API to end room and get recording
            # recording_data = VideoConferencingService._call_video_service_api('end_room', room_id)
            
            return {
                "success": True,
                "message": "Conference ended successfully",
                "duration_minutes": int((room.actual_end - room.actual_start).total_seconds() / 60)
            }
        except VideoConferenceRoom.DoesNotExist:
            return {"success": False, "message": "Room not found or not authorized"}

    @staticmethod
    def join_conference(room_id, user_id):
        """Join a conference room"""
        try:
            room = VideoConferenceRoom.objects.get(room_id=room_id)
            participant = ConferenceParticipant.objects.get(conference=room, user_id=user_id)
            
            if room.status != 'active':
                return {"success": False, "message": "Conference is not active"}
            
            participant.joined_at = datetime.now()
            participant.save()
            
            return {
                "success": True,
                "message": "Joined conference successfully",
                "meeting_url": room.meeting_url,
                "meeting_password": room.meeting_password
            }
        except VideoConferenceRoom.DoesNotExist:
            return {"success": False, "message": "Room not found"}
        except ConferenceParticipant.DoesNotExist:
            return {"success": False, "message": "Not invited to this conference"}

    @staticmethod
    def leave_conference(room_id, user_id):
        """Leave a conference room"""
        try:
            room = VideoConferenceRoom.objects.get(room_id=room_id)
            participant = ConferenceParticipant.objects.get(conference=room, user_id=user_id)
            
            participant.left_at = datetime.now()
            if participant.joined_at:
                duration = (participant.left_at - participant.joined_at).total_seconds() / 60
                participant.duration_minutes = int(duration)
            participant.save()
            
            return {
                "success": True,
                "message": "Left conference successfully",
                "duration_minutes": participant.duration_minutes
            }
        except (VideoConferenceRoom.DoesNotExist, ConferenceParticipant.DoesNotExist):
            return {"success": False, "message": "Room or participation not found"}

    @staticmethod
    def get_conference_details(room_id, user_id):
        """Get conference room details"""
        try:
            room = VideoConferenceRoom.objects.get(room_id=room_id)
            
            # Check if user is participant or has access
            try:
                participant = ConferenceParticipant.objects.get(conference=room, user_id=user_id)
                has_access = True
            except ConferenceParticipant.DoesNotExist:
                # Check if user is enrolled in course
                if room.course:
                    from course_management import Enrollment
                    has_access = Enrollment.objects.filter(
                        student_id=user_id, 
                        course=room.course
                    ).exists()
