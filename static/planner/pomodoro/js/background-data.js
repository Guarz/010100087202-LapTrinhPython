
/* =====================================================
   POMODORO WORKSPACE 2.0
   BACKGROUND LIBRARY DATA - V1

   Một nguồn dữ liệu dùng chung cho:
   - Pre-Focus Background Picker
   - Active Focus Fullscreen
   ===================================================== */

const BACKGROUND_BASE_URL =
    "/static/planner/pomodoro/media/backgrounds/";

/*
   Đổi IMAGE_EXTENSION thành ".jpg"
   nếu 6 ảnh trong thư mục vẫn là JPG.

   Chỉ dùng ".webp" nếu đã chuyển đổi ảnh
   sang WebP thực sự.
*/
const IMAGE_EXTENSION = ".webp";

function imagePath(filename) {
    return `${BACKGROUND_BASE_URL}${filename}${IMAGE_EXTENSION}`;
}

export const backgrounds = [
    {
        id: "cozy-city-night",
        name: "Cozy City Night",
        type: "image",
        category: "cozy",
        src: imagePath("cozy-city-night"),
        thumbnail: imagePath("cozy-city-night")
    },
    {
        id: "rainy-city",
        name: "Rainy City",
        type: "image",
        category: "rain",
        src: imagePath("rainy-city"),
        thumbnail: imagePath("rainy-city")
    },
    {
        id: "autumn-window",
        name: "Autumn Window",
        type: "image",
        category: "cozy",
        src: imagePath("autumn-window"),
        thumbnail: imagePath("autumn-window")
    },
    {
        id: "sunny-study-desk",
        name: "Sunny Study Desk",
        type: "image",
        category: "study",
        src: imagePath("sunny-study-desk"),
        thumbnail: imagePath("sunny-study-desk")
    },
    {
        id: "little-daydream",
        name: "Little Daydream",
        type: "image",
        category: "fantasy",
        src: imagePath("little-daydream"),
        thumbnail: imagePath("little-daydream")
    },
    {
        id: "forest-hideaway",
        name: "Forest Hideaway",
        type: "image",
        category: "nature",
        src: imagePath("forest-hideaway"),
        thumbnail: imagePath("forest-hideaway")
    }
];

export const typeLabels = {
    image: "Ảnh tĩnh",
    animated: "Ảnh động",
    video: "Video nền"
};

export function getBackgroundById(id) {
    return backgrounds.find(item => item.id === id) || null;
}

export function getDefaultBackground() {
    return backgrounds[0];
}
