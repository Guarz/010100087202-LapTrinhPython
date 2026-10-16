
/* =====================================================
   POMODORO WORKSPACE 2.0
   TASK SELECTOR V13 - DJANGO INTEGRATION

   GIỮ NGUYÊN:
   - Single Active Task
   - Scheduled Task và Quick Goal loại trừ nhau
   - Chọn Scheduled Task => khóa Quick Goal
   - Tạo Quick Goal => khóa Scheduled Task
   - Bỏ chọn => mở khóa cả hai
   - Chỉ có một Quick Goal tại một thời điểm
   - Dialog xác nhận thay đổi Quick Goal
   - Sự kiện pomodoro:task-change

   CẬP NHẬT C2.3.2:
   - Không còn Scheduled Task mẫu
   - Lấy Task thật từ Django Template
   - Sử dụng taskId là khóa chính planner_task
   - Giữ nguyên Quick Goal trong bộ nhớ
   - Không tự tạo Task trong database
   ===================================================== */


export function initTaskSelector() {

    // ========================================================
    // 01. LẤY CÁC PHẦN TỬ DOM
    // ========================================================

    const dateDisplay =
        document.getElementById("pm-date-display");

    const dateInput =
        document.getElementById("pm-study-date");

    const taskSelect =
        document.getElementById("pm-task-select");

    const taskHint =
        document.getElementById("pm-task-hint");

    const scheduledSection =
        document.getElementById("pm-scheduled-section");

    const scheduledActive =
        document.getElementById("pm-scheduled-active");

    const clearScheduledBtn =
        document.getElementById("pm-clear-scheduled");

    const quickSection =
        document.getElementById("pm-quick-section");

    const quickLockHint =
        document.getElementById("pm-quick-lock-hint");

    const showBtn =
        document.getElementById("pm-show-add-task");

    const form =
        document.getElementById("pm-add-task-form");

    const input =
        document.getElementById("pm-new-task");

    const saveBtn =
        document.getElementById("pm-save-task");

    const cancelBtn =
        document.getElementById("pm-cancel-task");

    const quickGoalBox =
        document.getElementById("pm-quick-goal");

    const quickGoalName =
        document.getElementById("pm-quick-goal-name");

    const quickGoalStatus =
        document.getElementById("pm-quick-goal-status");

    const dialog =
        document.getElementById("pm-goal-confirm-dialog");

    const dialogGoalName =
        document.getElementById("pm-dialog-goal-name");

    const keepGoalBtn =
        document.getElementById("pm-keep-goal");

    const replaceGoalBtn =
        document.getElementById("pm-replace-goal");


    // ========================================================
    // 02. KIỂM TRA DOM
    // ========================================================

    const requiredElements = [
        dateDisplay,
        dateInput,
        taskSelect,
        scheduledSection,
        scheduledActive,
        clearScheduledBtn,
        quickSection,
        quickLockHint,
        showBtn,
        form,
        input,
        saveBtn,
        cancelBtn,
        quickGoalBox,
        quickGoalName,
        quickGoalStatus,
        dialog,
        dialogGoalName,
        keepGoalBtn,
        replaceGoalBtn
    ];

    if (requiredElements.some(element => !element)) {
        console.warn(
            "Task Selector V13: Thiếu phần tử HTML."
        );

        return;
    }

    // Ngăn khởi tạo nhiều lần trên cùng giao diện.
    if (taskSelect.dataset.initialized === "true") {
        return;
    }

    taskSelect.dataset.initialized = "true";


    // ========================================================
    // 03. NGÀY HỌC
    // ========================================================

    const now = new Date();

    const year = now.getFullYear();

    const month = String(
        now.getMonth() + 1
    ).padStart(2, "0");

    const day = String(
        now.getDate()
    ).padStart(2, "0");

    dateInput.value = `${year}-${month}-${day}`;

    dateDisplay.textContent =
        `${day}/${month}/${year}`;


    // ========================================================
    // 04. C2.3.2 - ĐỌC TASK THẬT TỪ DJANGO
    //
    // Nguồn dữ liệu:
    //
    // {{ pomodoro_tasks|json_script:"pm-scheduled-tasks-data" }}
    //
    // Ví dụ:
    // [
    //     {
    //         id: 12,
    //         taskId: 12,
    //         name: "Hoàn thành bài Python",
    //         type: "scheduled"
    //     }
    // ]
    // ========================================================

    function loadScheduledTasks() {

        const dataElement = document.getElementById(
            "pm-scheduled-tasks-data"
        );

        if (!dataElement) {
            console.warn(
                "[Task Selector] Chưa tìm thấy dữ liệu Task từ Django."
            );

            return [];
        }

        try {

            const parsedData = JSON.parse(
                dataElement.textContent
            );

            if (!Array.isArray(parsedData)) {
                console.warn(
                    "[Task Selector] Dữ liệu Task không phải Array."
                );

                return [];
            }

            // Chỉ nhận Task có ID thực và tên hợp lệ.
            const validTasks = parsedData.filter(
                task => (
                    task !== null &&
                    typeof task === "object" &&
                    Number.isSafeInteger(task.id) &&
                    task.id > 0 &&
                    Number.isSafeInteger(task.taskId) &&
                    task.taskId === task.id &&
                    typeof task.name === "string" &&
                    task.name.trim() !== ""
                )
            );

            return validTasks.map(task => ({
                id: task.id,
                taskId: task.taskId,
                name: task.name.trim(),
                type: "scheduled"
            }));

        } catch (error) {

            console.error(
                "[Task Selector] Không đọc được dữ liệu Django:",
                error
            );

            return [];
        }
    }


    const scheduledTasks = loadScheduledTasks();


    // ========================================================
    // 05. MODULE STATE
    // ========================================================

    // Chỉ có một mục tiêu phát sinh.
    let quickGoal = null;

    // Chỉ có một nhiệm vụ đang được chọn.
    let selectedTask = null;


    // ========================================================
    // 06. THÔNG BÁO NHIỆM VỤ ĐƯỢC CHỌN
    //
    // Focus Timer tiếp tục nhận:
    //
    // {
    //     id,
    //     name,
    //     type,
    //     taskId
    // }
    //
    // Với Quick Goal, taskId không tồn tại.
    // ========================================================

    function emitSelection() {

        document.dispatchEvent(
            new CustomEvent(
                "pomodoro:task-change",
                {
                    detail: selectedTask
                        ? { ...selectedTask }
                        : null
                }
            )
        );
    }


    // ========================================================
    // 07. RENDER
    // ========================================================

    function render() {

        const hasScheduled =
            selectedTask?.type === "scheduled";

        const hasQuick =
            selectedTask?.type === "quick";

        const hasGoal =
            quickGoal !== null;

        const formOpen =
            !form.hidden;


        // ----------------------------------------------------
        // A. SCHEDULED TASK
        // ----------------------------------------------------

        // Quick Goal đang chọn sẽ khóa dropdown.
        taskSelect.disabled = hasQuick;

        scheduledSection.classList.toggle(
            "is-locked",
            hasQuick
        );

        scheduledSection.classList.toggle(
            "is-selected",
            hasScheduled
        );

        scheduledActive.hidden = !hasScheduled;

        if (hasScheduled) {

            // <select>.value luôn là String.
            taskSelect.value = String(
                selectedTask.id
            );

        } else {

            taskSelect.value = "";
        }

        if (taskHint) {

            if (hasQuick) {

                taskHint.textContent =
                    "Đã khóa vì bạn đang chọn mục tiêu phát sinh.";

            } else if (scheduledTasks.length === 0) {

                taskHint.textContent =
                    "Bạn chưa có nhiệm vụ đang thực hiện. " +
                    "Có thể tạo nhiệm vụ hoặc sử dụng Quick Goal.";

            } else {

                taskHint.textContent =
                    "Chọn một nhiệm vụ trong danh sách học tập của bạn.";
            }
        }


        // ----------------------------------------------------
        // B. QUICK GOAL
        // ----------------------------------------------------

        // Khi đang chọn Scheduled Task:
        // khóa chức năng thêm Quick Goal.
        showBtn.disabled = hasScheduled;

        quickSection.classList.toggle(
            "is-locked",
            hasScheduled
        );

        quickSection.classList.toggle(
            "is-selected",
            hasQuick
        );

        quickLockHint.hidden = !hasScheduled;

        // Không hiển thị nút thêm khi:
        // - Form đang mở
        // - Đã có Quick Goal
        showBtn.hidden = formOpen || hasGoal;

        showBtn.setAttribute(
            "aria-expanded",
            String(formOpen)
        );

        quickGoalBox.hidden = !hasGoal;

        if (hasGoal) {

            quickGoalName.textContent =
                quickGoal.name;

            quickGoalStatus.textContent =
                "Đang được chọn";

        } else {

            quickGoalName.textContent = "";

            quickGoalStatus.textContent = "";
        }

        quickGoalBox.classList.toggle(
            "is-active",
            hasQuick
        );
    }


    // ========================================================
    // 08. UPDATE SELECTION
    // ========================================================

    function updateSelection(task) {

        selectedTask = task
            ? { ...task }
            : null;

        render();

        emitSelection();
    }


    // ========================================================
    // 09. HIỂN THỊ SCHEDULED TASK
    // ========================================================

    function renderScheduledTasks() {

        taskSelect.replaceChildren();

        taskSelect.add(
            new Option(
                "Chọn một nhiệm vụ",
                ""
            )
        );

        scheduledTasks.forEach(task => {

            taskSelect.add(
                new Option(
                    task.name,
                    String(task.id)
                )
            );
        });

        render();
    }


    // ========================================================
    // 10. CHỌN SCHEDULED TASK
    // ========================================================

    taskSelect.addEventListener(
        "change",
        () => {

            // Không cho chọn Scheduled Task
            // nếu Quick Goal đang tồn tại.
            if (quickGoal !== null) {

                render();

                return;
            }

            // HTML select luôn trả về chuỗi.
            // Django Task.id là số nguyên.
            const task = scheduledTasks.find(
                item =>
                    String(item.id) === taskSelect.value
            );

            // Đóng form Quick Goal nếu đang mở.
            form.hidden = true;

            input.value = "";

            updateSelection(
                task
                    ? {
                        ...task,
                        type: "scheduled"
                    }
                    : null
            );
        }
    );


    // ========================================================
    // 11. BỎ CHỌN SCHEDULED TASK
    // ========================================================

    clearScheduledBtn.addEventListener(
        "click",
        () => {

            if (
                selectedTask?.type !== "scheduled"
            ) {
                return;
            }

            updateSelection(null);

            taskSelect.focus();
        }
    );


    // ========================================================
    // 12. MỞ / ĐÓNG FORM QUICK GOAL
    // ========================================================

    function toggleForm(open) {

        if (
            open &&
            (
                selectedTask?.type === "scheduled" ||
                quickGoal !== null
            )
        ) {
            return;
        }

        form.hidden = !open;

        render();

        if (open) {
            input.focus();
        }
    }


    showBtn.addEventListener(
        "click",
        () => {

            if (showBtn.disabled) {
                return;
            }

            toggleForm(true);
        }
    );


    cancelBtn.addEventListener(
        "click",
        () => {

            input.value = "";

            toggleForm(false);

            showBtn.focus();
        }
    );


    // ========================================================
    // 13. TẠO QUICK GOAL
    //
    // Quick Goal vẫn là mục tiêu tạm thời.
    //
    // Sau này Session Recorder sẽ gửi tên mục tiêu
    // vào trường quick_goal_title của PomodoroLog.
    //
    // Không tạo bản ghi mới trong planner_task.
    // ========================================================

    function addQuickGoal() {

        if (
            quickGoal !== null ||
            selectedTask?.type === "scheduled"
        ) {
            return;
        }

        const name = input.value.trim();

        if (!name) {

            input.focus();

            return;
        }

        // Đồng bộ giới hạn với quick_goal_title
        // trong model PomodoroLog.
        if (name.length > 200) {

            input.setCustomValidity(
                "Mục tiêu không được vượt quá 200 ký tự."
            );

            input.reportValidity();

            input.focus();

            return;
        }

        input.setCustomValidity("");

        quickGoal = {
            id: "quick-current",
            name,
            type: "quick"
        };

        input.value = "";

        form.hidden = true;

        updateSelection(quickGoal);

        quickGoalBox.focus();
    }


    saveBtn.addEventListener(
        "click",
        addQuickGoal
    );


    input.addEventListener(
        "input",
        () => {

            // Xóa thông báo kiểm tra cũ
            // khi người dùng nhập lại.
            input.setCustomValidity("");
        }
    );


    input.addEventListener(
        "keydown",
        event => {

            if (event.key === "Enter") {

                event.preventDefault();

                addQuickGoal();
            }

            if (event.key === "Escape") {

                event.preventDefault();

                input.value = "";

                input.setCustomValidity("");

                toggleForm(false);

                showBtn.focus();
            }
        }
    );


    // ========================================================
    // 14. MỞ DIALOG THAY ĐỔI QUICK GOAL
    // ========================================================

    function openConfirmDialog() {

        if (!quickGoal) {
            return;
        }

        dialogGoalName.textContent =
            `“${quickGoal.name}”`;

        if (
            typeof dialog.showModal === "function"
        ) {

            if (!dialog.open) {

                dialog.showModal();
            }

        } else {

            const confirmed = window.confirm(
                `Thay đổi mục tiêu "${quickGoal.name}"?`
            );

            if (confirmed) {

                replaceQuickGoal();
            }
        }
    }


    quickGoalBox.addEventListener(
        "click",
        openConfirmDialog
    );


    // ========================================================
    // 15. GIỮ QUICK GOAL
    // ========================================================

    keepGoalBtn.addEventListener(
        "click",
        () => {

            if (dialog.open) {

                dialog.close();
            }

            // Không thay đổi selectedTask.
            quickGoalBox.focus();
        }
    );


    // ========================================================
    // 16. THAY ĐỔI QUICK GOAL
    // ========================================================

    function replaceQuickGoal() {

        if (!quickGoal) {
            return;
        }

        quickGoal = null;

        input.value = "";

        input.setCustomValidity("");

        form.hidden = true;

        // Mở khóa Scheduled Task và Quick Goal.
        updateSelection(null);

        showBtn.focus();
    }


    replaceGoalBtn.addEventListener(
        "click",
        () => {

            if (dialog.open) {

                dialog.close();
            }

            replaceQuickGoal();
        }
    );


    // ========================================================
    // 17. ĐÓNG DIALOG
    // ========================================================

    dialog.addEventListener(
        "close",
        () => {

            // Giữ hành vi cũ khi nhấn Esc
            // hoặc Giữ mục tiêu.
            if (!quickGoalBox.hidden) {

                quickGoalBox.focus();
            }
        }
    );


    // ========================================================
    // 18. INITIALIZATION
    // ========================================================

    renderScheduledTasks();

    updateSelection(null);

    console.info(
        "[Task Selector] V13 - Django Integration initialized.",
        scheduledTasks.length,
        "Scheduled Task"
    );
}
