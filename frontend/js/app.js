// Конфигурация API
// 1) В локальной разработке (frontend на :8080, backend на :8000) — ходим на :8000
// 2) В продакшене за reverse-proxy (HTTPS на 443/80) — ходим на тот же origin
const API_BASE_URL =
  window.location.port === '8080'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : window.location.origin;

// URL картинки каталога с белым фоном (без шахматки) — через API
// ?v=2 обходит кэш браузера
function catalogImageUrl(item) {
  if (!item || !item.image_url) return `${API_BASE_URL}/catalog/placeholder.png`;
  const filename = item.image_url.replace(/^\/catalog\//, '');
  return `${API_BASE_URL}/api/catalog/img/${filename}?v=2`;
}

// Глобальные переменные
let roomImagePath = null;
let furnitureImagePaths = []; // Массив путей к мебели
let selectedMode = 'auto';
let placementMode = 'place'; // 'place' | 'replace' — разместить или заменить мебель
let roomFurnitureItems = []; // Результат анализа комнаты для режима замены: [{type, position}]
let replaceWhat = null;      // Выбранный предмет для замены (например "sofa on the left")
let manualPosition = null;
let manualBox = null; // {x, y, w, h} in image pixels
let catalogItems = [];
let roomImageElement = null;

// DOM элементы
const roomInput = document.getElementById('roomInput');
const roomDropZone = document.getElementById('roomDropZone');
const roomPreview = document.getElementById('roomPreview');

const furnitureInput = document.getElementById('furnitureInput');
const furnitureDropZone = document.getElementById('furnitureDropZone');
const furniturePreviewGrid = document.getElementById('furniturePreviewGrid');

const autoModeBtn = document.getElementById('autoMode');
const manualModeBtn = document.getElementById('manualMode');
const manualSelection = document.getElementById('manualSelection');
const roomCanvas = document.getElementById('roomCanvas');

const generateBtn = document.getElementById('generateBtn');
const step1 = document.getElementById('step1');
const step2 = document.getElementById('step2');
const step3 = document.getElementById('step3');

const loadingState = document.getElementById('loadingState');
const resultState = document.getElementById('resultState');
const resultImage = document.getElementById('resultImage');
const generationTime = document.getElementById('generationTime');

const downloadBtn = document.getElementById('downloadBtn');
const tryAgainBtn = document.getElementById('tryAgainBtn');

// Tabs
const tabs = document.querySelectorAll('.tab');
const tabContents = document.querySelectorAll('.tab-content');

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    initDropZones();
    initTabs();
    initPlacementMode();
    initModeSelection();
    initCanvas();
    loadCatalog();
});

// Режим: разместить мебель / заменить мебель в комнате
function initPlacementMode() {
    const placeBtn = document.getElementById('placeModeBtn');
    const replaceBtn = document.getElementById('replaceModeBtn');
    const hint = document.getElementById('placementModeHint');
    const roomTitle = document.getElementById('roomUploadTitle');
    const furnitureTitle = document.getElementById('furnitureUploadTitle');
    const furnitureDropText = document.getElementById('furnitureDropZoneText');
    const step2Title = document.getElementById('step2Title');
    const replaceModeMessage = document.getElementById('replaceModeMessage');
    const placeModeSelection = document.getElementById('placeModeSelection');

    function setPlacementMode(mode) {
        placementMode = mode;
        placeBtn.classList.toggle('active', mode === 'place');
        replaceBtn.classList.toggle('active', mode === 'replace');
        if (hint) {
            hint.textContent = mode === 'place'
                ? 'Загрузите фото комнаты и выберите мебель — ИИ разместит её в интерьере.'
                : 'Загрузите фото комнаты со старой мебелью и выберите новую — ИИ заменит старую на новую.';
        }
        if (roomTitle) {
            roomTitle.textContent = mode === 'place'
                ? '📷 Фотография Интерьера'
                : '📷 Комната с мебелью, которую заменить';
        }
        if (furnitureTitle) {
            furnitureTitle.textContent = mode === 'place'
                ? '🪑 Предметы Мебели'
                : '🪑 Новая мебель (на что заменить)';
        }
        if (furnitureDropText) {
            furnitureDropText.textContent = mode === 'place'
                ? 'Загрузите до 5 предметов мебели'
                : 'Выберите один предмет (новую мебель)';
        }
        if (step2Title) {
            step2Title.textContent = mode === 'place' ? 'Режим Размещения' : 'Заменить мебель';
        }
        if (replaceModeMessage) replaceModeMessage.style.display = mode === 'replace' ? 'block' : 'none';
        if (placeModeSelection) placeModeSelection.style.display = mode === 'place' ? 'flex' : 'none';
        const replaceWhatBlock = document.getElementById('replaceWhatSelection');
        if (replaceWhatBlock) replaceWhatBlock.style.display = mode === 'replace' ? 'block' : 'none';
        if (mode === 'replace' && roomImagePath) {
            analyzeRoomForReplace();
        } else if (mode === 'place') {
            roomFurnitureItems = [];
            replaceWhat = null;
            renderReplaceWhatButtons();
        }
        if (mode === 'replace' && furnitureImagePaths.length > 1) {
            furnitureImagePaths = furnitureImagePaths.slice(0, 1);
            renderFurniturePreviews();
        }
    }

    placeBtn.addEventListener('click', () => setPlacementMode('place'));
    replaceBtn.addEventListener('click', () => setPlacementMode('replace'));
}

// Drop Zones
function initDropZones() {
    // Room upload
    setupDropZone(roomDropZone, roomInput, async (file) => {
        await uploadRoomImage(file);
    });

    // Furniture upload
    setupDropZone(furnitureDropZone, furnitureInput, async (file) => {
        await uploadFurnitureImage(file);
    });
}

function setupDropZone(dropZone, input, onFileSelect) {
    // Click to select
    dropZone.addEventListener('click', (e) => {
        // Не открывать input если кликнули на кнопку удаления
        if (e.target.classList.contains('furniture-preview-remove')) return;
        input.click();
    });

    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            // Если это мебель, передаем массив файлов
            if (input.id === 'furnitureInput' && e.target.files.length > 1) {
                onFileSelect(Array.from(e.target.files));
            } else {
                onFileSelect(e.target.files[0]);
            }
        }
    });

    // Drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        if (e.dataTransfer.files.length > 0) {
            // Если это мебель, можем принять несколько
            if (dropZone.id === 'furnitureDropZone' && e.dataTransfer.files.length > 1) {
                onFileSelect(Array.from(e.dataTransfer.files));
            } else {
                onFileSelect(e.dataTransfer.files[0]);
            }
        }
    });
}

// Upload Room Image
async function uploadRoomImage(file) {
    try {
        showPreview(file, roomPreview);
        
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/api/upload/room`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (data.success) {
            roomImagePath = data.file_path;
            roomImageElement = roomPreview;
            if (placementMode === 'replace') await analyzeRoomForReplace();
            checkReadyToGenerate();
        } else {
            alert('Ошибка загрузки комнаты');
        }
    } catch (error) {
        console.error('Error uploading room:', error);
        alert('Ошибка загрузки комнаты');
    }
}

// Upload Furniture Images (multiple support)
async function uploadFurnitureImage(files) {
    try {
        let fileArray = Array.isArray(files) ? files : [files];
        if (placementMode === 'replace') {
            fileArray = fileArray.slice(0, 1);
            if (files.length > 1) alert('В режиме «Заменить мебель» загружается только один предмет.');
        } else if (fileArray.length > 5) {
            alert('Максимум 5 предметов мебели');
            return;
        }
        
        // Показываем превью перед загрузкой
        const formData = new FormData();
        for (const file of fileArray) {
            formData.append('files', file);
        }

        // Индикатор загрузки
        const dropContent = furnitureDropZone.querySelector('.drop-zone-content');
        if (dropContent) dropContent.style.display = 'none';
        furniturePreviewGrid.style.display = 'grid';
        furniturePreviewGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center;">Загрузка...</p>';

        const response = await fetch(`${API_BASE_URL}/api/upload/furniture`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (data.success && data.items) {
            furnitureImagePaths = data.items.map(item => item.file_path);
            renderFurniturePreviews(data.items);
            checkReadyToGenerate();
        } else {
            alert('Ошибка загрузки мебели');
            furniturePreviewGrid.style.display = 'none';
            if (dropContent) dropContent.style.display = 'block';
        }
    } catch (error) {
        console.error('Error uploading furniture:', error);
        alert('Ошибка загрузки мебели');
        const dropContent = furnitureDropZone.querySelector('.drop-zone-content');
        furniturePreviewGrid.style.display = 'none';
        if (dropContent) dropContent.style.display = 'block';
    }
}

function renderFurniturePreviews(items) {
    furniturePreviewGrid.innerHTML = items.map((item, index) => `
        <div class="furniture-preview-item">
            <img src="${API_BASE_URL}/uploads/${item.filename}" alt="Furniture ${index + 1}">
            <button class="furniture-preview-remove" data-index="${index}">×</button>
        </div>
    `).join('');
    
    // Обработчики удаления
    furniturePreviewGrid.querySelectorAll('.furniture-preview-remove').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const index = parseInt(btn.dataset.index);
            removeFurnitureItem(index);
        });
    });
}

function removeFurnitureItem(index) {
    furnitureImagePaths.splice(index, 1);
    
    if (furnitureImagePaths.length === 0) {
        furniturePreviewGrid.style.display = 'none';
        const dropContent = furnitureDropZone.querySelector('.drop-zone-content');
        if (dropContent) dropContent.style.display = 'block';
        checkReadyToGenerate();
    } else {
        // Перерисовываем (в реальном приложении лучше просто удалить элемент)
        // Здесь для простоты просто скроем элемент
        const items = furniturePreviewGrid.querySelectorAll('.furniture-preview-item');
        if (items[index]) {
            items[index].style.display = 'none';
        }
        checkReadyToGenerate();
    }
}

function showPreview(file, imgElement) {
    const reader = new FileReader();
    reader.onload = (e) => {
        imgElement.src = e.target.result;
        imgElement.style.display = 'block';
        imgElement.parentElement.querySelector('.drop-zone-content').style.display = 'none';
    };
    reader.readAsDataURL(file);
}

// Tabs
function initTabs() {
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            
            // Update active tab
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Update active content
            tabContents.forEach(content => {
                if (content.id === `${tabName}Tab`) {
                    content.classList.add('active');
                } else {
                    content.classList.remove('active');
                }
            });
        });
    });
}

// Load Catalog
async function loadCatalog() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/catalog`);
        const data = await response.json();
        
        if (data.success && data.items.length > 0) {
            catalogItems = data.items;
            renderCatalog();
        }
    } catch (error) {
        console.error('Error loading catalog:', error);
    }
}

function renderCatalog() {
    const catalogGrid = document.getElementById('catalogGrid');
    
    if (catalogItems.length === 0) {
        catalogGrid.innerHTML = '<p class="empty-catalog">Каталог пуст</p>';
        return;
    }
    
    catalogGrid.innerHTML = catalogItems.map(item => `
        <div class="catalog-item" data-id="${item.id}" data-path="${item.image_path}">
            <img src="${catalogImageUrl(item)}" alt="${item.name}">
            <div class="catalog-item-name">${item.name}</div>
        </div>
    `).join('');
    
    // Add click handlers
    document.querySelectorAll('.catalog-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.catalog-item').forEach(i => i.classList.remove('selected'));
            item.classList.add('selected');
            
            if (placementMode === 'replace') {
                furnitureImagePaths = [item.dataset.path];
                renderFurniturePreviews([{ file_path: item.dataset.path, filename: item.querySelector('img').alt }]);
            } else if (!furnitureImagePaths.includes(item.dataset.path)) {
                furnitureImagePaths.push(item.dataset.path);
                renderFurniturePreviews([{ file_path: item.dataset.path, filename: item.querySelector('img').alt }]);
            }
            
            checkReadyToGenerate();
        });
    });
    
    // Render catalog preview on homepage
    renderCatalogPreview();
}

function renderCatalogPreview() {
    const catalogPreview = document.getElementById('catalogPreview');
    const catalogPreviewGrid = document.getElementById('catalogPreviewGrid');
    
    if (catalogItems.length === 0) {
        catalogPreview.style.display = 'none';
        return;
    }
    
    catalogPreview.style.display = 'block';
    
    // Show first 6 items
    catalogPreviewGrid.innerHTML = catalogItems.slice(0, 12).map(item => `
        <div class="product-card" data-id="${item.id}" data-path="${item.image_path}">
            <img src="${catalogImageUrl(item)}" alt="${item.name}">
            <div class="product-card-content">
                <h3>${item.name}</h3>
                <p>${item.description || ''}</p>
                <div class="product-card-footer">
                    ${item.price ? `<span class="product-price">${item.price} ₽</span>` : ''}
                    <button class="product-try-btn">Примерить</button>
                </div>
            </div>
        </div>
    `).join('');
    
    // Add click handlers
    catalogPreviewGrid.querySelectorAll('.product-try-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const card = btn.closest('.product-card');
            selectFurnitureFromCatalog(card.dataset.path);
        });
    });
}

function selectFurnitureFromCatalog(path) {
    if (placementMode === 'replace') {
        furnitureImagePaths = [path];
    } else if (!furnitureImagePaths.includes(path)) {
        furnitureImagePaths.push(path);
    }
    if (furnitureImagePaths.length) {
        const dropContent = furnitureDropZone.querySelector('.drop-zone-content');
        if (dropContent) dropContent.style.display = 'none';
        furniturePreviewGrid.style.display = 'grid';
        if (placementMode === 'replace') furniturePreviewGrid.innerHTML = '';

        const item = catalogItems.find(i => i.image_path === path);
        const previewHtml = `
            <div class="furniture-preview-item">
                <img src="${catalogImageUrl(item)}" alt="${item.name}">
                <button class="furniture-preview-remove" data-path="${path}">×</button>
            </div>
        `;
        
        furniturePreviewGrid.innerHTML += previewHtml;
        
        // Обработчик удаления
        furniturePreviewGrid.querySelector(`[data-path="${path}"]`).addEventListener('click', (e) => {
            e.stopPropagation();
            removeFurnitureByPath(path);
        });
        
        checkReadyToGenerate();
        
        // Scroll to step 1
        step1.scrollIntoView({ behavior: 'smooth' });
    }
}

function removeFurnitureByPath(path) {
    const index = furnitureImagePaths.indexOf(path);
    if (index > -1) {
        furnitureImagePaths.splice(index, 1);
        
        if (furnitureImagePaths.length === 0) {
            furniturePreviewGrid.style.display = 'none';
            const dropContent = furnitureDropZone.querySelector('.drop-zone-content');
            if (dropContent) dropContent.style.display = 'block';
        } else {
            // Просто скрываем элемент
            const items = furniturePreviewGrid.querySelectorAll('.furniture-preview-item');
            items[index]?.remove();
        }
        checkReadyToGenerate();
    }
}

// Mode Selection
function initModeSelection() {
    autoModeBtn.addEventListener('click', () => {
        selectedMode = 'auto';
        autoModeBtn.classList.add('active');
        manualModeBtn.classList.remove('active');
        manualSelection.style.display = 'none';
        manualPosition = null;
        manualBox = null;
    });

    manualModeBtn.addEventListener('click', () => {
        selectedMode = 'manual';
        manualModeBtn.classList.add('active');
        autoModeBtn.classList.remove('active');
        manualSelection.style.display = 'block';
        
        // Draw room on canvas
        if (roomImageElement) {
            drawRoomOnCanvas();
        }
    });
}

// Canvas for manual selection
function initCanvas() {
    let isDrawing = false;
    let startX = 0;
    let startY = 0;
    let currentX = 0;
    let currentY = 0;

    function drawSelectionRect() {
        drawRoomOnCanvas();
        const ctx = roomCanvas.getContext('2d');
        const rect = roomCanvas.getBoundingClientRect();
        const scaleX = roomCanvas.width / rect.width;
        const scaleY = roomCanvas.height / rect.height;

        const x1 = startX * scaleX;
        const y1 = startY * scaleY;
        const x2 = currentX * scaleX;
        const y2 = currentY * scaleY;

        const rx = Math.min(x1, x2);
        const ry = Math.min(y1, y2);
        const rw = Math.abs(x2 - x1);
        const rh = Math.abs(y2 - y1);

        ctx.save();
        ctx.strokeStyle = '#4F46E5';
        ctx.lineWidth = 4;
        ctx.setLineDash([10, 6]);
        ctx.strokeRect(rx, ry, rw, rh);
        ctx.fillStyle = 'rgba(79, 70, 229, 0.12)';
        ctx.fillRect(rx, ry, rw, rh);
        ctx.restore();
    }

    roomCanvas.addEventListener('mousedown', (e) => {
        if (selectedMode !== 'manual') return;
        isDrawing = true;
        const rect = roomCanvas.getBoundingClientRect();
        startX = e.clientX - rect.left;
        startY = e.clientY - rect.top;
        currentX = startX;
        currentY = startY;
        drawSelectionRect();
    });

    window.addEventListener('mousemove', (e) => {
        if (!isDrawing || selectedMode !== 'manual') return;
        const rect = roomCanvas.getBoundingClientRect();
        currentX = e.clientX - rect.left;
        currentY = e.clientY - rect.top;
        drawSelectionRect();
    });

    window.addEventListener('mouseup', (e) => {
        if (!isDrawing || selectedMode !== 'manual') return;
        isDrawing = false;

        const rect = roomCanvas.getBoundingClientRect();
        const endX = e.clientX - rect.left;
        const endY = e.clientY - rect.top;

        // Convert to image coordinates
        const scaleX = roomCanvas.width / rect.width;
        const scaleY = roomCanvas.height / rect.height;

        const x1 = Math.min(startX, endX) * scaleX;
        const y1 = Math.min(startY, endY) * scaleY;
        const x2 = Math.max(startX, endX) * scaleX;
        const y2 = Math.max(startY, endY) * scaleY;

        const w = Math.max(1, Math.floor(x2 - x1));
        const h = Math.max(1, Math.floor(y2 - y1));

        manualBox = {
            x: Math.floor(x1),
            y: Math.floor(y1),
            w,
            h
        };

        // Также совместимость: центр bbox как manualPosition
        manualPosition = {
            x: Math.floor(manualBox.x + manualBox.w / 2),
            y: Math.floor(manualBox.y + manualBox.h / 2)
        };

        drawSelectionRect();
    });
}

function drawRoomOnCanvas() {
    if (!roomImageElement) return;
    
    const ctx = roomCanvas.getContext('2d');
    const draw = () => {
        const w = roomImageElement.naturalWidth || roomImageElement.width;
        const h = roomImageElement.naturalHeight || roomImageElement.height;
        if (!w || !h) return;
        roomCanvas.width = w;
        roomCanvas.height = h;
        ctx.setLineDash([]);
        ctx.drawImage(roomImageElement, 0, 0);
    };

    if (roomImageElement.complete && (roomImageElement.naturalWidth || roomImageElement.width)) {
        draw();
    } else {
        roomImageElement.onload = () => draw();
    }
}

// Анализ комнаты для режима «Заменить»: ИИ предлагает, что заменить (диван, стол и т.д.)
async function analyzeRoomForReplace() {
    const container = document.getElementById('replaceWhatButtons');
    const hint = document.getElementById('replaceWhatHint');
    if (!container) return;
    container.innerHTML = '<span class="analyzing-text">Анализируем комнату...</span>';
    if (hint) hint.style.display = 'none';
    roomFurnitureItems = [];
    replaceWhat = null;
    try {
        const formData = new FormData();
        formData.append('room_image_path', roomImagePath);
        const response = await fetch(`${API_BASE_URL}/api/analyze-room-replace`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.items && data.items.length > 0) {
            roomFurnitureItems = data.items;
        }
    } catch (e) {
        console.error('Analyze room for replace:', e);
        if (hint) { hint.textContent = 'Не удалось проанализировать комнату. Можно создать визуализацию без выбора — ИИ попробует определить объект сам.'; hint.style.display = 'block'; }
    }
    renderReplaceWhatButtons();
}

// Подписи типов мебели по-русски
const furnitureTypeLabels = {
    sofa: 'Диван', table: 'Стол', bed: 'Кровать', chair: 'Стул', desk: 'Стол (письменный)',
    cabinet: 'Шкаф', armchair: 'Кресло', shelf: 'Полка', lamp: 'Лампа'
};
function furnitureLabel(type) {
    return furnitureTypeLabels[type] || type;
}

function renderReplaceWhatButtons() {
    const container = document.getElementById('replaceWhatButtons');
    const hint = document.getElementById('replaceWhatHint');
    if (!container) return;
    if (!roomFurnitureItems || roomFurnitureItems.length === 0) {
        container.innerHTML = '';
        if (hint) { hint.textContent = 'Мебель в комнате не определена. Создайте визуализацию — ИИ попробует заменить подходящий объект.'; hint.style.display = 'block'; }
        return;
    }
    if (hint) hint.style.display = 'block';
    container.innerHTML = roomFurnitureItems.map((it, i) => {
        const pos = (it.position || 'center').toLowerCase();
        const posRu = pos === 'center' ? 'в центре' : pos === 'left' ? 'слева' : pos === 'right' ? 'справа' : pos;
        const label = furnitureLabel(it.type) + ' (' + posRu + ')';
        const value = pos === 'center' ? `${it.type} in the center` : `${it.type} on the ${pos}`;
        const active = replaceWhat === value ? ' active' : '';
        return `<button type="button" class="replace-what-btn${active}" data-replace-value="${value.replace(/"/g, '&quot;')}">${label}</button>`;
    }).join('');
    container.querySelectorAll('.replace-what-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            replaceWhat = btn.dataset.replaceValue;
            container.querySelectorAll('.replace-what-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
}

// Check if ready to generate
function checkReadyToGenerate() {
    if (roomImagePath && furnitureImagePaths.length > 0) {
        step2.style.display = 'block';
        generateBtn.disabled = false;
        if (placementMode === 'replace') {
            const replaceWhatBlock = document.getElementById('replaceWhatSelection');
            if (replaceWhatBlock) replaceWhatBlock.style.display = 'block';
            if (roomFurnitureItems.length === 0 && roomImagePath) analyzeRoomForReplace();
        }
    } else {
        generateBtn.disabled = true;
    }
}

// Generate (Nano Banana Pro)
generateBtn.addEventListener('click', async () => {
    if (placementMode === 'replace' && furnitureImagePaths.length !== 1) {
        alert('В режиме «Заменить мебель» выберите ровно один предмет — новую мебель.');
        return;
    }
    if (selectedMode === 'manual' && !manualBox) {
        alert('Выделите прямоугольником место на комнате где разместить мебель');
        return;
    }
    
    // Show step 3
    step3.style.display = 'block';
    step3.scrollIntoView({ behavior: 'smooth' });
    loadingState.style.display = 'block';
    resultState.style.display = 'none';
    
    try {
        // Prepare form data
        const formData = new FormData();
        formData.append('room_image_path', roomImagePath);
        const pathsToSend = placementMode === 'replace' && furnitureImagePaths.length
            ? [furnitureImagePaths[0]]
            : furnitureImagePaths;
        formData.append('furniture_image_paths', JSON.stringify(pathsToSend));
        formData.append('placement_mode', placementMode);
        if (placementMode === 'replace' && replaceWhat) formData.append('replace_what', replaceWhat);
        formData.append('mode', selectedMode);
        
        // rotation: 0 or 90
        const rotationValue = document.querySelector('input[name="rotation"]:checked')?.value || '0';
        formData.append('furniture_rotation', rotationValue);
        // wall alignment
        const wallValue = document.querySelector('input[name="wall"]:checked')?.value || 'auto';
        formData.append('wall_alignment', wallValue);

        if (selectedMode === 'manual' && manualBox) {
            formData.append('manual_box_x', manualBox.x);
            formData.append('manual_box_y', manualBox.y);
            formData.append('manual_box_w', manualBox.w);
            formData.append('manual_box_h', manualBox.h);
        }
        
        updateLoadingText(placementMode === 'replace'
            ? 'Замена мебели в комнате...'
            : `Анализ ${furnitureImagePaths.length} предмет(ов) мебели...`);
        setLoadingNoticeVisible(true);
        
        // Call API
        const response = await fetch(`${API_BASE_URL}/api/generate`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            setLoadingNoticeVisible(false);
            loadingState.style.display = 'none';
            const msg = data.detail || data.error || data.message || 'Ошибка генерации';
            alert(typeof msg === 'string' ? msg : (msg.msg || JSON.stringify(msg)));
            return;
        }
        
        if (data.success) {
            updateLoadingText('Скачиваем изображение...');
            const resultUrl = `${API_BASE_URL}${data.result_image_url}`;
            generationTime.textContent = data.generation_time.toFixed(1);
            const onImageReady = () => {
                setLoadingNoticeVisible(false);
                updateLoadingText('Готово!');
                loadingState.style.display = 'none';
                resultState.style.display = 'block';
                if (data.model_used) {
                    console.log(`Использована модель: ${data.model_used}`);
                    console.log(`Размещено предметов: ${data.furniture_count || 1}`);
                }
                loadUpsellRecommendations(data.analysis, furnitureImagePaths);
            };
            resultImage.onload = onImageReady;
            resultImage.onerror = () => {
                updateLoadingText('Ошибка загрузки изображения');
                onImageReady();
            };
            resultImage.src = resultUrl;
        } else {
            throw new Error(data.error || 'Ошибка генерации');
        }
    } catch (error) {
        console.error('Generation error:', error);
        setLoadingNoticeVisible(false);
        loadingState.style.display = 'none';
        alert(`Ошибка генерации: ${error.message}`);
    }
});

function setLoadingNoticeVisible(visible) {
    const notice = document.querySelector('.loading-wait-notice');
    if (notice) notice.style.display = visible ? 'block' : 'none';
}

function updateLoadingText(text) {
    const substep = document.querySelector('.loading-substep');
    if (substep) substep.textContent = text === 'Готово!' ? '' : text;
}

// Upsell recommendations — только релевантные товары, без уже размещённых
async function loadUpsellRecommendations(analysis, placedPaths) {
    try {
        if (!catalogItems || catalogItems.length === 0) {
            document.getElementById('upsellSection').style.display = 'none';
            return;
        }
        
        const formData = new FormData();
        const furnitureData = analysis.furniture_analysis || analysis.furniture_items?.[0] || {};
        const roomData = analysis.room_analysis || {};
        
        formData.append('furniture_analysis', JSON.stringify(furnitureData));
        formData.append('room_analysis', JSON.stringify(roomData));
        formData.append('exclude_paths', JSON.stringify(placedPaths || []));
        
        const response = await fetch(`${API_BASE_URL}/api/upsell`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        const upsellSection = document.getElementById('upsellSection');
        const upsellGrid = document.getElementById('upsellGrid');
        const upsellMessage = document.getElementById('upsellMessage');
        
        if (data.success && data.recommendations.length > 0) {
            upsellSection.style.display = 'block';
            if (upsellMessage) upsellMessage.style.display = 'none';
            if (upsellGrid) upsellGrid.style.display = 'grid';
            renderUpsellRecommendations(data.recommendations);
        } else if (data.success && data.message) {
            upsellSection.style.display = 'block';
            if (upsellGrid) upsellGrid.style.display = 'none';
            const msgEl = document.getElementById('upsellMessageText');
            if (msgEl) msgEl.textContent = data.message;
            if (upsellMessage) upsellMessage.style.display = 'block';
        } else {
            upsellSection.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading upsell:', error);
        document.getElementById('upsellSection').style.display = 'none';
    }
}

function renderUpsellRecommendations(recommendations) {
    const upsellGrid = document.getElementById('upsellGrid');
    
    upsellGrid.innerHTML = recommendations.map(item => `
        <div class="upsell-item">
            <img src="${catalogImageUrl(item)}" alt="${item.name}">
            <div class="upsell-item-content">
                <h4>${item.name}</h4>
                <p class="ai-recommendation-text">💡 <strong>AI рекомендует:</strong> ${item.recommendation_reason || item.description || ''}</p>
                ${item.recommendation_category ? `<span class="upsell-item-category">${item.recommendation_category}</span>` : ''}
                ${item.price ? `<div class="upsell-item-price">${item.price} ₽</div>` : ''}
                <button class="product-try-btn" data-path="${item.image_path}" style="margin-top: var(--spacing-md); width: 100%;">
                    Показать как будет выглядеть
                </button>
            </div>
        </div>
    `).join('');
    
    // Add click handlers for "try" buttons
    upsellGrid.querySelectorAll('.product-try-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const path = btn.dataset.path;
            // Reset and start new generation with this item
            tryAgainBtn.click();
            
            setTimeout(() => {
                selectFurnitureFromCatalog(path);
            }, 500);
        });
    });
}

// Download result
downloadBtn.addEventListener('click', () => {
    const link = document.createElement('a');
    link.href = resultImage.src;
    link.download = 'furniture-placement-result.png';
    link.click();
});

// Try again
tryAgainBtn.addEventListener('click', () => {
    // Reset
    roomImagePath = null;
    furnitureImagePaths = [];
    manualPosition = null;
    manualBox = null;
    
    roomPreview.style.display = 'none';
    roomPreview.src = '';
    roomDropZone.querySelector('.drop-zone-content').style.display = 'block';
    
    furniturePreviewGrid.style.display = 'none';
    furniturePreviewGrid.innerHTML = '';
    const dropContent = furnitureDropZone.querySelector('.drop-zone-content');
    if (dropContent) dropContent.style.display = 'block';
    
    step2.style.display = 'none';
    step3.style.display = 'none';
    
    generateBtn.disabled = true;
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
});
