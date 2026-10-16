
// =====================================================
// POMODORO WORKSPACE 2.0
// SESSION SUMMARY V1
// Celebration Sheet - Grass Green
// =====================================================

let summaryInitialized = false;

const congratulations = [
    {
        title: "Vuýt đấy! CPU đã cày xong phiên này.",
        message: "Cho nghỉ ngơi tí đi nào!"
    },
    {
        title: "Xong một phiên rồi nhenn!",
        message:
            "Học đỉnh thế này chắc sắp thành " +
            "'học bá' tới nơi rồi đấy nhờ!"
    },
    {
        title: "Out trình chưa!",
        message:
            "Học hành năng suất thế này thì " +
            "thủ khoa cũng phải dè chừng bạn đấy nhá!"
    },
    {
        title: "Xịn chưa!",
        message:
            "Bộ não vừa chạy hết 101% " +
            "công suất luôn rồi đấy!"
    }
];


// -----------------------------------------------------
// Chuyển đổi số phút thành giá trị hợp lệ
// -----------------------------------------------------

function normalizeMinutes(value) {
    if (value === null || value === undefined || value === "") {
        return null;
    }

    const number = Number(value);

    if (!Number.isFinite(number) || number <= 0) {
        return null;
    }

    return Math.round(number * 10) / 10;
}


// -----------------------------------------------------
// Lấy thời lượng từ sự kiện hoàn thành
// -----------------------------------------------------

function getCompletedMinutes(detail = {}) {
    const directMinutes = [
        detail.durationMinutes,
        detail.minutes,
        detail.selectedMinutes,
        detail.focusMinutes,
        detail.plannedMinutes
    ];

    for (const value of directMinutes) {
        const minutes = normalizeMinutes(value);

        if (minutes !== null) {
            return minutes;
        }
    }

    const durationSeconds = Number(detail.durationSeconds);

    if (Number.isFinite(durationSeconds) && durationSeconds > 0) {
        return normalizeMinutes(durationSeconds / 60);
    }

    // Dự phòng: đọc thời lượng đang chọn ở In-Focus.
    const selectedButton = document.querySelector(
        "#pm-focus-duration-options " +
        ".pm-focus-duration-btn[aria-pressed='true']"
    );

    if (selectedButton) {
        const selectedValue = selectedButton.dataset.minutes;

        if (selectedValue === "custom") {
            const customInput = document.getElementById(
                "pm-focus-custom-minutes"
            );

            return normalizeMinutes(customInput?.value);
        }

        return normalizeMinutes(selectedValue);
    }

    return null;
}


// -----------------------------------------------------
// Lấy tên nhiệm vụ của phiên vừa hoàn thành
// -----------------------------------------------------

function getCompletedTaskName(detail = {}) {
    const candidates = [
        detail.taskName,
        detail.taskTitle,
        detail.task?.name,
        detail.task?.title,
        document.getElementById("pm-focus-active-task-name")?.textContent,
        document.getElementById("pm-focus-task-name")?.textContent
    ];

    for (const candidate of candidates) {
        if (typeof candidate !== "string") {
            continue;
        }

        const name = candidate.trim();

        if (
            name &&
            name !== "Nhiệm vụ đang học" &&
            name !== "Chưa chọn nhiệm vụ"
        ) {
            return name;
        }
    }

    return "Phiên tập trung";
}


// -----------------------------------------------------
// Khởi tạo Celebration Sheet
// -----------------------------------------------------

export function initSessionSummary() {
    if (summaryInitialized) {
        return;
    }

    const dialog = document.getElementById("pm-session-summary");

    if (!dialog) {
        console.warn(
            "[Session Summary] Không tìm thấy #pm-session-summary"
        );
        return;
    }

    const titleElement = document.getElementById("pm-summary-title");
    const messageElement = document.getElementById("pm-summary-message");
    const taskElement = document.getElementById("pm-summary-task-name");
    const minutesElement = document.getElementById("pm-summary-minutes");

    const closeButton = document.getElementById("pm-summary-close");
    const dismissButton = document.getElementById("pm-summary-dismiss");
    const progressButton = document.getElementById(
        "pm-summary-view-progress"
    );

    if (
        !titleElement ||
        !messageElement ||
        !taskElement ||
        !minutesElement ||
        !closeButton ||
        !dismissButton ||
        !progressButton
    ) {
        console.error(
            "[Session Summary] Thiếu thành phần HTML của sheet."
        );
        return;
    }

    let lastMessageIndex = -1;
    let completionVersion = 0;


    // -------------------------------------------------
    // Chọn thông điệp ngẫu nhiên
    // Hạn chế lặp lại cùng một câu liên tiếp
    // -------------------------------------------------

    function chooseMessage() {
        let index = Math.floor(
            Math.random() * congratulations.length
        );

        if (congratulations.length > 1 &&
            index === lastMessageIndex) {
            index = (index + 1) % congratulations.length;
        }

        lastMessageIndex = index;

        return congratulations[index];
    }


    // -------------------------------------------------
    // Đóng sheet
    // -------------------------------------------------

    function closeSummary() {
        if (dialog.open) {
            dialog.close();
        }
    }


    // -------------------------------------------------
    // Chuyển đến Dashboard
    // -------------------------------------------------

    function viewProgress() {
        closeSummary();

        const postFocus = document.getElementById(
            "pm-post-focus"
        );

        if (postFocus) {
            postFocus.scrollIntoView({
                behavior: window.matchMedia(
                    "(prefers-reduced-motion: reduce)"
                ).matches ? "auto" : "smooth",
                block: "start"
            });
        } else {
            console.info(
                "[Session Summary] Dashboard Post-Focus " +
                "sẽ được kết nối ở Giai đoạn B."
            );
        }
    }


    // -------------------------------------------------
    // Hiển thị kết quả phiên vừa hoàn thành
    // -------------------------------------------------

    function showSummary(detail = {}) {
        const message = chooseMessage();

        const taskName = getCompletedTaskName(detail);
        const minutes = getCompletedMinutes(detail);

        titleElement.textContent = message.title;
        messageElement.textContent = message.message;
        taskElement.textContent = taskName;

        minutesElement.textContent =
            minutes === null ? "—" : String(minutes);

        if (!dialog.open) {
            dialog.showModal();
        }

        console.log("[Session Summary] Celebration Sheet opened", {
            taskName,
            minutes
        });
    }


    // -------------------------------------------------
    // Sau khi Focus hoàn thành
    // -------------------------------------------------

    function handleFocusComplete(event) {
        const detail = event.detail ?? {};

        // Chụp dữ liệu ngay tại thời điểm nhận sự kiện.
        // Không đợi timer reset xong mới đọc dữ liệu.
        const snapshot = {
            taskName: getCompletedTaskName(detail),
            durationMinutes: getCompletedMinutes(detail)
        };

        const currentVersion = ++completionVersion;

        // Trình duyệt cần thoát Fullscreen trước khi
        // hiển thị modal trên trang Pomodoro chính.
        const fullscreenExit = document.fullscreenElement
            ? document.exitFullscreen().catch(() => {})
            : Promise.resolve();

        fullscreenExit.then(() => {
            if (currentVersion !== completionVersion) {
                return;
            }

            requestAnimationFrame(() => {
                showSummary(snapshot);
            });
        });
    }


    // -------------------------------------------------
    // Event listeners
    // -------------------------------------------------

    closeButton.addEventListener("click", closeSummary);

    dismissButton.addEventListener("click", closeSummary);

    progressButton.addEventListener("click", viewProgress);

    // Cho phép nhấn Escape theo hành vi mặc định
    // của <dialog>. Không chặn thao tác này.

    document.addEventListener(
        "pomodoro:focus-complete",
        handleFocusComplete
    );

    summaryInitialized = true;

    console.log(
        "[Session Summary] Celebration Sheet V1 initialized"
    );
}
