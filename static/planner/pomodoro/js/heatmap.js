
/* ============================================================
   POMODORO WORKSPACE 2.0
   POST-FOCUS HEATMAP - TIMELINE V2.3

   CHỨC NĂNG:
   01. Hiển thị Heatmap 12 tháng gần nhất
   02. Mỗi cột tương ứng một tuần
   03. Bảy hàng: Thứ Hai đến Chủ nhật
   04. Nhãn tháng định dạng 01 - 12
   05. Tổng thời gian theo từng tuần
   06. Cuộn ngang xem lịch sử
   07. Hiển thị số phút khi có hoạt động
   08. Không hiển thị tooltip cho ô 0 phút
   09. Chỉ cho chọn ô có hoạt động
   10. Nhận dữ liệu từ Django Backend

   QUY TẮC DỮ LIỆU:
   - Chỉ ghi nhận phiên hoàn thành
   - Không cộng phiên Gác lại
   - Không tạo dữ liệu thống kê giả
   - Không tự lưu dữ liệu vào database

   PUBLIC API:
   - initHeatmap()
   - setHeatmapData(data)

   EVENT:
   - pomodoro:heatmap-data
   ============================================================ */


// ============================================================
// 01. MODULE STATE
// ============================================================

let heatmapInitialized = false;

let elements = null;

// Tổng số phút tập trung theo ngày.
// Key: YYYY-MM-DD
// Value: tổng số phút
const dailyMinutes = new Map();

// Hiển thị 12 tháng gần nhất, bao gồm tháng hiện tại.
const TIMELINE_MONTHS = 12;

// Tên các thứ trong tuần bằng tiếng Việt.
const WEEKDAYS = [
    "Thứ Hai",
    "Thứ Ba",
    "Thứ Tư",
    "Thứ Năm",
    "Thứ Sáu",
    "Thứ Bảy",
    "Chủ nhật"
];


// ============================================================
// 02. DATE UTILITIES
// ============================================================

// Đưa ngày về 00:00:00 theo giờ địa phương.
function startOfDay(date) {
    return createDate(
        date.getFullYear(),
        date.getMonth(),
        date.getDate()
    );
}


// Tạo một đối tượng Date.
//
// Sử dụng setFullYear để xử lý chính xác
// cả những năm nằm trong khoảng 0 - 99.
function createDate(year, month, day) {
    const date = new Date(0);

    date.setFullYear(year, month, day);
    date.setHours(0, 0, 0, 0);

    return date;
}


// Cộng hoặc trừ số ngày.
//
// Không cộng trực tiếp milliseconds để tránh
// sai lệch khi có thay đổi giờ địa phương.
function addDays(date, amount) {
    return createDate(
        date.getFullYear(),
        date.getMonth(),
        date.getDate() + amount
    );
}


// Xác định ngày Thứ Hai đầu tuần.
//
// JavaScript:
// Chủ nhật = 0
// Thứ Hai = 1
// ...
// Thứ Bảy = 6
function startOfWeek(date) {
    const weekday = date.getDay();

    const offset = (weekday + 6) % 7;

    return addDays(date, -offset);
}


// Lấy ngày đầu tiên của tháng.
function startOfMonth(date) {
    return createDate(
        date.getFullYear(),
        date.getMonth(),
        1
    );
}


// ============================================================
// 03. TIMELINE RANGE
// ============================================================

/*
    Quy tắc hiện tại:

    Hiển thị 12 tháng gần nhất,
    bao gồm tháng đang diễn ra.

    Ví dụ:
    Hôm nay: 15/10/2026

    Bắt đầu: 01/11/2025
    Kết thúc: 15/10/2026

    Các ngày trước tháng đầu tiên hoặc
    sau ngày hiện tại không được tạo thành
    ô dữ liệu.

    Phạm vi này được giữ nguyên ở V2.3.
*/

function getTimelineRange() {
    const today = startOfDay(new Date());

    const firstMonth = createDate(
        today.getFullYear(),
        today.getMonth() - (TIMELINE_MONTHS - 1),
        1
    );

    return {
        today,

        firstMonth,

        firstWeek: startOfWeek(firstMonth),

        lastWeek: startOfWeek(today)
    };
}


// ============================================================
// 04. DATE KEY
// ============================================================

// Chuyển Date thành YYYY-MM-DD.
//
// Không sử dụng toISOString() vì hàm đó
// chuyển về UTC, có thể gây lệch ngày.
function dateKey(date) {
    const year = date.getFullYear();

    const month = String(
        date.getMonth() + 1
    ).padStart(2, "0");

    const day = String(
        date.getDate()
    ).padStart(2, "0");

    return `${year}-${month}-${day}`;
}


// Chuyển chuỗi YYYY-MM-DD thành Date.
//
// Nếu chuỗi không phải ngày hợp lệ,
// trả về null.
function parseDateKey(value) {
    if (
        typeof value !== "string" ||
        !/^\d{4}-\d{2}-\d{2}$/.test(value)
    ) {
        return null;
    }

    const [year, month, day] = value
        .split("-")
        .map(Number);

    const parsedDate = createDate(
        year,
        month - 1,
        day
    );

    if (
        parsedDate.getFullYear() !== year ||
        parsedDate.getMonth() !== month - 1 ||
        parsedDate.getDate() !== day
    ) {
        return null;
    }

    return parsedDate;
}


// ============================================================
// 05. FORMATTING - TIẾNG VIỆT
// ============================================================

// Định dạng ngày: 15/10/2026.
const dateFormatter = new Intl.DateTimeFormat(
    "vi-VN",
    {
        day: "2-digit",
        month: "2-digit",
        year: "numeric"
    }
);


// Định dạng số phút theo tiếng Việt.
const numberFormatter = new Intl.NumberFormat(
    "vi-VN",
    {
        maximumFractionDigits: 1
    }
);


// Hiển thị ngày.
function formatDate(date) {
    return dateFormatter.format(date);
}


// Hiển thị số phút.
function formatMinutes(minutes) {
    return numberFormatter.format(minutes);
}


// Hiển thị tháng:
//
// Tháng 01
// Tháng 02
// ...
// Tháng 12
function formatMonth(date) {
    const month = String(
        date.getMonth() + 1
    ).padStart(2, "0");

    return `Tháng ${month}`;
}


// ============================================================
// 06. DATA UTILITIES
// ============================================================

// Lấy tổng số phút của một ngày.
//
// Nếu chưa có bản ghi, mặc định là 0.
function getMinutes(date) {
    return dailyMinutes.get(dateKey(date)) ?? 0;
}


// Phân loại mức độ tập trung.
//
// Level 0: 0 phút
// Level 1: Trên 0 và dưới 15 phút
// Level 2: 15 đến 60 phút
// Level 3: Trên 60 phút
function getLevel(minutes) {
    if (minutes <= 0) {
        return 0;
    }

    if (minutes < 15) {
        return 1;
    }

    if (minutes <= 60) {
        return 2;
    }

    return 3;
}


// Kiểm tra ngày thuộc phạm vi Timeline.
function isWithinTimeline(date, range) {
    return (
        date >= range.firstMonth &&
        date <= range.today
    );
}


// ============================================================
// 07. DOM UTILITIES
// ============================================================

// Tạo phần tử HTML.
//
// Sử dụng textContent thay vì innerHTML
// để tránh chèn mã HTML từ dữ liệu.
function createElement(
    tag,
    className,
    text = null
) {
    const element = document.createElement(tag);

    if (className) {
        element.className = className;
    }

    if (text !== null) {
        element.textContent = text;
    }

    return element;
}


// Xác định vị trí trong CSS Grid.
function positionElement(
    element,
    column,
    row
) {
    element.style.gridColumn = String(column);

    element.style.gridRow = String(row);

    return element;
}


// Tạo nhãn cho Grid.
function addLabel(
    grid,
    text,
    column,
    row,
    className
) {
    const label = createElement(
        "span",
        className,
        text
    );

    positionElement(
        label,
        column,
        row
    );

    grid.appendChild(label);

    return label;
}


// Tạo ô trống ngoài phạm vi Timeline.
//
// Ô này không tương tác,
// không có tooltip.
function createEmptyCell(column, row) {
    const empty = createElement(
        "span",
        "pm-heatmap-empty"
    );

    empty.setAttribute(
        "aria-hidden",
        "true"
    );

    positionElement(
        empty,
        column,
        row
    );

    return empty;
}


// ============================================================
// 08. SELECTED DAY DETAILS
// ============================================================

/*
    Chỉ những ngày có thời gian tập trung
    lớn hơn 0 phút mới được chọn.

    Ví dụ:
    15/10/2026 có 25 phút

    Hiển thị:
    "Bạn đã tập trung 25 phút vào ngày 15/10/2026."

    Ô 0 phút sẽ không gọi hàm này.
*/

function selectDay(date, button) {
    if (!elements) {
        return;
    }

    const minutes = getMinutes(date);

    // Ngăn mở chi tiết nếu không có hoạt động.
    if (minutes <= 0) {
        return;
    }

    // Bỏ trạng thái được chọn trước đó.
    const selectedCells = elements.grid.querySelectorAll(
        ".pm-heatmap-cell.is-selected"
    );

    selectedCells.forEach(cell => {
        cell.classList.remove(
            "is-selected"
        );

        cell.setAttribute(
            "aria-pressed",
            "false"
        );
    });

    // Đánh dấu ô vừa được chọn.
    button.classList.add(
        "is-selected"
    );

    button.setAttribute(
        "aria-pressed",
        "true"
    );

    // Hiển thị ngày.
    elements.selectedDate.textContent =
        formatDate(date);

    // Hiển thị thông tin tập trung.
    elements.selectedDescription.textContent =
        `Bạn đã tập trung ${formatMinutes(minutes)} ` +
        `phút vào ngày ${formatDate(date)}.`;

    // Hiện khung chi tiết.
    elements.dayDetails.hidden = false;
}


// ============================================================
// 09. CREATE DAY CELL - V2.3
// ============================================================

/*
    QUY TẮC HIỂN THỊ:

    A. Ngày không có hoạt động:
       - Màu Level 0
       - Không có số phút
       - Không tooltip
       - Không thể nhấn
       - Không mở chi tiết

    B. Ngày có hoạt động:
       - Màu theo số phút
       - Hiển thị số phút
       - Có tooltip tiếng Việt
       - Nhấn để xem chi tiết

    C. Ngày tương lai:
       - Không có thành tích
       - Không tooltip
       - Không thể nhấn
*/

function createDayCell(date) {
    const minutes = getMinutes(date);

    const today = startOfDay(new Date());

    const isFuture = date > today;

    const isInactive = minutes <= 0 || isFuture;

    const button = createElement(
        "button",
        "pm-heatmap-cell"
    );

    button.type = "button";

    button.dataset.date = dateKey(date);

    // --------------------------------------------------------
    // A. KHÔNG CÓ HOẠT ĐỘNG
    // --------------------------------------------------------

    if (isInactive) {
        button.dataset.level = "0";

        // Không hiển thị số phút.
        button.textContent = "";

        // Không có tooltip.
        button.removeAttribute("title");

        // Không tương tác bằng chuột/bàn phím.
        button.disabled = true;

        // Vẫn cung cấp mô tả ngắn gọn cho
        // công nghệ hỗ trợ tiếp cận.
        button.setAttribute(
            "aria-label",
            `${formatDate(date)}: 0 phút tập trung`
        );

        return button;
    }

    // --------------------------------------------------------
    // B. NGÀY CÓ HOẠT ĐỘNG
    // --------------------------------------------------------

    const level = getLevel(minutes);

    button.dataset.level = String(level);

    // Hiển thị số phút trong ô.
    button.textContent = formatMinutes(minutes);

    // Nội dung tooltip.
    const description =
        `Ngày ${formatDate(date)}: ` +
        `${formatMinutes(minutes)} phút tập trung.`;

    // Hiển thị tooltip khi hover.
    button.title = description;

    // Hỗ trợ trình đọc màn hình.
    button.setAttribute(
        "aria-label",
        description
    );

    // Trạng thái chọn.
    button.setAttribute(
        "aria-pressed",
        "false"
    );

    // Chỉ ô có hoạt động mới được gắn sự kiện.
    button.addEventListener(
        "click",
        () => {
            selectDay(date, button);
        }
    );

    return button;
}


// ============================================================
// 10. CREATE TIMELINE GRID
// ============================================================

/*
    Grid có cấu trúc:

    Cột 1:
        Nhãn Thứ Hai đến Chủ nhật
        và Tổng cộng.

    Cột 2 trở đi:
        Mỗi cột = một tuần.

    Hàng 1:
        Tên tháng.

    Hàng 2 - 8:
        Thứ Hai đến Chủ nhật.

    Hàng 9:
        Tổng phút mỗi tuần.

    CSS xử lý cố định cột thứ.
*/

function createTimelineGrid(weekCount) {
    const grid = createElement(
        "div",
        "pm-heatmap-calendar"
    );

    grid.style.gridTemplateColumns =
        "var(--pm-heatmap-label-width, 82px) " +
        `repeat(${weekCount}, ` +
        "var(--pm-heatmap-cell-width, 44px))";

    grid.style.gridTemplateRows =
        "26px repeat(7, " +
        "var(--pm-heatmap-cell-height, 29px)) 28px";

    return grid;
}


// ============================================================
// 11. MONTH LABELS
// ============================================================

/*
    Mỗi tháng có một nhãn riêng.

    Ví dụ:
    Tháng 11
    Tháng 12
    Tháng 01
    ...

    Nhãn tháng đặt tại tuần chứa ngày 01
    của tháng tương ứng.

    CSS chịu trách nhiệm hiển thị toàn bộ
    nhãn, không cắt chữ.
*/

function addMonthLabels(
    grid,
    weekStarts,
    range
) {
    for (
        let monthDate = range.firstMonth;
        monthDate <= range.today;
        monthDate = createDate(
            monthDate.getFullYear(),
            monthDate.getMonth() + 1,
            1
        )
    ) {
        const monthWeek = startOfWeek(
            monthDate
        );

        const weekIndex = weekStarts.findIndex(
            week =>
                week.getTime() ===
                monthWeek.getTime()
        );

        if (weekIndex === -1) {
            continue;
        }

        const column = weekIndex + 2;

        const label = addLabel(
            grid,
            formatMonth(monthDate),
            column,
            1,
            "pm-heatmap-month-label"
        );

        label.dataset.month = dateKey(
            monthDate
        );

        // Có thể dùng khi kiểm tra dữ liệu
        // trải dài qua nhiều năm.
        label.title =
            `${formatMonth(monthDate)}/` +
            monthDate.getFullYear();
    }
}


// ============================================================
// 12. WEEKDAY LABELS
// ============================================================

function addWeekdayLabels(grid) {
    // Bảy hàng tương ứng với bảy thứ.
    WEEKDAYS.forEach(
        (dayName, index) => {
            addLabel(
                grid,
                dayName,
                1,
                index + 2,
                "pm-heatmap-day-label"
            );
        }
    );

    // Hàng tổng cuối cùng.
    addLabel(
        grid,
        "Tổng cộng",
        1,
        9,
        "pm-heatmap-day-label " +
        "pm-heatmap-day-label--total"
    );
}


// ============================================================
// 13. RENDER WEEK COLUMNS
// ============================================================

/*
    Mỗi cột là một tuần.

    Một tuần gồm:
    - Thứ Hai
    - Thứ Ba
    - Thứ Tư
    - Thứ Năm
    - Thứ Sáu
    - Thứ Bảy
    - Chủ nhật

    Tổng cộng = tổng phút của bảy ngày
    nằm trong phạm vi Timeline.

    Không cộng ngày ngoài phạm vi.
*/

function renderWeekColumns(
    grid,
    weekStarts,
    range
) {
    weekStarts.forEach(
        (weekStart, weekIndex) => {
            const column = weekIndex + 2;

            let weeklyTotal = 0;

            // Tạo bảy ô của tuần.
            for (
                let weekday = 0;
                weekday < 7;
                weekday++
            ) {
                const date = addDays(
                    weekStart,
                    weekday
                );

                const row = weekday + 2;

                // --------------------------------------------
                // NGÀY NGOÀI PHẠM VI
                // --------------------------------------------

                if (!isWithinTimeline(date, range)) {
                    const empty = createEmptyCell(
                        column,
                        row
                    );

                    grid.appendChild(empty);

                    continue;
                }

                // --------------------------------------------
                // NGÀY TRONG PHẠM VI
                // --------------------------------------------

                const cell = createDayCell(date);

                positionElement(
                    cell,
                    column,
                    row
                );

                grid.appendChild(cell);

                // Tổng số phút trong tuần.
                weeklyTotal += getMinutes(date);
            }

            // --------------------------------------------
            // HÀNG TỔNG CỘNG
            // --------------------------------------------

            addLabel(
                grid,
                formatMinutes(weeklyTotal),
                column,
                9,
                "pm-heatmap-column-total"
            );
        }
    );
}


// ============================================================
// 14. RENDER HEATMAP
// ============================================================

function renderHeatmap() {
    if (!elements) {
        return;
    }

    const range = getTimelineRange();

    // Danh sách các tuần trong khoảng thời gian.
    const weekStarts = [];

    for (
        let week = range.firstWeek;
        week <= range.lastWeek;
        week = addDays(week, 7)
    ) {
        weekStarts.push(week);
    }

    // Tạo CSS Grid.
    const grid = createTimelineGrid(
        weekStarts.length
    );

    // Thêm nhãn tháng.
    addMonthLabels(
        grid,
        weekStarts,
        range
    );

    // Thêm nhãn các thứ và Tổng cộng.
    addWeekdayLabels(grid);

    // Tạo ma trận ngày và tổng tuần.
    renderWeekColumns(
        grid,
        weekStarts,
        range
    );

    // Thay thế nội dung biểu đồ cũ.
    elements.grid.replaceChildren(grid);

    // Ẩn thông tin của ngày từng chọn.
    elements.dayDetails.hidden = true;

    elements.selectedDate.textContent = "—";

    elements.selectedDescription.textContent =
        "Chọn ngày có hoạt động để xem chi tiết.";

    // Khi khởi tạo hoặc cập nhật dữ liệu,
    // đưa phần cuộn đến các tuần gần nhất.
    requestAnimationFrame(() => {
        if (!elements) {
            return;
        }

        elements.scroll.scrollLeft =
            elements.scroll.scrollWidth -
            elements.scroll.clientWidth;
    });
}


// ============================================================
// 15. PUBLIC DATA API
// ============================================================

/*
    API nhận dữ liệu theo hai dạng.

    CÁCH 1: ARRAY

    [
        {
            date: "2026-10-12",
            minutes: 25
        },
        {
            date: "2026-10-13",
            minutes: 50
        }
    ]

    CÁCH 2: OBJECT

    {
        "2026-10-12": 25,
        "2026-10-13": 50
    }

    Quy tắc:
    - Chỉ truyền phút của phiên hoàn thành.
    - Không truyền phiên Gác lại.
    - Cùng ngày sẽ được cộng dồn.
    - Gọi lại sẽ thay thế dữ liệu cũ.
    - Không tự phát sinh dữ liệu giả.

    Các khóa date, minutes được giữ
    theo chuẩn API để kết nối Django.
*/

export function setHeatmapData(data) {
    const updatedData = new Map();

    let records = [];

    // --------------------------------------------------------
    // A. ĐỌC ARRAY
    // --------------------------------------------------------

    if (Array.isArray(data)) {
        records = data;
    }

    // --------------------------------------------------------
    // B. ĐỌC OBJECT
    // --------------------------------------------------------

    else if (
        data !== null &&
        typeof data === "object"
    ) {
        records = Object.entries(data).map(
            ([date, minutes]) => ({
                date,
                minutes
            })
        );
    }

    // --------------------------------------------------------
    // C. CHUẨN HÓA DỮ LIỆU
    // --------------------------------------------------------

    for (const record of records) {
        if (
            !record ||
            typeof record !== "object"
        ) {
            continue;
        }

        const parsedDate = parseDateKey(
            record.date
        );

        const minutes = Number(
            record.minutes
        );

        // Không chấp nhận dữ liệu không hợp lệ.
        if (
            !parsedDate ||
            !Number.isFinite(minutes) ||
            minutes < 0
        ) {
            continue;
        }

        const key = dateKey(
            parsedDate
        );

        const existing = updatedData.get(key) ?? 0;

        updatedData.set(
            key,
            existing + minutes
        );
    }

    // --------------------------------------------------------
    // D. THAY THẾ DỮ LIỆU CŨ
    // --------------------------------------------------------

    dailyMinutes.clear();

    updatedData.forEach(
        (minutes, date) => {
            dailyMinutes.set(
                date,
                minutes
            );
        }
    );

    // --------------------------------------------------------
    // E. CẬP NHẬT GIAO DIỆN
    // --------------------------------------------------------

    renderHeatmap();

    console.log(
        "[Heatmap] Đã cập nhật dữ liệu:",
        dailyMinutes.size,
        "ngày"
    );
}


// ============================================================
// 16. INITIALIZATION
// ============================================================

export function initHeatmap() {
    // Không khởi tạo nhiều lần.
    if (heatmapInitialized) {
        return;
    }

    const root = document.getElementById(
        "pm-focus-heatmap"
    );

    if (!root) {
        console.warn(
            "[Heatmap] Không tìm thấy #pm-focus-heatmap"
        );

        return;
    }

    // --------------------------------------------------------
    // A. LẤY DOM ELEMENTS
    // --------------------------------------------------------

    elements = {
        root,

        grid: document.getElementById(
            "pm-heatmap-grid"
        ),

        scroll: document.getElementById(
            "pm-heatmap-scroll"
        ),

        dayDetails: document.getElementById(
            "pm-heatmap-day-details"
        ),

        selectedDate: document.getElementById(
            "pm-heatmap-selected-date"
        ),

        selectedDescription: document.getElementById(
            "pm-heatmap-selected-description"
        )
    };

    // --------------------------------------------------------
    // B. KIỂM TRA HTML
    // --------------------------------------------------------

    const required = [
        "grid",
        "scroll",
        "dayDetails",
        "selectedDate",
        "selectedDescription"
    ];

    const missing = required.filter(
        key => !elements[key]
    );

    if (missing.length > 0) {
        console.error(
            "[Heatmap] Thiếu thành phần HTML:",
            missing
        );

        elements = null;

        return;
    }

    // --------------------------------------------------------
    // C. LẮNG NGHE DỮ LIỆU
    // --------------------------------------------------------

    document.addEventListener(
        "pomodoro:heatmap-data",
        event => {
            setHeatmapData(
                event.detail?.days ?? []
            );
        }
    );

    // --------------------------------------------------------
    // D. KHỞI TẠO
    // --------------------------------------------------------

    heatmapInitialized = true;

    renderHeatmap();

    console.log(
        "[Heatmap] Timeline V2.3 đã khởi tạo"
    );
}
