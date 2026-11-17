# planner/forms.py
from django import forms
from .models import Course, RecurringSchedule, ScheduleBlock, Task, UserProfile
from django.contrib.auth.models import User
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth.password_validation import validate_password

class TaskForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].queryset = (
            Course.objects.filter(user=user)
            if user is not None
            else Course.objects.none()
        )
        self.fields['course'].empty_label = '— Không gắn môn —'

    deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'field'}
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
            'title': forms.TextInput(attrs={'class': 'field', 'placeholder': 'VD: Làm bài tập lớn...'}),
            'course': forms.Select(attrs={'class': 'field'}),
            'subject_name': forms.TextInput(attrs={'class': 'field', 'placeholder': 'VD: Kiến trúc máy tính'}),
            'estimated_minutes': forms.NumberInput(attrs={'class': 'field', 'placeholder': 'VD: 90'}),
            'priority': forms.Select(attrs={'class': 'field'}),
            'material_url': forms.URLInput(attrs={'class': 'field', 'placeholder': 'https://drive.google.com/...'}),
            'material_file': forms.ClearableFileInput(attrs={
                'class': 'field',
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
                'class': 'field',
            }
        ),
        label='Bắt đầu'
    )
    end_time = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'field',
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
                'class': 'field',
                'placeholder': 'VD: Ôn tập chương 1',
            }),
            'task': forms.Select(attrs={
                'class': 'field',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['task'].required = False
        self.fields['task'].empty_label = '— Không gắn nhiệm vụ —'
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
            'title': forms.TextInput(attrs={'class': 'field', 'placeholder': 'VD: Học Thể dục, Ca làm part-time...'}),
            'day_of_week': forms.Select(attrs={'class': 'field'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'field'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'field'}),
            'category': forms.Select(
                choices=[('school', 'Lịch học trường'), ('part_time', 'Ca làm thêm'), ('personal', 'Việc cá nhân')],
                attrs={'class': 'field'}
            ),
        }
class RegisterForm(forms.ModelForm):
    """Đăng ký với 3 trường: email, tên đăng nhập, mật khẩu.

    Một email được dùng cho nhiều tài khoản; tên đăng nhập là duy nhất
    và không đổi được sau khi tạo.
    """
    password = forms.CharField(
        label='Mật khẩu',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'field', 'autocomplete': 'new-password'}),
        help_text='Ít nhất 8 ký tự, không quá giống tên đăng nhập, không chỉ gồm số.',
    )

    class Meta:
        model = User
        fields = ['email', 'username']
        labels = {
            'email': 'Email',
            'username': 'Tên đăng nhập',
        }
        help_texts = {
            'username': 'Dùng để đăng nhập, không thể đổi sau này. Chỉ gồm chữ, số và @ . + - _',
        }
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'field', 'placeholder': 'sinhvien@gmail.com', 'autocomplete': 'email'}),
            'username': forms.TextInput(attrs={'class': 'field', 'placeholder': 'nhap_ten_dang_nhap', 'autocomplete': 'username', 'autocapitalize': 'none'}),
        }
        error_messages = {
            'username': {'unique': 'Tên đăng nhập này đã có người dùng.'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def _post_clean(self):
        super()._post_clean()
        # Kiểm tra độ mạnh mật khẩu với thông tin của chính tài khoản đang tạo
        password = self.cleaned_data.get('password')
        if password:
            try:
                validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error('password', error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Đăng nhập bằng tên đăng nhập + mật khẩu; chặn tài khoản chưa xác thực email."""

    error_messages = {
        'invalid_login': 'Tên đăng nhập hoặc mật khẩu không chính xác.',
        'inactive': 'Tài khoản này đã bị khóa.',
        'unverified': 'Bạn cần xác thực email trước khi đăng nhập. Hãy mở link trong email chúng tôi đã gửi.',
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        from .accounts import is_email_verified
        if not is_email_verified(user):
            raise forms.ValidationError(self.error_messages['unverified'], code='unverified')


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['code', 'name', 'description']
        labels = {
            'code': 'Mã môn',
            'name': 'Tên môn học',
            'description': 'Ghi chú',
        }
        widgets = {
            'code': forms.TextInput(attrs={'class': 'field', 'placeholder': 'VD: PY101'}),
            'name': forms.TextInput(attrs={'class': 'field', 'placeholder': 'VD: Lập trình Python'}),
            'description': forms.Textarea(attrs={'class': 'field', 'rows': 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        if self.user and Course.objects.filter(user=self.user, code=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Bạn đã có môn với mã này.')
        return code


class StudyHoursForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['sleep_hours', 'preferred_study_hours']
        labels = {
            'sleep_hours': 'Giờ ngủ (HH:MM-HH:MM)',
            'preferred_study_hours': 'Khung giờ học ưa thích',
        }
        widgets = {
            'sleep_hours': forms.TextInput(attrs={'class': 'field', 'placeholder': '23:00-06:00'}),
            'preferred_study_hours': forms.TextInput(attrs={'class': 'field', 'placeholder': '19:00-22:00'}),
        }

    def _clean_range(self, name):
        value = self.cleaned_data[name].replace(' ', '')
        try:
            start, end = value.split('-')
            for part in (start, end):
                hour, minute = part.split(':')
                if not (0 <= int(hour) < 24 and 0 <= int(minute) < 60):
                    raise ValueError
        except ValueError:
            raise forms.ValidationError('Định dạng đúng: HH:MM-HH:MM')
        return value

    def clean_sleep_hours(self):
        return self._clean_range('sleep_hours')

    def clean_preferred_study_hours(self):
        return self._clean_range('preferred_study_hours')


class IcsImportForm(forms.Form):
    ics_file = forms.FileField(
        label='Tệp lịch .ics',
        widget=forms.ClearableFileInput(attrs={'class': 'field', 'accept': '.ics,text/calendar'}),
    )

    def clean_ics_file(self):
        uploaded = self.cleaned_data['ics_file']
        if not uploaded.name.lower().endswith('.ics'):
            raise forms.ValidationError('Chỉ nhận tệp .ics.')
        if uploaded.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Tệp .ics không được vượt quá 2 MB.')
        return uploaded


class ProfileForm(forms.ModelForm):
    """Người dùng tự cập nhật thông tin cá nhân."""

    class Meta:
        model = User
        fields = ['last_name', 'first_name', 'email']
        labels = {
            'last_name': 'Họ',
            'first_name': 'Tên',
            'email': 'Email',
        }
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'field', 'autocomplete': 'family-name'}),
            'first_name': forms.TextInput(attrs={'class': 'field', 'autocomplete': 'given-name'}),
            'email': forms.EmailInput(attrs={'class': 'field', 'autocomplete': 'email'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True

    def clean_email(self):
        # Một email có thể dùng cho nhiều tài khoản nên không kiểm tra trùng
        return self.cleaned_data['email'].strip().lower()


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            'old_password': 'Mật khẩu hiện tại',
            'new_password1': 'Mật khẩu mới',
            'new_password2': 'Nhập lại mật khẩu mới',
        }
        for name, field in self.fields.items():
            field.label = labels[name]
            field.widget.attrs.update({'class': 'field'})
        self.fields['old_password'].widget.attrs.pop('autofocus', None)


class StyledPasswordResetForm(PasswordResetForm):
    """Gửi link đặt lại mật khẩu cho MỌI tài khoản đang dùng email này."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Email đã đăng ký'
        self.fields['email'].widget.attrs.update({'class': 'field', 'placeholder': 'sinhvien@gmail.com'})


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Mật khẩu mới'
        self.fields['new_password2'].label = 'Nhập lại mật khẩu mới'
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'field'})
        self.fields['new_password1'].help_text = 'Ít nhất 8 ký tự, không quá giống tên đăng nhập, không chỉ gồm số.'
