# planner/forms.py
from django import forms
from .models import Course, RecurringSchedule, ScheduleBlock, Task
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class TaskForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].queryset = (
            Course.objects.filter(user=user)
            if user is not None
            else Course.objects.none()
        )

    deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}
        ),
        label="Hạn chót (Deadline)"
    )

    class Meta:
        model = Task
        fields = [
            'title',
            'course',
            'subject_name',
            'deadline',
            'estimated_minutes',
            'priority',
            'material_url',
            'material_file',
        ]
        labels = {
            'title': 'Tên bài tập / Nhiệm vụ',
            'course': 'Môn học (khóa học)',
            'subject_name': 'Môn học',
            'estimated_minutes': 'Thời gian ước tính (phút)',
            'priority': 'Mức ưu tiên',
            'material_url': 'Link tài liệu ôn tập (tùy chọn)',
            'material_file': 'Tải tài liệu lên (PDF, Word, PowerPoint, TXT; tối đa 10 MB)',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'VD: Làm bài tập lớn...'}),
            'course': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'subject_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'VD: Kiến trúc máy tính'}),
            'estimated_minutes': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'VD: 90'}),
            'priority': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'material_url': forms.URLInput(attrs={'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'https://drive.google.com/...'}),
            'material_file': forms.ClearableFileInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'accept': '.pdf,.doc,.docx,.ppt,.pptx,.txt',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        course = cleaned_data.get('course')
        if course and not cleaned_data.get('subject_name'):
            cleaned_data['subject_name'] = course.name
        return cleaned_data


class ScheduleBlockForm(forms.ModelForm):
    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            }
        ),
        label='Bắt đầu'
    )
    end_time = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            }
        ),
        label='Kết thúc'
    )

    class Meta:
        model = ScheduleBlock
        fields = ['title', 'task', 'start_time', 'end_time']
        labels = {
            'title': 'Tên sự kiện',
            'task': 'Nhiệm vụ liên quan',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'VD: Ôn tập chương 1',
            }),
            'task': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['task'].required = False
        self.fields['task'].queryset = (
            Task.objects.filter(user=user)
            if user is not None
            else Task.objects.none()
        )

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        if start_time and end_time and end_time <= start_time:
            self.add_error('end_time', 'Thời gian kết thúc phải sau thời gian bắt đầu.')
        return cleaned_data


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