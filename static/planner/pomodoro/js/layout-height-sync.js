
/* =====================================================
   POMODORO - LAYOUT HEIGHT SYNC V11

   Layout 1 là nguồn quyết định chiều cao.
   Layout 2 tự đồng bộ theo Layout 1.

   Không thay đổi logic Task, Background, Music.
   ===================================================== */

export function initLayoutHeightSync() {

    const taskCard = document.querySelector(
        "#pomodoro-app .pm-task-card"
    );

    const environmentCard = document.querySelector(
        "#pomodoro-app .pm-environment-card"
    );

    if (!taskCard || !environmentCard) {
        return;
    }

    const desktopQuery = window.matchMedia(
        "(min-width: 1101px)"
    );

    function syncHeight() {

        // Tablet / Mobile: để hai box tự cao theo nội dung
        if (!desktopQuery.matches) {
            environmentCard.style.removeProperty(
                "--pm-synced-height"
            );
            return;
        }

        // Lấy chiều cao thực tế của Layout 1
        const taskHeight = taskCard.getBoundingClientRect().height;

        // Áp dụng cho Layout 2
        environmentCard.style.setProperty(
            "--pm-synced-height",
            `${taskHeight}px`
        );
    }

    // Quan sát Layout 1 khi thêm / bỏ mục tiêu
    const observer = new ResizeObserver(() => {
        syncHeight();
    });

    observer.observe(taskCard);

    // Đồng bộ khi thay đổi kích thước cửa sổ
    desktopQuery.addEventListener(
        "change",
        syncHeight
    );

    window.addEventListener(
        "resize",
        syncHeight
    );

    syncHeight();
}
