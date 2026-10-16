
/* ============================================================
   POMODORO WORKSPACE 2.0
   MUSIC PLAYER - PRE-FOCUS / IN-FOCUS

   PRE-FOCUS:
   - Chọn nhạc.
   - Nghe thử nếu muốn.
   - Không lặp bản nghe thử.
   - Giữ nguyên giao diện hiện tại.

   IN-FOCUS:
   - Lấy bài đã chọn ở Pre-Focus.
   - Không phụ thuộc việc có nghe thử hay không.
   - Dừng nghe thử khi bắt đầu phiên.
   - Phát lại bài đã chọn từ 00:00.
   - Loop liên tục khi bài MP3 kết thúc.
   - Bật/tắt nhạc độc lập với đồng hồ.
   - Pause/Resume theo trạng thái phiên.
   - Gác lại/hoàn thành: dừng nhạc.

   Không thay đổi Task, Background, Timer, Layout.
   ============================================================ */


// ============================================================
// 1. MUSIC LIBRARY
// ============================================================

const musicBase = "/static/planner/pomodoro/media/music/";

const songs = [
    {
        id: "lofi",
        name: "Midnight Lo-fi",
        genre: "Lo-fi · Chill beats",
        color: "#557FA0",
        filename: "midnight-lofi.mp3"
    },
    {
        id: "rain",
        name: "Rainy Afternoon",
        genre: "Nature · Ambient",
        color: "#66888D",
        filename: "rainy-afternoon.mp3"
    },
    {
        id: "piano",
        name: "Coffee & Piano",
        genre: "Piano · Instrumental",
        color: "#B18360",
        filename: "coffee-piano.mp3"
    },
    {
        id: "jazz",
        name: "Slow Jazz Nights",
        genre: "Jazz · Relax",
        color: "#856B91",
        filename: "slow-jazz.mp3"
    },
    {
        id: "none",
        name: "Không phát nhạc",
        genre: "Không gian yên tĩnh",
        color: "#7F8A95",
        filename: null
    }
];


// ============================================================
// 2. MODULE INITIALIZATION
// ============================================================

let musicPlayerInitialized = false;


export function initMusicPlayer() {

    // Log ngay khi hàm được gọi, trước mọi điều kiện return.
    console.log("[Music Player] initMusicPlayer() called");

    if (musicPlayerInitialized) {

        console.info(
            "[Music Player] Đã khởi tạo trước đó."
        );

        return;
    }


    // ========================================================
    // 3. HTML ELEMENTS
    // ========================================================

    const get = id => document.getElementById(id);

    const trigger = get("pm-music-trigger");
    const library = get("pm-music-library");
    const list = get("pm-music-list");

    const cover = get("pm-music-cover");
    const title = get("pm-music-title");
    const subtitle = get("pm-music-subtitle");

    const player = get("pm-mini-player");
    const playBtn = get("pm-music-play");
    const playerTitle = get("pm-player-title");

    const progress = get("pm-music-progress");
    const currentTime = get("pm-current-time");
    const totalTime = get("pm-total-time");
    const message = get("pm-music-message");

    const focusMusicToggle = get("pm-focus-music-toggle");
    const focusMusicName = get("pm-focus-active-music-name");

    const required = {
        trigger,
        library,
        list,
        cover,
        title,
        subtitle,
        player,
        playBtn,
        playerTitle,
        progress,
        currentTime,
        totalTime,
        message
    };

    const missing = Object.entries(required)
        .filter(([, element]) => element === null)
        .map(([name]) => name);

    if (missing.length > 0) {

        console.error(
            "[Music Player] Thiếu HTML Pre-Focus:",
            missing
        );

        return;
    }

    if (!focusMusicToggle) {

        console.error(
            "[Music Player] Không tìm thấy #pm-focus-music-toggle."
        );

        // Vẫn cho phép sử dụng Pre-Focus.
        // Không làm hỏng chức năng nghe thử.
    }


    // ========================================================
    // 4. TWO SEPARATE AUDIO OBJECTS
    // ========================================================

    // Audio chỉ dành cho nghe thử ở Pre-Focus.
    const previewAudio = new Audio();

    previewAudio.preload = "metadata";
    previewAudio.loop = false;


    // Audio chỉ dành cho phiên In-Focus.
    const focusAudio = new Audio();

    focusAudio.preload = "auto";
    focusAudio.loop = true;
    focusAudio.muted = false;
    focusAudio.volume = 1;


    // ========================================================
    // 5. STATE
    // ========================================================

    let selectedId = "lofi";

    let focusActive = false;
    let focusPaused = false;
    let focusMusicEnabled = false;

    // Bài nhạc được chốt khi bắt đầu Focus.
    let focusSong = null;

    // Chặn kết quả phát cũ cập nhật nhầm phiên mới.
    let previewRequestId = 0;
    let focusRequestId = 0;


    // ========================================================
    // 6. HELPERS
    // ========================================================

    function getSelectedSong() {

        return songs.find(song => song.id === selectedId)
            || null;
    }


    function getMusicUrl(song) {

        if (!song?.filename) {
            return null;
        }

        return musicBase + song.filename;
    }


    function formatTime(seconds) {

        if (
            !Number.isFinite(seconds) ||
            seconds < 0
        ) {
            return "0:00";
        }

        const minutes = Math.floor(seconds / 60);
        const remainder = Math.floor(seconds % 60);

        return (
            `${minutes}:${String(remainder).padStart(2, "0")}`
        );
    }


    function resetAudioTime(audio) {

        try {

            audio.currentTime = 0;

        } catch (error) {

            // Audio chưa tải đủ metadata.
        }
    }


    function setPlaying(value) {

        playBtn.innerHTML = value
            ? '<i class="fa-solid fa-pause"></i>'
            : '<i class="fa-solid fa-play"></i>';

        playBtn.setAttribute(
            "aria-label",
            value
                ? "Tạm dừng nghe thử"
                : "Phát nhạc nghe thử"
        );
    }


    function toggleLibrary(open) {

        library.hidden = !open;

        trigger.setAttribute(
            "aria-expanded",
            String(open)
        );
    }


    function emitMusicChange(song) {

        trigger.dispatchEvent(
            new CustomEvent(
                "pomodoro:music-change",
                {
                    bubbles: true,
                    detail: {
                        id: song.id
                    }
                }
            )
        );
    }


    // ========================================================
    // 7. RENDER PRE-FOCUS MUSIC LIBRARY
    // ========================================================

    function renderMusicList() {

        list.replaceChildren();

        songs.forEach(song => {

            const button = document.createElement("button");

            button.type = "button";
            button.className = "pm-music-item";

            const selected = song.id === selectedId;

            if (selected) {
                button.classList.add("is-selected");
            }

            button.setAttribute(
                "aria-pressed",
                String(selected)
            );

            button.innerHTML = `
                <span class="pm-music-art"
                      style="background:${song.color}">
                    <i class="fa-solid ${
                        song.id === "none"
                            ? "fa-volume-xmark"
                            : "fa-compact-disc"
                    }"></i>
                </span>

                <span class="pm-music-details">
                    <strong>${song.name}</strong>
                    <small>${song.genre}</small>
                </span>

                <i class="fa-solid ${
                    selected
                        ? "fa-circle-check"
                        : "fa-circle-play"
                }"></i>
            `;

            button.addEventListener("click", () => {

                if (focusActive) {
                    return;
                }

                selectSong(song.id, true);

                toggleLibrary(false);
                trigger.focus();
            });

            list.appendChild(button);
        });
    }


    // ========================================================
    // 8. PRE-FOCUS: SELECT SONG
    // ========================================================

    function selectSong(id, autoPreview = false) {

        if (focusActive) {
            return;
        }

        const song = songs.find(item => item.id === id);

        if (!song) {
            return;
        }

        // Dừng bản nghe thử cũ.
        pausePreview();

        previewAudio.removeAttribute("src");
        previewAudio.load();

        selectedId = song.id;

        setPlaying(false);

        title.textContent = song.name;

        subtitle.textContent =
            `${song.genre} · Đã chọn`;

        playerTitle.textContent = song.name;

        cover.style.background = song.color;

        trigger.dataset.musicId = song.id;

        progress.value = 0;
        progress.disabled = true;

        currentTime.textContent = "0:00";
        totalTime.textContent = "0:00";

        if (song.filename) {

            previewAudio.src = getMusicUrl(song);
            previewAudio.load();

            player.hidden = false;

            message.textContent =
                "Chọn Play hoặc chọn bài để nghe thử.";

        } else {

            player.hidden = true;

            message.textContent =
                "Đã chọn không phát nhạc.";
        }

        renderMusicList();

        emitMusicChange(song);

        // Giữ hành vi cũ: chọn bài có thể nghe thử.
        // Nhưng nghe thử không phải điều kiện của Focus.
        if (autoPreview && song.filename) {
            playPreview();
        }
    }


    // ========================================================
    // 9. PRE-FOCUS: PREVIEW PLAYBACK
    // ========================================================

    async function playPreview() {

        const song = getSelectedSong();

        if (
            focusActive ||
            !song?.filename
        ) {
            return;
        }

        const requestId = ++previewRequestId;

        try {

            await previewAudio.play();

            if (
                requestId !== previewRequestId ||
                focusActive
            ) {
                if (focusActive) {
                    previewAudio.pause();
                }

                return;
            }

            setPlaying(true);

            message.textContent = "Đang nghe thử.";

        } catch (error) {

            if (
                requestId !== previewRequestId ||
                focusActive
            ) {
                return;
            }

            setPlaying(false);

            message.textContent =
                "Chưa phát được nhạc. Hãy kiểm tra file âm thanh.";

            console.warn(
                "[Pre-Focus] Không phát được nhạc nghe thử:",
                error
            );
        }
    }


    function pausePreview() {

        previewRequestId++;

        previewAudio.pause();
    }


    function stopPreview() {

        pausePreview();

        resetAudioTime(previewAudio);

        setPlaying(false);

        progress.value = 0;
        currentTime.textContent = "0:00";
    }


    trigger.addEventListener("click", () => {

        if (focusActive) {
            return;
        }

        toggleLibrary(library.hidden);
    });


    playBtn.addEventListener("click", () => {

        if (focusActive) {
            return;
        }

        if (previewAudio.paused) {

            playPreview();

        } else {

            pausePreview();
        }
    });


    // ========================================================
    // 10. PRE-FOCUS AUDIO EVENTS
    // ========================================================

    previewAudio.addEventListener("play", () => {

        if (focusActive) {

            previewAudio.pause();
            return;
        }

        setPlaying(true);

        message.textContent = "Đang nghe thử.";
    });


    previewAudio.addEventListener("pause", () => {

        setPlaying(false);

        if (
            !focusActive &&
            getSelectedSong()?.filename
        ) {

            message.textContent =
                "Đã tạm dừng nghe thử.";
        }
    });


    previewAudio.addEventListener("loadedmetadata", () => {

        if (!Number.isFinite(previewAudio.duration)) {
            return;
        }

        progress.max = previewAudio.duration;
        progress.disabled = false;

        totalTime.textContent =
            formatTime(previewAudio.duration);
    });


    previewAudio.addEventListener("timeupdate", () => {

        if (!Number.isFinite(previewAudio.currentTime)) {
            return;
        }

        progress.value = previewAudio.currentTime;

        currentTime.textContent =
            formatTime(previewAudio.currentTime);
    });


    progress.addEventListener("input", () => {

        if (focusActive) {
            return;
        }

        if (Number.isFinite(previewAudio.duration)) {

            previewAudio.currentTime =
                Number(progress.value);
        }
    });


    previewAudio.addEventListener("ended", () => {

        setPlaying(false);

        if (!focusActive) {

            message.textContent =
                "Đã kết thúc bản nghe thử.";
        }
    });


    previewAudio.addEventListener("error", () => {

        if (!previewAudio.getAttribute("src")) {
            return;
        }

        setPlaying(false);

        if (!focusActive) {

            message.textContent =
                "Không tìm thấy hoặc không đọc được file nhạc.";
        }

        console.error(
            "[Pre-Focus] Lỗi tải MP3:",
            previewAudio.currentSrc || previewAudio.src
        );
    });


    // ========================================================
    // 11. IN-FOCUS: MUSIC BUTTON STATE
    // ========================================================

    function updateFocusMusicButton() {

        if (!focusMusicToggle) {
            return;
        }

        // Dùng bài đã chốt cho phiên hiện tại.
        const hasMusic = Boolean(
            focusActive &&
            focusSong?.filename
        );

        const enabled = Boolean(
            hasMusic &&
            focusMusicEnabled
        );

        focusMusicToggle.disabled = !hasMusic;

        focusMusicToggle.setAttribute(
            "aria-pressed",
            String(enabled)
        );

        focusMusicToggle.setAttribute(
            "aria-label",
            !hasMusic
                ? "Không có nhạc nền"
                : enabled
                    ? "Tắt nhạc nền"
                    : "Bật nhạc nền"
        );

        const icon = focusMusicToggle.querySelector("i");

        if (icon) {

            icon.className = enabled
                ? "fa-solid fa-volume-high"
                : "fa-solid fa-volume-xmark";
        }
    }


    // ========================================================
    // 12. IN-FOCUS: PAUSE AUDIO
    // ========================================================

    function pauseFocusAudio() {

        focusRequestId++;

        focusAudio.pause();
    }


    // ========================================================
    // 13. IN-FOCUS: PLAY AUDIO
    // ========================================================

    async function playFocusAudio() {

        if (
            !focusActive ||
            focusPaused ||
            !focusMusicEnabled ||
            !focusAudio.getAttribute("src")
        ) {
            return;
        }

        const requestId = ++focusRequestId;

        try {

            await focusAudio.play();

            if (
                requestId !== focusRequestId ||
                !focusActive ||
                focusPaused ||
                !focusMusicEnabled
            ) {
                return;
            }

            console.log(
                "[In-Focus] Nhạc đang phát:",
                focusSong?.name
            );

        } catch (error) {

            if (requestId !== focusRequestId) {
                return;
            }

            console.error(
                "[In-Focus] Phát nhạc thất bại:",
                error.name,
                error.message
            );

            console.error(
                "[In-Focus] Đường dẫn MP3:",
                focusAudio.currentSrc || focusAudio.src
            );

            // Không tự chuyển ý định người dùng thành tắt nhạc.
            updateFocusMusicButton();
        }
    }


    // ========================================================
    // 14. IN-FOCUS: START MUSIC
    // ========================================================

    function startFocusPlayback() {

        // Lấy bài đã chọn, không lấy thời gian nghe thử.
        const selectedSong = getSelectedSong();

        // Dừng trailer.
        stopPreview();

        // Dừng nhạc phiên cũ.
        pauseFocusAudio();

        focusAudio.removeAttribute("src");

        focusActive = true;
        focusPaused = false;

        // Chốt bài nhạc cho toàn bộ phiên này.
        focusSong = selectedSong
            ? { ...selectedSong }
            : null;

        // Có bài thì bật nhạc mặc định.
        // Không quan tâm người dùng đã nghe thử hay chưa.
        focusMusicEnabled = Boolean(focusSong?.filename);

        focusAudio.loop = true;
        focusAudio.muted = false;
        focusAudio.volume = 1;

        // Cập nhật tên bài nhạc In-Focus nếu có element.
        if (focusMusicName) {

            focusMusicName.textContent =
                focusSong?.name || "Không phát nhạc";
        }

        if (!focusSong?.filename) {

            focusAudio.load();

            updateFocusMusicButton();

            console.log(
                "[In-Focus] Phiên không phát nhạc."
            );

            return;
        }

        // Nạp đúng bài đã chọn, bắt đầu từ đầu.
        focusAudio.src = getMusicUrl(focusSong);

        updateFocusMusicButton();

        console.log(
            "[In-Focus] Bắt đầu bài:",
            focusSong.name
        );

        // Focus Timer phát sự kiện từ nút Bắt đầu tập trung.
        // Phát ngay trong quá trình xử lý sự kiện đó.
        playFocusAudio();
    }


    document.addEventListener(
        "pomodoro:focus-start",
        startFocusPlayback
    );


    // ========================================================
    // 15. IN-FOCUS: GLOBAL PAUSE
    // ========================================================

    document.addEventListener(
        "pomodoro:focus-media-pause",
        () => {

            if (!focusActive) {
                return;
            }

            focusPaused = true;

            pauseFocusAudio();
        }
    );


    // ========================================================
    // 16. IN-FOCUS: GLOBAL RESUME
    // ========================================================

    document.addEventListener(
        "pomodoro:focus-media-resume",
        () => {

            if (!focusActive) {
                return;
            }

            focusPaused = false;

            if (focusMusicEnabled) {
                playFocusAudio();
            }
        }
    );


    // ========================================================
    // 17. IN-FOCUS: MUSIC ON / OFF
    // ========================================================

    if (focusMusicToggle) {

        focusMusicToggle.addEventListener(
            "click",
            () => {

                if (
                    !focusActive ||
                    focusPaused ||
                    !focusSong?.filename
                ) {
                    return;
                }

                focusMusicEnabled = !focusMusicEnabled;

                updateFocusMusicButton();

                if (focusMusicEnabled) {

                    // Bật lại từ vị trí đã dừng.
                    playFocusAudio();

                } else {

                    // Tắt, nhưng giữ thời gian phát nhạc.
                    pauseFocusAudio();
                }
            }
        );
    }


    // ========================================================
    // 18. IN-FOCUS: STOP MUSIC
    // ========================================================

    function stopFocusPlayback() {

        if (!focusActive) {
            return;
        }

        pauseFocusAudio();

        resetAudioTime(focusAudio);

        focusAudio.removeAttribute("src");
        focusAudio.load();

        focusActive = false;
        focusPaused = false;
        focusMusicEnabled = false;
        focusSong = null;

        updateFocusMusicButton();

        console.log(
            "[In-Focus] Đã dừng nhạc của phiên."
        );
    }


    document.addEventListener(
        "pomodoro:focus-abandon",
        stopFocusPlayback
    );


    document.addEventListener(
        "pomodoro:focus-complete",
        stopFocusPlayback
    );


    // ========================================================
    // 19. IN-FOCUS AUDIO EVENTS
    // ========================================================

    focusAudio.addEventListener("playing", () => {

        console.log(
            "[In-Focus] Audio đang phát thực tế:",
            {
                song: focusSong?.name,
                currentTime: focusAudio.currentTime,
                paused: focusAudio.paused,
                muted: focusAudio.muted,
                volume: focusAudio.volume,
                loop: focusAudio.loop
            }
        );
    });


    focusAudio.addEventListener("error", () => {

        if (!focusAudio.getAttribute("src")) {
            return;
        }

        console.error(
            "[In-Focus] Không tải được MP3:",
            {
                url: focusAudio.currentSrc || focusAudio.src,
                errorCode: focusAudio.error?.code
            }
        );
    });


    // ========================================================
    // 20. PAGE LIFECYCLE
    // ========================================================

    window.addEventListener("pagehide", () => {

        pausePreview();
        pauseFocusAudio();
    });


    // ========================================================
    // 21. INITIALIZE
    // ========================================================

    selectSong("lofi", false);

    updateFocusMusicButton();

    musicPlayerInitialized = true;

    console.log(
        "[Music Player] Initialized successfully - Preview + Focus"
    );
}
