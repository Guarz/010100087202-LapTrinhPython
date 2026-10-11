# planner/forms.py
from django import forms
from .models import Task
from .models import RecurringSchedule
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class TaskForm(forms.ModelForm):
    deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}
        ),
        label="Hạn chót (Deadline)"
    )

    class Meta:
        model = Task
        fields = ['title', 'subject_name', 'deadline', 'estimated_minutes', 'priority', 'material_url']
        labels = {
            'title': 'Tên bài tập / Nhiệm vụ',
            'subject_name': 'Môn học',
            'estimated_minutes': 'Thời gian ước tính (phút)',
            'priority': 'Mức ưu tiên',
            'material_url': 'Link tài liệu ôn tập',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'VD: Làm bài tập lớn...'}),
            'subject_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'VD: Kiến trúc máy tính'}),
            'estimated_minutes': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'VD: 90'}),
            'priority': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'material_url': forms.URLInput(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'https://drive.google.com/...'}),
        }
class RecurringScheduleForm(forms.ModelForm):
    class Meta:
        model = RecurringSchedule
        fields = ['title', 'day_of_week', 'start_time', 'end_time', 'category']
        labels = {
            'title': 'Tên lịch bận / Môn học',
            'day_of_week': 'Thứ trong tuần',
            'start_time': 'Giờ bắt đầu (HH:MM)',
            'end_time': 'Giờ kết thúc (HH:MM)',
            'category': 'Phân loại',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'VD: Học Thể dục, Ca làm part-time...'}),
            'day_of_week': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'category': forms.Select(
                choices=[('school', 'Lịch học trường'), ('part_time', 'Ca làm thêm'), ('personal', 'Việc cá nhân')],
                attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}
            ),
        }
class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'sinhvien@gmail.com'})
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        labels = {
            'username': 'Tên đăng nhập',
            'email': 'Địa chỉ Email',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'nhap_ten_dang_nhap'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style cho 2 ô mật khẩu mặc định của Django
        self.fields['password1'].widget.attrs.update({'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'})
        self.fields['password2'].widget.attrs.update({'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'})