# planner/themes.py
"""
BỘ MÀU GIAO DIỆN

Mỗi theme gồm thang màu chủ đạo `brand` (50-900) và màu nhấn `accent`
(dùng cho gradient). base.html khai báo Tailwind `brand-*` / `accent-*`
bằng biến CSS (--brand-600: "79 70 229"), nên đổi theme chỉ cần đổi biến,
không phải sửa template.

Quy ước tương phản (WCAG AA, nền trắng):
- brand-600: nền nút chính có chữ trắng và màu chữ link -> >= 4.5:1.
- brand-700 trên brand-50: mục menu đang chọn -> >= 4.5:1.
Với màu sáng (xanh ngọc, cam) thang được dịch đậm hơn 1 bậc để đạt chuẩn.
"""

THEMES = {
    'indigo': {
        'label': 'Chàm',
        'description': 'Mặc định, tập trung và chuyên nghiệp',
        'brand': {
            50: '#eef2ff', 100: '#e0e7ff', 200: '#c7d2fe', 300: '#a5b4fc', 400: '#818cf8',
            500: '#6366f1', 600: '#4f46e5', 700: '#4338ca', 800: '#3730a3', 900: '#312e81',
        },
        'accent': {100: '#ede9fe', 500: '#8b5cf6', 600: '#7c3aed', 700: '#6d28d9', 800: '#5b21b6'},
    },
    'violet': {
        'label': 'Tím học tập',
        'description': 'Sáng tạo, gợi cảm hứng ghi nhớ',
        'brand': {
            50: '#f5f3ff', 100: '#ede9fe', 200: '#ddd6fe', 300: '#c4b5fd', 400: '#a78bfa',
            500: '#8b5cf6', 600: '#7c3aed', 700: '#6d28d9', 800: '#5b21b6', 900: '#4c1d95',
        },
        'accent': {100: '#fae8ff', 500: '#d946ef', 600: '#c026d3', 700: '#a21caf', 800: '#86198f'},
    },
    'teal': {
        'label': 'Xanh ngọc',
        'description': 'Dịu mắt, phù hợp học lâu',
        'brand': {
            50: '#f0fdfa', 100: '#ccfbf1', 200: '#99f6e4', 300: '#5eead4', 400: '#2dd4bf',
            500: '#14b8a6', 600: '#0f766e', 700: '#115e59', 800: '#134e4a', 900: '#042f2e',
        },
        'accent': {100: '#cffafe', 500: '#06b6d4', 600: '#0891b2', 700: '#0e7490', 800: '#155e75'},
    },
    'blue': {
        'label': 'Xanh dương',
        'description': 'Tin cậy, rõ ràng như lịch truyền thống',
        'brand': {
            50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd', 400: '#60a5fa',
            500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a',
        },
        'accent': {100: '#e0f2fe', 500: '#0ea5e9', 600: '#0284c7', 700: '#0369a1', 800: '#075985'},
    },
    'orange': {
        'label': 'Cam năng lượng',
        'description': 'Ấm áp, tạo động lực bắt đầu',
        'brand': {
            50: '#fff7ed', 100: '#ffedd5', 200: '#fed7aa', 300: '#fdba74', 400: '#fb923c',
            500: '#f97316', 600: '#c2410c', 700: '#9a3412', 800: '#7c2d12', 900: '#431407',
        },
        'accent': {100: '#fef3c7', 500: '#f59e0b', 600: '#d97706', 700: '#b45309', 800: '#92400e'},
    },
}

DEFAULT_THEME = 'indigo'
THEME_CHOICES = [(key, theme['label']) for key, theme in THEMES.items()]


def get_theme(key):
    return THEMES.get(key) or THEMES[DEFAULT_THEME]


def _channels(hex_color):
    hex_color = hex_color.lstrip('#')
    return ' '.join(str(int(hex_color[i:i + 2], 16)) for i in (0, 2, 4))


def theme_css_variables(key):
    """Chuỗi khai báo biến CSS cho :root, VD '--brand-600: 79 70 229;'."""
    theme = get_theme(key)
    parts = [f'--brand-{shade}: {_channels(color)};' for shade, color in theme['brand'].items()]
    parts += [f'--accent-{shade}: {_channels(color)};' for shade, color in theme['accent'].items()]
    return ' '.join(parts)


def contrast_ratio(foreground, background):
    """Tỉ lệ tương phản WCAG giữa 2 màu hex."""
    def luminance(hex_color):
        channels = []
        for value in _channels(hex_color).split():
            c = int(value) / 255
            channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        r, g, b = channels
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)
