
/* ============================================================
   AI STUDYPLANNER
   POMODORO WORKSPACE 2.0

   APP INITIALIZATION - V19
   C4.2 - HEATMAP BACKEND INTEGRATION

   CÁC MODULE ĐƯỢC GIỮ NGUYÊN:

   01. Focus Timer V2.2
   02. Task Selector V13 - Django Integration
   03. Background Picker V2
   04. Music Player - Music Event Fix
   05. Layout Height Sync
   06. Session Summary / Celebration Sheet
   07. Heatmap Timeline V2.3
   08. Session Recorder V2 - C2.3.3
   09. Statistics Controller - C3.3

   BỔ SUNG C4.2:

   10. Heatmap Backend Controller
       GET /api/pomodoro-heatmap/

   NGUYÊN TẮC:

   - Không thay đổi Countdown Engine.
   - Không thay đổi Task Selector.
   - Không thay đổi Music Player.
   - Không thay đổi Celebration Sheet.
   - Không thay đổi giao diện HTML/CSS.
   - Không ảnh hưởng các module khác.
   ============================================================ */


// ============================================================
// 01. IMPORT MODULES
// ============================================================


// ------------------------------------------------------------
// A. TASK SELECTOR V13 - DJANGO INTEGRATION
//
// Đọc Scheduled Task thật từ Django Template.
// Giữ cơ chế khóa Scheduled Task và Quick Goal.
// ------------------------------------------------------------

import {
    initTaskSelector
} from "./task-selector.js?v=20261015-c232";


// ------------------------------------------------------------
// B. BACKGROUND PICKER V2
// ------------------------------------------------------------

import {
    initBackgroundPicker
} from "./background-picker.js";


// ------------------------------------------------------------
// C. MUSIC PLAYER - MUSIC EVENT FIX
//
// QUAN TRỌNG:
// Giữ nguyên tuyệt đối đường dẫn import này.
// ------------------------------------------------------------

import {
    initMusicPlayer
} from "./music-player.js?v=20261014-music-fix";


// ------------------------------------------------------------
// D. LAYOUT HEIGHT SYNC
// ------------------------------------------------------------

import {
    initLayoutHeightSync
} from "./layout-height-sync.js";


// ------------------------------------------------------------
// E. FOCUS TIMER V2.2
// ------------------------------------------------------------

import {
    initFocusTimer
} from "./focus-timer.js";


// ------------------------------------------------------------
// F. SESSION SUMMARY / CELEBRATION SHEET
// ------------------------------------------------------------

import {
    initSessionSummary
} from "./session-summary.js";


// ------------------------------------------------------------
// G. POST-FOCUS HEATMAP TIMELINE V2.3
//
// Giữ nguyên:
/// - Timeline 12 tháng
//  - Thứ Hai đến Chủ nhật
//  - Tổng phút theo tuần
//  - Cuộn ngang
//  - Tooltip chỉ cho ngày có hoạt động
// ------------------------------------------------------------

import {
    initHeatmap
} from "./heatmap.js?v=20261015-timeline-v23";


// ------------------------------------------------------------
// H. SESSION RECORDER V2 - C2.3.3
//
// POST /api/save-pomodoro/
//
// Ghi nhận:
// - session_uuid
// - task_id
// - quick_goal_title
// - completed / deferred
// - duration_minutes
// - actual_seconds
// - remaining_seconds
// ------------------------------------------------------------

import {
    initSessionRecorder
} from "./session-recorder.js?v=20261015-c234";


// ------------------------------------------------------------
// I. STATISTICS CONTROLLER - C3.3
//
// GET /api/pomodoro-statistics/
//
// Hiển thị:
// - Tổng thời gian tập trung
// - Phiên đã hoàn thành
// - Chuỗi ngày tập trung
//
// Tự cập nhật sau pomodoro:session-saved.
// ------------------------------------------------------------

import {
    initStatistics
} from "./statistics.js?v=20261015-c33";


// ------------------------------------------------------------
// J. HEATMAP BACKEND CONTROLLER - C4.2
//
// GET /api/pomodoro-heatmap/
//
// Controller nhận JSON từ Django và truyền vào
// setHeatmapData() của Heatmap Timeline V2.3.
//
// QUAN TRỌNG:
// heatmap-controller.js cũng phải import
// heatmap.js?v=20261015-timeline-v23
// để sử dụng cùng một module state.
// ------------------------------------------------------------

import {
    initHeatmapController
} from "./heatmap-controller.js?v=20261015-c42";


// ============================================================
// 02. APP INITIALIZATION
// ============================================================

function initPomodoro() {

    // --------------------------------------------------------
    // A. TÌM ROOT APPLICATION
    // --------------------------------------------------------

    const app = document.getElementById(
        "pomodoro-app"
    );

    if (!app) {
        return;
    }

    // --------------------------------------------------------
    // B. CHỐNG KHỞI TẠO NHIỀU LẦN
    // --------------------------------------------------------

    if (app.dataset.initialized === "true") {
        return;
    }


    // ========================================================
    // 01. FOCUS TIMER V2.2
    // ========================================================

    initFocusTimer();


    // ========================================================
    // 02. TASK SELECTOR V13
    // ========================================================

    initTaskSelector();


    // ========================================================
    // 03. BACKGROUND PICKER V2
    // ========================================================

    initBackgroundPicker();


    // ========================================================
    // 04. MUSIC PLAYER - MUSIC EVENT FIX
    //
    // Giữ nguyên thứ tự khởi tạo và console log
    // để kiểm tra Music Integration.
    // ========================================================

    console.log(
        "[APP] Chuẩn bị khởi tạo Music Player..."
    );

    console.log(
        "[APP] Phiên bản hàm Music Player:",
        initMusicPlayer.toString().slice(0, 180)
    );

    initMusicPlayer();

    console.log(
        "[APP] Đã gọi initMusicPlayer()."
    );


    // ========================================================
    // 05. LAYOUT HEIGHT SYNC
    // ========================================================

    initLayoutHeightSync();


    // ========================================================
    // 06. SESSION SUMMARY / CELEBRATION SHEET
    // ========================================================

    initSessionSummary();


    // ========================================================
    // 07. HEATMAP TIMELINE V2.3
    //
    // Khởi tạo cấu trúc Timeline.
    // Controller sẽ tải dữ liệu sau.
    // ========================================================

    initHeatmap();


    // ========================================================
    // 08. SESSION RECORDER - C2.3.3
    //
    // Lắng nghe các sự kiện:
    // - pomodoro:task-change
    // - pomodoro:focus-start
    // - pomodoro:focus-pause
    // - pomodoro:focus-resume
    // - pomodoro:focus-media-pause
    // - pomodoro:focus-media-resume
    // - pomodoro:focus-complete
    // - pomodoro:focus-abandon
    //
    // Khi Backend lưu thành công:
    // - Phát pomodoro:session-saved
    // ========================================================

    initSessionRecorder();


    // ========================================================
    // 09. STATISTICS CONTROLLER - C3.3
    //
    // Khi mở trang:
    // GET /api/pomodoro-statistics/
    //
    // Khi lưu phiên thành công:
    // Cập nhật ba thẻ Statistics.
    // ========================================================

    initStatistics();


    // ========================================================
    // 10. HEATMAP BACKEND CONTROLLER - C4.2
    //
    // Khi mở trang:
    // GET /api/pomodoro-heatmap/
    //
    // Khi lưu phiên thành công:
    // Tự tải lại dữ liệu theo ngày.
    //
    // Giữ nguyên Timeline V2.3.
    // ========================================================

    initHeatmapController();


    // ========================================================
    // 11. COMPLETE INITIALIZATION
    // ========================================================

    app.dataset.initialized = "true";

    console.log(
        "Pomodoro Workspace 2.0 - V19 initialized"
    );
}


// ============================================================
// 03. DOM READY
// ============================================================

if (document.readyState === "loading") {

    document.addEventListener(
        "DOMContentLoaded",
        initPomodoro,
        {
            once: true
        }
    );

} else {

    initPomodoro();
}
