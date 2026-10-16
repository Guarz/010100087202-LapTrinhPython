
/* ============================================================
   AI STUDYPLANNER - POMODORO WORKSPACE 2.0

   C2.3.3 - SESSION RECORDER V2

   NHIỆM VỤ:
   - Theo dõi một phiên Focus.
   - Không tính thời gian Pause / Exit Dialog.
   - Gửi completed hoặc deferred về Django.
   - Liên kết Task thật từ Task Selector V13.
   - Lưu tên Quick Goal.
   - Tạo UUID duy nhất cho mỗi phiên.
   - Giữ UUID không đổi cho request của cùng phiên.

   KHÔNG CAN THIỆP:
   - Countdown Engine
   - Music Player
   - Background Picker
   - Celebration Sheet

   API:
   POST /api/save-pomodoro/
   ============================================================ */


// ============================================================
// 01. MODULE STATE
// ============================================================

let recorderInitialized = false;

let currentSession = null;

// Ghi nhớ lựa chọn hiện tại của Task Selector.
let selectedTask = null;

const SAVE_API_URL = "/api/save-pomodoro/";


// ============================================================
// 02. UTILITIES
// ============================================================

// Đọc cookie Django.
function getCookie(name) {

    const cookies = document.cookie
        ? document.cookie.split(";")
        : [];

    for (const cookie of cookies) {

        const value = cookie.trim();

        if (value.startsWith(`${name}=`)) {

            return decodeURIComponent(
                value.substring(name.length + 1)
            );
        }
    }

    return null;
}


// Ưu tiên CSRF token trong form, sau đó đến cookie.
function getCsrfToken() {

    const input = document.querySelector(
        'input[name="csrfmiddlewaretoken"]'
    );

    return (
        input?.value ||
        getCookie("csrftoken")
    );
}


// Giới hạn một giá trị số.
function clamp(value, minimum, maximum) {

    return Math.min(
        maximum,
        Math.max(minimum, value)
    );
}


// Chỉ nhận số nguyên dương hợp lệ.
function positiveInteger(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return null;
    }

    const number = Number(value);

    if (
        !Number.isSafeInteger(number) ||
        number <= 0
    ) {
        return null;
    }

    return number;
}


// Tạo UUID v4 bằng Web Crypto API.
function createSessionUUID() {

    if (
        typeof crypto !== "undefined" &&
        typeof crypto.randomUUID === "function"
    ) {
        return crypto.randomUUID();
    }

    if (
        typeof crypto === "undefined" ||
        typeof crypto.getRandomValues !== "function"
    ) {
        throw new Error(
            "Trình duyệt không hỗ trợ tạo UUID an toàn."
        );
    }

    const bytes = new Uint8Array(16);

    crypto.getRandomValues(bytes);

    // UUID version 4.
    bytes[6] = (bytes[6] & 0x0f) | 0x40;

    // UUID variant RFC 4122.
    bytes[8] = (bytes[8] & 0x3f) | 0x80;

    const hex = Array.from(
        bytes,
        byte => byte.toString(16).padStart(2, "0")
    );

    return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join("")
    ].join("-");
}


// ============================================================
// 03. TASK SELECTION
// ============================================================

// Task Selector V13 phát pomodoro:task-change.
//
// Scheduled Task:
// {
//     id: 12,
//     taskId: 12,
//     name: "...",
//     type: "scheduled"
// }
//
// Quick Goal:
// {
//     id: "quick-current",
//     name: "...",
//     type: "quick"
// }

function updateSelectedTask(detail) {

    if (
        !detail ||
        typeof detail !== "object"
    ) {
        selectedTask = null;
        return;
    }

    selectedTask = { ...detail };
}


// Xác định Task chính xác tại thời điểm bắt đầu.
//
// Không dùng id của Quick Goal làm task_id.
// Không dùng một ID chưa được xác thực là Task thật.

function resolveSessionTask(focusTask) {

    const task = (
        focusTask &&
        typeof focusTask === "object"
    )
        ? focusTask
        : null;

    if (!task) {

        return {
            taskId: null,
            quickGoalTitle: ""
        };
    }

    if (task.type === "quick") {

        const name = String(
            task.name || ""
        ).trim();

        return {
            taskId: null,
            quickGoalTitle: name.slice(0, 200)
        };
    }

    if (task.type === "scheduled") {

        // Ưu tiên ID thật nếu Focus Timer có truyền.
        let taskId = positiveInteger(
            task.taskId
        );

        // Focus Timer V2.2 có thể chỉ truyền id/name/type.
        // Khi đó đối chiếu với lựa chọn của Task Selector.
        if (
            taskId === null &&
            selectedTask?.type === "scheduled" &&
            String(selectedTask.id) === String(task.id) &&
            selectedTask.name === task.name
        ) {
            taskId = positiveInteger(
                selectedTask.taskId
            );
        }

        return {
            taskId,
            quickGoalTitle: ""
        };
    }

    return {
        taskId: null,
        quickGoalTitle: ""
    };
}


// ============================================================
// 04. TRACKING ACTIVE TIME
// ============================================================

function accumulateRunningTime() {

    if (
        !currentSession ||
        !currentSession.isRunning
    ) {
        return;
    }

    const now = performance.now();

    const delta = Math.max(
        0,
        now - currentSession.lastResumeAt
    );

    currentSession.activeMilliseconds += delta;

    currentSession.lastResumeAt = now;
}


// Bắt đầu hoặc tiếp tục tính thời gian tập trung.
function resumeTracking() {

    if (
        !currentSession ||
        currentSession.finalized ||
        currentSession.isRunning
    ) {
        return;
    }

    currentSession.lastResumeAt = performance.now();

    currentSession.isRunning = true;
}


// Tạm dừng tính thời gian tập trung.
function pauseTracking() {

    if (
        !currentSession ||
        !currentSession.isRunning
    ) {
        return;
    }

    accumulateRunningTime();

    currentSession.isRunning = false;
}


// ============================================================
// 05. BEGIN SESSION
// ============================================================

function beginSession(detail = {}) {

    const durationMinutes = positiveInteger(
        detail.durationMinutes
    );

    if (
        durationMinutes === null ||
        durationMinutes > 180
    ) {

        console.error(
            "[Pomodoro Recorder] Thời lượng không hợp lệ."
        );

        return;
    }

    // Không ghi đè một phiên chưa kết thúc.
    if (
        currentSession &&
        !currentSession.finalized
    ) {

        console.warn(
            "[Pomodoro Recorder] Có phiên chưa kết thúc."
        );

        return;
    }

    let sessionUUID;

    try {

        sessionUUID = createSessionUUID();

    } catch (error) {

        console.error(
            "[Pomodoro Recorder] Không tạo được UUID:",
            error
        );

        return;
    }

    const taskInfo = resolveSessionTask(
        detail.task
    );

    const now = performance.now();

    currentSession = {

        sessionUUID,

        startedAt: new Date().toISOString(),

        durationMinutes,

        taskId: taskInfo.taskId,

        quickGoalTitle: taskInfo.quickGoalTitle,

        activeMilliseconds: 0,

        lastResumeAt: now,

        isRunning: true,

        finalized: false
    };

    console.info(
        "[Pomodoro Recorder] C2.3 - Bắt đầu phiên:",
        {
            session_uuid: sessionUUID,
            task_id: currentSession.taskId,
            quick_goal_title: currentSession.quickGoalTitle,
            duration_minutes: durationMinutes
        }
    );
}


// ============================================================
// 06. BUILD SESSION PAYLOAD
// ============================================================

function buildSessionPayload(status) {

    if (!currentSession) {
        return null;
    }

    const session = currentSession;

    const maximumSeconds =
        session.durationMinutes * 60;

    let actualSeconds = 0;

    let remainingSeconds = 0;

    if (status === "completed") {

        // Focus Timer chỉ phát complete khi về 00:00.
        actualSeconds = maximumSeconds;

        remainingSeconds = 0;

    } else if (status === "deferred") {

        actualSeconds = Math.floor(
            session.activeMilliseconds / 1000
        );

        actualSeconds = clamp(
            actualSeconds,
            0,
            maximumSeconds - 1
        );

        remainingSeconds =
            maximumSeconds - actualSeconds;

    } else {

        return null;
    }

    return {

        session_uuid: session.sessionUUID,

        task_id: session.taskId,

        quick_goal_title: session.quickGoalTitle,

        status,

        duration_minutes: session.durationMinutes,

        actual_seconds: actualSeconds,

        remaining_seconds: remainingSeconds,

        started_at: session.startedAt
    };
}


// ============================================================
// 07. SAVE SESSION TO DJANGO
// ============================================================

async function saveSession(payload) {

    const csrfToken = getCsrfToken();

    if (!csrfToken) {

        throw new Error(
            "Không tìm thấy CSRF token của Django."
        );
    }

    const response = await fetch(
        SAVE_API_URL,
        {
            method: "POST",

            credentials: "same-origin",

            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
                "Accept": "application/json"
            },

            body: JSON.stringify(payload)
        }
    );

    const contentType = (
        response.headers.get("content-type") || ""
    );

    if (!contentType.includes("application/json")) {

        throw new Error(
            "Máy chủ không trả về JSON. " +
            "Hãy kiểm tra đăng nhập và cấu hình URL."
        );
    }

    const result = await response.json();

    if (
        !response.ok ||
        result.status !== "success"
    ) {

        throw new Error(
            result.message ||
            `Không thể lưu phiên (HTTP ${response.status}).`
        );
    }

    return result;
}


// ============================================================
// 08. FINISH SESSION
// ============================================================

async function finishSession(status) {

    if (!currentSession) {

        console.warn(
            "[Pomodoro Recorder] Không có phiên để lưu."
        );

        return;
    }

    if (currentSession.finalized) {
        return;
    }

    // Chốt thời gian trước khi tạo payload.
    pauseTracking();

    // Ngăn hai event kết thúc gửi hai request.
    currentSession.finalized = true;

    const payload = buildSessionPayload(status);

    if (!payload) {

        console.error(
            "[Pomodoro Recorder] Không tạo được payload."
        );

        currentSession = null;

        return;
    }

    // Phiên mới không bị khóa bởi request cũ.
    currentSession = null;

    try {

        const result = await saveSession(payload);

        console.info(
            "[Pomodoro Recorder] C2.3 - Đã lưu phiên:",
            result.data
        );

        document.dispatchEvent(
            new CustomEvent(
                "pomodoro:session-saved",
                {
                    detail: {
                        payload,
                        result
                    }
                }
            )
        );

    } catch (error) {

        console.error(
            "[Pomodoro Recorder] Lưu phiên thất bại:",
            error
        );

        document.dispatchEvent(
            new CustomEvent(
                "pomodoro:session-save-error",
                {
                    detail: {
                        payload,
                        message: error.message
                    }
                }
            )
        );
    }
}


// ============================================================
// 09. INITIALIZATION
// ============================================================

export function initSessionRecorder() {

    if (recorderInitialized) {
        return;
    }

    const root = document.getElementById(
        "pomodoro-app"
    );

    if (!root) {
        return;
    }

    recorderInitialized = true;


    // A. THEO DÕI TASK ĐANG CHỌN
    document.addEventListener(
        "pomodoro:task-change",
        event => {

            updateSelectedTask(
                event.detail
            );
        }
    );


    // B. BẮT ĐẦU PHIÊN
    document.addEventListener(
        "pomodoro:focus-start",
        event => {

            beginSession(
                event.detail || {}
            );
        }
    );


    // C. PAUSE
    document.addEventListener(
        "pomodoro:focus-media-pause",
        pauseTracking
    );

    document.addEventListener(
        "pomodoro:focus-pause",
        pauseTracking
    );


    // D. RESUME
    document.addEventListener(
        "pomodoro:focus-media-resume",
        resumeTracking
    );

    document.addEventListener(
        "pomodoro:focus-resume",
        resumeTracking
    );


    // E. HOÀN THÀNH
    document.addEventListener(
        "pomodoro:focus-complete",
        () => {

            void finishSession("completed");
        }
    );


    // F. GÁC LẠI
    document.addEventListener(
        "pomodoro:focus-abandon",
        () => {

            void finishSession("deferred");
        }
    );


    console.info(
        "[Pomodoro Recorder] C2.3.3 đã khởi tạo."
    );
}
