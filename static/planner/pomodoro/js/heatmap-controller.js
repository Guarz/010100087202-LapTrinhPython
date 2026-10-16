
/* ============================================================
   AI STUDYPLANNER
   POMODORO WORKSPACE 2.0

   C4.2 - HEATMAP BACKEND CONTROLLER V1

   CHỨC NĂNG:
   01. Lấy dữ liệu Heatmap từ Django Backend
   02. Chỉ nhận dữ liệu phiên hoàn thành
   03. Giữ nguyên Heatmap Timeline V2.3
   04. Tự cập nhật khi lưu phiên thành công
   05. Không thay đổi HTML/CSS
   06. Không ghi dữ liệu vào database

   API:
   GET /api/pomodoro-heatmap/

   EVENT:
   pomodoro:session-saved

   MODULE:
   heatmap.js V2.3
   ============================================================ */


// ============================================================
// 01. IMPORT HEATMAP MODULE
// ============================================================

// Phải sử dụng cùng URL import với app.js V19.
// Tránh tạo hai instance Heatmap khác nhau.

import {
    setHeatmapData
} from "./heatmap.js?v=20261015-timeline-v23";


// ============================================================
// 02. MODULE STATE
// ============================================================

let heatmapControllerInitialized = false;

const HEATMAP_API_URL = "/api/pomodoro-heatmap/";

// Ngăn response cũ ghi đè dữ liệu của request mới.
let latestRequestId = 0;


// ============================================================
// 03. FETCH HEATMAP DATA
// ============================================================

async function fetchHeatmapData() {

    const response = await fetch(
        HEATMAP_API_URL,
        {
            method: "GET",

            credentials: "same-origin",

            cache: "no-store",

            headers: {
                "Accept": "application/json"
            }
        }
    );

    // --------------------------------------------------------
    // A. KIỂM TRA CONTENT TYPE
    // --------------------------------------------------------

    const contentType = (
        response.headers.get("content-type") || ""
    );

    if (!contentType.includes("application/json")) {

        throw new Error(
            "Heatmap API không trả về JSON. " +
            "Hãy kiểm tra trạng thái đăng nhập."
        );
    }

    // --------------------------------------------------------
    // B. ĐỌC JSON
    // --------------------------------------------------------

    const result = await response.json();

    // --------------------------------------------------------
    // C. KIỂM TRA HTTP STATUS
    // --------------------------------------------------------

    if (!response.ok) {

        throw new Error(
            result?.message ||
            `Heatmap API lỗi HTTP ${response.status}.`
        );
    }

    // --------------------------------------------------------
    // D. KIỂM TRA CẤU TRÚC DỮ LIỆU
    // --------------------------------------------------------

    if (
        result?.status !== "success" ||
        !Array.isArray(result?.data?.days)
    ) {

        throw new Error(
            "Dữ liệu Heatmap API không hợp lệ."
        );
    }

    return result.data.days;
}


// ============================================================
// 04. REFRESH HEATMAP
// ============================================================

async function refreshHeatmap() {

    // Mỗi lần gọi có một ID tăng dần.
    const requestId = ++latestRequestId;

    try {

        // ----------------------------------------------------
        // A. LẤY DỮ LIỆU BACKEND
        // ----------------------------------------------------

        const days = await fetchHeatmapData();

        // ----------------------------------------------------
        // B. NGĂN RESPONSE CŨ GHI ĐÈ
        // ----------------------------------------------------

        if (requestId !== latestRequestId) {
            return;
        }

        // ----------------------------------------------------
        // C. CẬP NHẬT HEATMAP V2.3
        // ----------------------------------------------------

        setHeatmapData(days);

        console.info(
            "[Heatmap Controller] Đã tải dữ liệu:",
            days.length,
            "ngày"
        );

    } catch (error) {

        if (requestId !== latestRequestId) {
            return;
        }

        console.error(
            "[Heatmap Controller] Lỗi tải dữ liệu:",
            error
        );
    }
}


// ============================================================
// 05. INITIALIZATION
// ============================================================

export function initHeatmapController() {

    // --------------------------------------------------------
    // A. CHỐNG KHỞI TẠO NHIỀU LẦN
    // --------------------------------------------------------

    if (heatmapControllerInitialized) {
        return;
    }

    // --------------------------------------------------------
    // B. KIỂM TRA ROOT ELEMENT
    // --------------------------------------------------------

    const root = document.getElementById(
        "pm-focus-heatmap"
    );

    if (!root) {

        console.warn(
            "[Heatmap Controller] Không tìm thấy Heatmap."
        );

        return;
    }

    // --------------------------------------------------------
    // C. ĐÁNH DẤU KHỞI TẠO
    // --------------------------------------------------------

    heatmapControllerInitialized = true;

    // --------------------------------------------------------
    // D. LẤY DỮ LIỆU LẦN ĐẦU
    // --------------------------------------------------------

    void refreshHeatmap();

    // --------------------------------------------------------
    // E. LẮNG NGHE PHIÊN ĐÃ LƯU
    //
    // Session Recorder phát sự kiện sau khi
    // Django xác nhận lưu thành công.
    //
    // Chỉ khi lưu thành công mới làm mới Heatmap.
    // Backend tự lọc phiên completed.
    // --------------------------------------------------------

    document.addEventListener(
        "pomodoro:session-saved",
        () => {
            void refreshHeatmap();
        }
    );

    // --------------------------------------------------------
    // F. LOG
    // --------------------------------------------------------

    console.info(
        "[Heatmap Controller] C4.2 đã khởi tạo."
    );
}
