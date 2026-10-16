
/* =====================================================
   POMODORO WORKSPACE 2.0
   BACKGROUND PICKER V2 - REAL IMAGE LIBRARY
   ===================================================== */

import {
    backgrounds,
    typeLabels,
    getBackgroundById,
    getDefaultBackground
} from "./background-data.js";

let selectedBackground = getDefaultBackground();

export function getSelectedBackground() {
    return selectedBackground
        ? { ...selectedBackground }
        : null;
}

export function initBackgroundPicker() {

    const trigger = document.getElementById(
        "pm-background-trigger"
    );

    const library = document.getElementById(
        "pm-background-library"
    );

    const grid = document.getElementById(
        "pm-background-grid"
    );

    const thumb = document.getElementById(
        "pm-bg-selected-thumb"
    );

    const name = document.getElementById(
        "pm-bg-selected-name"
    );

    const type = document.getElementById(
        "pm-bg-selected-type"
    );

    const count = document.getElementById(
        "pm-bg-count"
    );

    const filters = [
        ...document.querySelectorAll(
            ".pm-background-picker .pm-filter-btn"
        )
    ];

    if (
        !trigger ||
        !library ||
        !grid ||
        !thumb ||
        !name ||
        !type ||
        !count
    ) {
        console.warn(
            "Background Picker: Thiếu phần tử HTML."
        );
        return;
    }

    // Tránh gắn sự kiện nhiều lần.
    if (trigger.dataset.initialized === "true") {
        return;
    }

    trigger.dataset.initialized = "true";

    let activeFilter = "all";


    /* =================================================
       1. ĐÓNG / MỞ THƯ VIỆN
       ================================================= */

    function toggleLibrary(open) {
        library.hidden = !open;

        trigger.setAttribute(
            "aria-expanded",
            String(open)
        );
    }


    /* =================================================
       2. TẠO ẢNH THU NHỎ
       ================================================= */

    function createImage(src, alt = "") {

        const image = document.createElement("img");

        image.src = src;
        image.alt = alt;
        image.loading = "lazy";
        image.decoding = "async";
        image.className = "pm-bg-real-image";

        image.addEventListener("error", () => {
            image.classList.add("is-error");
        });

        return image;
    }


    /* =================================================
       3. HIỂN THỊ THƯ VIỆN
       ================================================= */

    function renderGallery() {

        const visible = backgrounds.filter(item => {
            return (
                activeFilter === "all" ||
                item.type === activeFilter
            );
        });

        count.textContent =
            `${visible.length} không gian`;

        grid.replaceChildren();

        // Danh mục chưa có ảnh/video tương ứng.
        if (visible.length === 0) {

            const empty = document.createElement("p");

            empty.className = "pm-bg-empty-state";
            empty.textContent =
                "Chưa có không gian thuộc danh mục này.";

            grid.appendChild(empty);
            return;
        }

        visible.forEach(item => {

            const button = document.createElement("button");

            button.type = "button";
            button.className = "pm-bg-item";

            // Dữ liệu để kiểm tra trong DevTools.
            button.dataset.backgroundId = item.id;
            button.dataset.backgroundType = item.type;
            button.dataset.backgroundUrl = item.src;

            const isSelected =
                selectedBackground?.id === item.id;

            button.classList.toggle(
                "is-selected",
                isSelected
            );

            button.setAttribute(
                "aria-pressed",
                String(isSelected)
            );

            button.setAttribute(
                "aria-label",
                `${item.name}, ${typeLabels[item.type]}`
            );

            // Preview hình nền.
            const preview = document.createElement("span");

            preview.className = "pm-bg-item-preview";

            preview.appendChild(
                createImage(item.thumbnail, "")
            );

            // Loại hình nền hiển thị trên thumbnail.
            const badge = document.createElement("span");

            badge.className = "pm-media-type";
            badge.textContent = typeLabels[item.type];

            preview.appendChild(badge);

            // Tên.
            const itemName = document.createElement("span");

            itemName.className = "pm-bg-item-name";
            itemName.textContent = item.name;

            // Phụ đề.
            const itemType = document.createElement("span");

            itemType.className = "pm-bg-item-type";
            itemType.textContent = typeLabels[item.type];

            button.append(
                preview,
                itemName,
                itemType
            );

            button.addEventListener("click", () => {
                selectBackground(item.id);
                toggleLibrary(false);
                trigger.focus();
            });

            grid.appendChild(button);
        });
    }


    /* =================================================
       4. CHỌN HÌNH NỀN
       ================================================= */

    function selectBackground(id) {

        const item = getBackgroundById(id);

        if (!item) return;

        selectedBackground = item;

        // Cập nhật thumbnail bên ngoài dropdown.
        thumb.className = "pm-bg-selected-thumb";

        thumb.replaceChildren(
            createImage(item.thumbnail, "")
        );

        name.textContent = item.name;

        type.textContent =
            `${typeLabels[item.type]} · Đã chọn`;

        // Lưu trên trigger để dễ kiểm tra.
        trigger.dataset.backgroundId = item.id;
        trigger.dataset.backgroundType = item.type;
        trigger.dataset.backgroundUrl = item.src;

        renderGallery();

        // Phát sự kiện thống nhất cho module khác.
        trigger.dispatchEvent(
            new CustomEvent(
                "pomodoro:background-change",
                {
                    bubbles: true,
                    detail: { ...item }
                }
            )
        );
    }


    /* =================================================
       5. BẤM NÚT MỞ THƯ VIỆN
       ================================================= */

    trigger.addEventListener("click", () => {

        toggleLibrary(library.hidden);
    });


    /* =================================================
       6. BỘ LỌC
       ================================================= */

    filters.forEach(button => {

        button.addEventListener("click", () => {

            activeFilter = button.dataset.filter || "all";

            filters.forEach(filterBtn => {

                const active =
                    filterBtn.dataset.filter === activeFilter;

                filterBtn.classList.toggle(
                    "is-active",
                    active
                );

                filterBtn.setAttribute(
                    "aria-pressed",
                    String(active)
                );
            });

            renderGallery();
        });
    });


    /* =================================================
       7. KHỞI TẠO
       ================================================= */

    selectBackground(
        selectedBackground?.id || backgrounds[0].id
    );

    toggleLibrary(false);

    console.log(
        "Background Picker V2 initialized"
    );
}
