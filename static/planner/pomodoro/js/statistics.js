
/* ============================================================
   AI STUDYPLANNER - POMODORO WORKSPACE 2.0

   C3.3 - STATISTICS CONTROLLER V1

   CHỨC NĂNG:
   - Lấy thống kê thật từ Django API.
   - Cập nhật ba thẻ Post-Focus.
   - Tự làm mới khi một phiên được lưu thành công.
   - Không thay đổi HTML/CSS.
   - Không ghi dữ liệu vào database.

   API:
   GET /api/pomodoro-statistics/
   ============================================================ */


// ============================================================
// 01. MODULE STATE
// ============================================================

let statisticsInitialized = false;

const STATISTICS_API_URL = "/api/pomodoro-statistics/";


// ============================================================
// 02. DOM UTILITIES
// ============================================================

function getStatisticsElements() {

    return {
        totalMinutes: document.getElementById(
            "pm-stat-total-minutes"
        ),

        completedSessions: document.getElementById(
            "pm-stat-completed-sessions"
        ),

        currentStreak: document.getElementById(
            "pm-stat-current-streak"
        )
    };
}


// ============================================================
// 03. VALIDATE DATA
// ============================================================

function isValidStatistic(value) {

    return (
        Number.isSafeInteger(value) &&
        value >= 0
    );
}


function validateStatistics(data) {

    if (
        !data ||
        typeof data !== "object"
    ) {
        throw new Error(
            "Dữ liệu Statistics không hợp lệ."
        );
    }

    const {
        total_minutes,
        completed_sessions,
        current_streak
    } = data;

    if (
        !isValidStatistic(total_minutes) ||
        !isValidStatistic(completed_sessions) ||
        !isValidStatistic(current_streak)
    ) {
        throw new Error(
            "Các chỉ số Statistics không hợp lệ."
        );
    }

    return {
        totalMinutes: total_minutes,
        completedSessions: completed_sessions,
        currentStreak: current_streak
    };
}


// ============================================================
// 04. RENDER STATISTICS
// ============================================================

function renderStatistics(data) {

    const elements = getStatisticsElements();

    const formatted = new Intl.NumberFormat("vi-VN");

    elements.totalMinutes.textContent =
        formatted.format(data.totalMinutes);

    elements.completedSessions.textContent =
        formatted.format(data.completedSessions);

    elements.currentStreak.textContent =
        formatted.format(data.currentStreak);
}


// ============================================================
// 05. FETCH STATISTICS
// ============================================================

async function fetchStatistics() {

    const response = await fetch(
        STATISTICS_API_URL,
        {
            method: "GET",

            credentials: "same-origin",

            headers: {
                "Accept": "application/json"
            },

            cache: "no-store"
        }
    );

    const contentType = (
        response.headers.get("content-type") || ""
    );

    if (!contentType.includes("application/json")) {

        throw new Error(
            "Statistics API không trả về JSON. " +
            "Hãy kiểm tra trạng thái đăng nhập."
        );
    }

    const result = await response.json();

    if (
        !response.ok ||
        result.status !== "success"
    ) {
        throw new Error(
            result.message ||
            `Statistics API lỗi HTTP ${response.status}.`
        );
    }

    return validateStatistics(result.data);
}


// ============================================================
// 06. LOAD AND UPDATE
// ============================================================

async function refreshStatistics() {

    try {

        const statistics = await fetchStatistics();

        renderStatistics(statistics);

        console.info(
            "[Statistics] Đã cập nhật dữ liệu:",
            statistics
        );

    } catch (error) {

        console.error(
            "[Statistics] Không thể tải dữ liệu:",
            error
        );
    }
}


// ============================================================
// 07. INITIALIZATION
// ============================================================

export function initStatistics() {

    if (statisticsInitialized) {
        return;
    }

    const root = document.getElementById(
        "pm-streak-stats"
    );

    if (!root) {

        console.warn(
            "[Statistics] Không tìm thấy #pm-streak-stats."
        );

        return;
    }

    const elements = getStatisticsElements();

    if (
        !elements.totalMinutes ||
        !elements.completedSessions ||
        !elements.currentStreak
    ) {

        console.error(
            "[Statistics] Thiếu ID của các thẻ thống kê."
        );

        return;
    }

    statisticsInitialized = true;

    // Tải dữ liệu lần đầu khi mở trang.
    void refreshStatistics();

    // Cập nhật sau khi Backend đã lưu phiên thành công.
    document.addEventListener(
        "pomodoro:session-saved",
        () => {
            void refreshStatistics();
        }
    );

    console.info(
        "[Statistics] C3.3 đã khởi tạo."
    );
}
