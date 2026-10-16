
/* ============================================================
   POMODORO WORKSPACE 2.0
   FOCUS TIMER V2.2 - MUSIC EVENT FIX

   GIỮ NGUYÊN:
   - Task Selector Integration
   - Background Picker Integration
   - Duration Selector
   - Countdown Engine
   - Global Pause / Resume
   - Fullscreen API + Fallback
   - Adaptive Contrast
   - Exit Dialog
   - Complete / Abandon Events

   CHỈ CHỈNH MUSIC INTEGRATION:
   - Focus Timer không tự tạo Audio.
   - Focus Timer không tự khóa nút nhạc.
   - Music Player quản lý nhạc nghe thử và nhạc Focus.
   - Gửi focus-start trước khi khởi chạy timer/video.
   - Global Pause/Resume phát sự kiện điều khiển nhạc.

   TƯƠNG THÍCH:
   music-player.js bản có focusAudio riêng và các
   sự kiện pomodoro:focus-*.

   ============================================================ */

import {
    getSelectedBackground
} from "./background-picker.js";


export function initFocusTimer() {

    /* ========================================================
       1. LẤY CÁC PHẦN TỬ HTML
       ======================================================== */

    const root = document.getElementById("pomodoro-app");

    if (!root) {
        return;
    }

    const get = id => document.getElementById(id);


    // PREVIEW

    const durationButtons = [
        ...root.querySelectorAll(".pm-focus-duration-btn")
    ];

    const customField = get("pm-focus-custom-field");
    const customInput = get("pm-focus-custom-minutes");

    const previewTime = get("pm-focus-preview-time");
    const previewTaskName = get("pm-focus-task-name");

    const previewTaskCheck = root.querySelector(
        ".pm-focus-task-check"
    );

    const startBtn = get("pm-focus-start");
    const startHint = get("pm-focus-start-hint");


    // ACTIVE FOCUS

    const focusScreen = get("pm-focus-screen");

    const activeTime = get("pm-focus-active-time");
    const activeTaskName = get("pm-focus-active-task-name");
    const activeStatus = get("pm-focus-active-status");

    const pauseBtn = get("pm-focus-pause");
    const resumeBtn = get("pm-focus-resume");


    // CONTRAST

    const lightBtn = get("pm-focus-contrast-light");
    const darkBtn = get("pm-focus-contrast-dark");


    // BACKGROUND

    const backgroundImage = get("pm-focus-background-image");
    const backgroundVideo = get("pm-focus-background-video");


    // MUSIC

    const musicName = get("pm-focus-active-music-name");
    const musicToggle = get("pm-focus-music-toggle");


    // EXIT

    const exitBtn = get("pm-focus-exit");
    const exitDialog = get("pm-focus-exit-dialog");

    const keepBtn = get("pm-focus-keep");
    const confirmExitBtn = get("pm-focus-confirm-exit");


    /* ========================================================
       2. KIỂM TRA CÁC PHẦN TỬ HTML
       ======================================================== */

    const required = [
        customField,
        customInput,
        previewTime,
        previewTaskName,
        startBtn,
        startHint,
        focusScreen,
        activeTime,
        activeTaskName,
        activeStatus,
        pauseBtn,
        resumeBtn,
        lightBtn,
        darkBtn,
        backgroundImage,
        backgroundVideo,
        musicName,
        musicToggle,
        exitBtn,
        exitDialog,
        keepBtn,
        confirmExitBtn
    ];

    if (
        durationButtons.length === 0 ||
        required.some(element => !element)
    ) {

        console.warn(
            "In-Focus V2.2: Thiếu phần tử HTML."
        );

        return;
    }

    // Chống khởi tạo Focus Timer nhiều lần.

    if (focusScreen.dataset.initialized === "true") {
        return;
    }

    focusScreen.dataset.initialized = "true";


    /* ========================================================
       3. DIALOG TRONG FULLSCREEN
       ======================================================== */

    if (!focusScreen.contains(exitDialog)) {
        focusScreen.appendChild(exitDialog);
    }


    /* ========================================================
       4. QUẢN LÝ TRẠNG THÁI PHIÊN
       ======================================================== */

    let selectedTask = null;

    let durationMode = "25";
    let sessionMinutes = 25;

    // idle | running | paused | confirming | closing

    let state = "idle";

    let remainingMs = 25 * 60 * 1000;

    let endAt = 0;
    let ticker = null;

    let stateBeforeDialog = "running";

    let closingSession = false;
    let startingSession = false;

    let sessionBackground = null;

    // Trạng thái video trước khi Pause.

    let videoWasPlaying = false;

    // Trạng thái video trước khi mở Exit Dialog.

    let dialogVideoWasPlaying = false;


    /* ========================================================
       5. CÁC HÀM TIỆN ÍCH
       ======================================================== */

    function emitEvent(name, detail = {}) {

        document.dispatchEvent(
            new CustomEvent(name, {
                detail
            })
        );
    }


    function isSessionActive() {

        return (
            state === "running" ||
            state === "paused" ||
            state === "confirming"
        );
    }


    function formatTime(milliseconds) {

        const totalSeconds = Math.max(
            0,
            Math.ceil(milliseconds / 1000)
        );

        const minutes = Math.floor(
            totalSeconds / 60
        );

        const seconds = totalSeconds % 60;

        return (
            String(minutes).padStart(2, "0") +
            ":" +
            String(seconds).padStart(2, "0")
        );
    }


    function getDurationMinutes() {

        if (durationMode !== "custom") {
            return Number(durationMode);
        }

        const raw = customInput.value.trim();

        if (raw === "") {
            return null;
        }

        const minutes = Number(raw);

        if (
            !Number.isInteger(minutes) ||
            minutes < 1 ||
            minutes > 180
        ) {
            return null;
        }

        return minutes;
    }


    /* ========================================================
       6. CẬP NHẬT PREVIEW
       ======================================================== */

    function updatePreview() {

        if (state !== "idle") {
            return;
        }

        const minutes = getDurationMinutes();

        const validDuration = minutes !== null;
        const hasTask = selectedTask !== null;

        previewTime.textContent = validDuration
            ? formatTime(minutes * 60 * 1000)
            : "--:--";

        previewTaskName.textContent = hasTask
            ? selectedTask.name
            : "Chưa chọn nhiệm vụ";

        if (previewTaskCheck) {

            previewTaskCheck.hidden = !hasTask;
        }

        startBtn.disabled = !(
            validDuration &&
            hasTask
        );

        if (!hasTask) {

            startHint.textContent =
                "Chọn một nhiệm vụ trong Pre-Focus " +
                "để bắt đầu phiên học.";

        } else if (!validDuration) {

            startHint.textContent =
                "Nhập thời lượng từ 1 đến 180 phút.";

        } else {

            startHint.textContent =
                "Sẵn sàng bắt đầu phiên tập trung.";
        }
    }


    /* ========================================================
       7. DURATION SELECTOR
       ======================================================== */

    function updateDurationButtons() {

        durationButtons.forEach(button => {

            const selected =
                button.dataset.minutes === durationMode;

            button.classList.toggle(
                "is-selected",
                selected
            );

            button.setAttribute(
                "aria-pressed",
                String(selected)
            );
        });

        customField.hidden =
            durationMode !== "custom";

        updatePreview();
    }


    durationButtons.forEach(button => {

        button.addEventListener("click", () => {

            if (state !== "idle") {
                return;
            }

            durationMode = button.dataset.minutes;

            updateDurationButtons();

            if (durationMode === "custom") {

                customInput.focus();
            }
        });
    });


    customInput.addEventListener("input", () => {

        if (state !== "idle") {
            return;
        }

        updatePreview();
    });


    /* ========================================================
       8. NHẬN TASK TỪ PRE-FOCUS
       ======================================================== */

    document.addEventListener(
        "pomodoro:task-change",
        event => {

            if (state !== "idle") {
                return;
            }

            const task = event.detail;

            if (
                task &&
                task.id != null &&
                typeof task.name === "string" &&
                task.name.trim() !== "" &&
                ["scheduled", "quick"].includes(task.type)
            ) {

                selectedTask = {
                    id: task.id,
                    name: task.name,
                    type: task.type
                };

            } else {

                selectedTask = null;
            }

            updatePreview();
        }
    );


    /* ========================================================
       9. BACKGROUND INTEGRATION
       ======================================================== */

    function setupBackground() {

        const selected = getSelectedBackground();

        sessionBackground = selected
            ? { ...selected }
            : null;

        // Dừng video của phiên trước.

        backgroundVideo.pause();

        backgroundVideo.removeAttribute("src");
        backgroundVideo.load();

        // Reset background.

        backgroundVideo.hidden = true;
        backgroundImage.hidden = false;

        backgroundImage.style.backgroundImage = "";

        if (
            !sessionBackground ||
            !sessionBackground.src
        ) {
            return;
        }

        // Ảnh tĩnh.

        if (sessionBackground.type === "image") {

            backgroundImage.style.backgroundImage =
                `url("${sessionBackground.src}")`;

            backgroundImage.style.backgroundSize = "cover";
            backgroundImage.style.backgroundPosition = "center";
            backgroundImage.style.backgroundRepeat = "no-repeat";

            return;
        }

        // Video nền.

        if (
            sessionBackground.type === "video" ||
            sessionBackground.type === "animated"
        ) {

            backgroundVideo.src = sessionBackground.src;

            backgroundVideo.loop = true;
            backgroundVideo.muted = true;
            backgroundVideo.playsInline = true;

            backgroundVideo.hidden = false;
            backgroundImage.hidden = true;

            backgroundVideo.load();
        }
    }


    /* ========================================================
       10. MUSIC INTEGRATION - PHẦN ĐƯỢC FIX

       PRE-FOCUS:
       - Chọn bài và nghe thử nếu muốn.

       IN-FOCUS:
       - Music Player lấy bài đang được chọn.
       - Không cần đã nghe thử.
       - Bắt đầu phát từ 00:00.
       - Tự động loop khi hết MP3.
       - Nút loa do Music Player quản lý.

       Focus Timer chỉ hiển thị tên bài.
       ======================================================== */

    function setupMusic() {

        const selectedMusic = root.querySelector(
            ".pm-music-picker .pm-music-item.is-selected"
        );

        const selectedName = selectedMusic?.querySelector(
            ".pm-music-details strong"
        );

        musicName.textContent =
            selectedName?.textContent?.trim() ||
            "Chưa chọn nhạc";

        /*
           KHÔNG thực hiện các thao tác sau:

           - Không tìm sessionAudio trong DOM.
           - Không kiểm tra đã nghe thử hay chưa.
           - Không dùng audio.paused để quyết định bật nhạc.
           - Không đặt musicToggle.disabled.
           - Không đăng ký click cho musicToggle.

           music-player.js quản lý nút nhạc và focusAudio.
        */
    }


    /* ========================================================
       11. BACKGROUND VIDEO CONTROL
       ======================================================== */

    async function playBackgroundVideo() {

        if (
            backgroundVideo.hidden ||
            state !== "running"
        ) {
            return;
        }

        try {

            await backgroundVideo.play();

        } catch (error) {

            console.warn(
                "Không thể phát video nền:",
                error
            );
        }
    }


    function pauseBackgroundVideo() {

        if (!backgroundVideo.paused) {

            backgroundVideo.pause();
        }
    }


    /* ========================================================
       12. GLOBAL MEDIA CONTROL

       Focus Timer:
       - Điều khiển video nền.
       - Phát sự kiện Pause/Resume.

       Music Player:
       - Nhận sự kiện.
       - Điều khiển focusAudio.
       ======================================================== */

    function pauseAllMedia() {

        // Dừng video nền.

        pauseBackgroundVideo();

        // Báo Music Player dừng nhạc In-Focus.

        emitEvent(
            "pomodoro:focus-media-pause"
        );
    }


    function resumeAllMedia({
        resumeVideo = true
    } = {}) {

        if (state !== "running") {
            return;
        }

        // Tiếp tục video nếu cần.

        if (resumeVideo) {

            playBackgroundVideo();
        }

        // Báo Music Player tiếp tục nhạc In-Focus.

        emitEvent(
            "pomodoro:focus-media-resume"
        );
    }


    /* ========================================================
       13. CẬP NHẬT ACTIVE FOCUS
       ======================================================== */

    function renderActive() {

        activeTime.textContent =
            formatTime(remainingMs);

        pauseBtn.hidden =
            state !== "running";

        resumeBtn.hidden =
            state !== "paused";

        let statusText = "Đang tập trung";

        if (state === "paused") {

            statusText = "Đã tạm dừng";
        }

        if (state === "confirming") {

            statusText = "Đang xác nhận gác lại";
        }

        if (state === "idle") {

            statusText = "Sẵn sàng tập trung";
        }

        activeStatus.replaceChildren();

        const dot = document.createElement("span");

        dot.className = "pm-focus-status-dot";
        dot.setAttribute(
            "aria-hidden",
            "true"
        );

        activeStatus.append(
            dot,
            document.createTextNode(statusText)
        );
    }


    /* ========================================================
       14. COUNTDOWN ENGINE
       ======================================================== */

    function stopTicker() {

        if (ticker !== null) {

            clearInterval(ticker);

            ticker = null;
        }
    }


    function tick() {

        if (state !== "running") {
            return;
        }

        remainingMs = Math.max(
            0,
            endAt - performance.now()
        );

        renderActive();

        if (remainingMs <= 0) {

            completeSession();
        }
    }


    function startTicker() {

        stopTicker();

        // Không trừ 1000 ms cố định.
        // Tính thời gian còn lại dựa trên performance.now().

        endAt = performance.now() + remainingMs;

        ticker = window.setInterval(
            tick,
            200
        );

        tick();
    }


    /* ========================================================
       15. START SESSION

       MUSIC FIX:
       Sự kiện focus-start được phát trực tiếp từ thao tác
       người dùng trước khi chạy timer và video.

       Nhờ đó Music Player có thể gọi focusAudio.play()
       trong luồng xử lý nút Bắt đầu tập trung.
       ======================================================== */

    function startSession() {

        if (
            state !== "idle" ||
            startingSession
        ) {
            return;
        }

        const minutes = getDurationMinutes();

        if (
            !selectedTask ||
            minutes === null
        ) {

            updatePreview();
            return;
        }

        startingSession = true;

        sessionMinutes = minutes;
        remainingMs = minutes * 60 * 1000;

        // Lấy môi trường Pre-Focus đã chọn.

        setupBackground();
        setupMusic();

        activeTaskName.textContent =
            selectedTask.name;

        state = "running";
        closingSession = false;

        // Hiển thị Active Focus.

        focusScreen.hidden = false;

        focusScreen.classList.add("is-open");

        document.body.classList.add(
            "pm-focus-session-open"
        );

        renderActive();

        /*
           MUSIC FIX:

           Phát sự kiện bắt đầu ngay tại đây.

           music-player.js sẽ:
           - Dừng nhạc nghe thử.
           - Lấy bài đã chọn.
           - Khởi tạo focusAudio từ 00:00.
           - Bật loop.
           - Phát nhạc, dù người dùng chưa từng nghe thử.
           - Cập nhật nút loa In-Focus.

           KHÔNG tự tạo hoặc phát Audio tại file này.
        */

        emitEvent(
            "pomodoro:focus-start",
            {
                task: { ...selectedTask },

                background: sessionBackground
                    ? { ...sessionBackground }
                    : null,

                durationMinutes: sessionMinutes
            }
        );

        // Bắt đầu đồng hồ.

        startTicker();

        // Bắt đầu video nền nếu có.

        playBackgroundVideo();

        // Fullscreen API.

        if (
            typeof focusScreen.requestFullscreen === "function"
        ) {

            try {

                const fullscreenRequest =
                    focusScreen.requestFullscreen();

                if (
                    fullscreenRequest &&
                    typeof fullscreenRequest.catch === "function"
                ) {

                    fullscreenRequest.catch(() => {

                        console.info(
                            "Sử dụng fullscreen dự phòng."
                        );
                    });
                }

            } catch (error) {

                console.info(
                    "Sử dụng fullscreen dự phòng."
                );
            }
        }

        startingSession = false;
    }


    startBtn.addEventListener(
        "click",
        startSession
    );


    /* ========================================================
       16. GLOBAL PAUSE
       ======================================================== */

    function pauseSession() {

        if (state !== "running") {
            return;
        }

        remainingMs = Math.max(
            0,
            endAt - performance.now()
        );

        if (remainingMs <= 0) {

            completeSession();
            return;
        }

        stopTicker();

        // Ghi nhớ video có đang chạy không.

        videoWasPlaying = Boolean(
            !backgroundVideo.hidden &&
            !backgroundVideo.paused
        );

        state = "paused";

        // Dừng video và nhạc In-Focus.

        pauseAllMedia();

        renderActive();

        emitEvent(
            "pomodoro:focus-pause",
            {
                remainingMs
            }
        );
    }


    pauseBtn.addEventListener(
        "click",
        pauseSession
    );


    /* ========================================================
       17. GLOBAL RESUME
       ======================================================== */

    function resumeSession() {

        if (state !== "paused") {
            return;
        }

        state = "running";

        startTicker();

        // Music Player tự kiểm tra nhạc có bật hay không.

        resumeAllMedia({
            resumeVideo: videoWasPlaying
        });

        renderActive();

        emitEvent(
            "pomodoro:focus-resume",
            {
                remainingMs
            }
        );
    }


    resumeBtn.addEventListener(
        "click",
        resumeSession
    );


    /* ========================================================
       18. ADAPTIVE CONTRAST
       ======================================================== */

    function setContrast(mode) {

        const contrast =
            mode === "dark" ? "dark" : "light";

        focusScreen.dataset.contrast = contrast;

        const isLight =
            contrast === "light";

        lightBtn.classList.toggle(
            "is-selected",
            isLight
        );

        darkBtn.classList.toggle(
            "is-selected",
            !isLight
        );

        lightBtn.setAttribute(
            "aria-pressed",
            String(isLight)
        );

        darkBtn.setAttribute(
            "aria-pressed",
            String(!isLight)
        );
    }


    lightBtn.addEventListener("click", () => {

        setContrast("light");
    });


    darkBtn.addEventListener("click", () => {

        setContrast("dark");
    });


    /* ========================================================
       19. MỞ DIALOG GÁC LẠI
       ======================================================== */

    function openExitDialog() {

        if (
            state !== "running" &&
            state !== "paused"
        ) {
            return;
        }

        stateBeforeDialog = state;

        if (state === "running") {

            remainingMs = Math.max(
                0,
                endAt - performance.now()
            );

            if (remainingMs <= 0) {

                completeSession();
                return;
            }

            // Ghi nhớ trạng thái video.

            videoWasPlaying = Boolean(
                !backgroundVideo.hidden &&
                !backgroundVideo.paused
            );
        }

        dialogVideoWasPlaying = videoWasPlaying;

        stopTicker();

        // Dừng nhạc và video khi mở dialog.

        pauseAllMedia();

        state = "confirming";

        renderActive();

        if (
            typeof exitDialog.showModal === "function"
        ) {

            if (!exitDialog.open) {

                exitDialog.showModal();
            }

        } else {

            const confirmed = window.confirm(
                "Bạn muốn gác lại phiên này?"
            );

            if (confirmed) {

                abandonSession();

            } else {

                keepSession();
            }
        }
    }


    exitBtn.addEventListener(
        "click",
        openExitDialog
    );


    /* ========================================================
       20. GIỮ TẬP TRUNG
       ======================================================== */

    function keepSession() {

        if (state !== "confirming") {
            return;
        }

        if (exitDialog.open) {

            exitDialog.close();
        }

        if (stateBeforeDialog === "running") {

            state = "running";

            startTicker();

            // Tiếp tục nhạc / video nếu phiên trước đang chạy.

            resumeAllMedia({
                resumeVideo: dialogVideoWasPlaying
            });

        } else {

            // Trước dialog đang Pause thì giữ nguyên Pause.

            state = "paused";
        }

        renderActive();
    }


    keepBtn.addEventListener(
        "click",
        keepSession
    );


    /* ========================================================
       21. ĐÓNG ACTIVE FOCUS
       ======================================================== */

    async function closeFocusScreen() {

        closingSession = true;

        stopTicker();

        // Gửi tín hiệu dừng nhạc.

        pauseAllMedia();

        pauseBackgroundVideo();

        if (exitDialog.open) {

            exitDialog.close();
        }

        if (
            document.fullscreenElement === focusScreen
        ) {

            try {

                await document.exitFullscreen();

            } catch (error) {

                console.warn(
                    "Không thể thoát Fullscreen:",
                    error
                );
            }
        }

        focusScreen.classList.remove(
            "is-open"
        );

        focusScreen.hidden = true;

        document.body.classList.remove(
            "pm-focus-session-open"
        );

        closingSession = false;
    }


    /* ========================================================
       22. GÁC LẠI PHIÊN
       ======================================================== */

    async function abandonSession() {

        if (
            state === "idle" ||
            state === "closing"
        ) {
            return;
        }

        const abandonedTask =
            selectedTask ? { ...selectedTask } : null;

        state = "closing";

        await closeFocusScreen();

        state = "idle";

        remainingMs =
            sessionMinutes * 60 * 1000;

        updatePreview();
        renderActive();

        // Music Player nhận sự kiện để dừng và reset nhạc.

        emitEvent(
            "pomodoro:focus-abandon",
            {
                task: abandonedTask,
                recorded: false
            }
        );
    }


    confirmExitBtn.addEventListener(
        "click",
        abandonSession
    );


    /* ========================================================
       23. HOÀN THÀNH PHIÊN
       ======================================================== */

    async function completeSession() {

        if (state !== "running") {
            return;
        }

        stopTicker();

        remainingMs = 0;

        renderActive();

        const result = {

            task: selectedTask
                ? { ...selectedTask }
                : null,

            background: sessionBackground
                ? { ...sessionBackground }
                : null,

            durationMinutes: sessionMinutes,

            completed: true,

            completedAt: new Date().toISOString()
        };

        state = "closing";

        await closeFocusScreen();

        state = "idle";

        remainingMs =
            sessionMinutes * 60 * 1000;

        updatePreview();
        renderActive();

        // Music Player nhận sự kiện để dừng và reset nhạc.

        emitEvent(
            "pomodoro:focus-complete",
            result
        );
    }


    /* ========================================================
       24. FULLSCREEN CHANGE / ESC
       ======================================================== */

    document.addEventListener(
        "fullscreenchange",
        () => {

            if (
                closingSession ||
                !isSessionActive()
            ) {
                return;
            }

            // Nếu đang chạy mà người dùng thoát fullscreen
            // bằng Escape, hỏi xác nhận trước khi gác lại.

            if (
                document.fullscreenElement !== focusScreen &&
                state !== "confirming"
            ) {

                openExitDialog();
            }
        }
    );


    /* ========================================================
       25. ESC KHI DIALOG ĐANG MỞ
       ======================================================== */

    exitDialog.addEventListener(
        "cancel",
        event => {

            event.preventDefault();

            keepSession();
        }
    );


    /* ========================================================
       26. TAB VISIBILITY
       ======================================================== */

    document.addEventListener(
        "visibilitychange",
        () => {

            if (
                document.visibilityState === "visible" &&
                state === "running"
            ) {

                tick();
            }
        }
    );


    /* ========================================================
       27. KHỞI TẠO
       ======================================================== */

    setContrast("light");

    updateDurationButtons();

    renderActive();

    console.log(
        "Pomodoro In-Focus V2.2 - Music Event Fix initialized"
    );
}
