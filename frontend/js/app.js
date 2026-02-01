// Конфигурация API
// 1) В локальной разработке (frontend на :8080, backend на :8000) — ходим на :8000
// 2) В продакшене за reverse-proxy (HTTPS на 443/80) — ходим на тот же origin
const API_BASE_URL =
  window.location.port === '8080'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : window.location.origin;

// Глобальные переменные
let roomImagePath = null;
let furnitureImagePath = null;
let selectedMode = 'auto';
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
const furniturePreview = document.getElementById('furniturePreview');

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
    initModeSelection();
    initCanvas();
    loadCatalog();
});

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
    dropZone.addEventListener('click', () => {
        input.click();
    });

    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            onFileSelect(e.target.files[0]);
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
            onFileSelect(e.dataTransfer.files[0]);
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
            checkReadyToGenerate();
        } else {
            alert('Ошибка загрузки комнаты');
        }
    } catch (error) {
        console.error('Error uploading room:', error);
        alert('Ошибка загрузки комнаты');
    }
}

// Upload Furniture Image
async function uploadFurnitureImage(file) {
    try {
        showPreview(file, furniturePreview);
        
        const formData = new FormData();
        formData.append('file', file);

        // Показываем индикатор загрузки
        furniturePreview.style.opacity = '0.5';

        const response = await fetch(`${API_BASE_URL}/api/upload/furniture`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (data.success) {
            furnitureImagePath = data.file_path;
            furniturePreview.style.opacity = '1';
            checkReadyToGenerate();
        } else {
            alert('Ошибка загрузки мебели');
            furniturePreview.style.opacity = '1';
        }
    } catch (error) {
        console.error('Error uploading furniture:', error);
        alert('Ошибка загрузки мебели');
        furniturePreview.style.opacity = '1';
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
            <img src="${API_BASE_URL}${item.image_url}" alt="${item.name}">
            <div class="catalog-item-name">${item.name}</div>
        </div>
    `).join('');
    
    // Add click handlers
    document.querySelectorAll('.catalog-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.catalog-item').forEach(i => i.classList.remove('selected'));
            item.classList.add('selected');
            
            furnitureImagePath = item.dataset.path;
            
            // Show preview
            furniturePreview.src = `${API_BASE_URL}${item.querySelector('img').src}`;
            furniturePreview.style.display = 'block';
            furnitureDropZone.querySelector('.drop-zone-content').style.display = 'none';
            
            checkReadyToGenerate();
        });
    });
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

// Check if ready to generate
function checkReadyToGenerate() {
    if (roomImagePath && furnitureImagePath) {
        step2.style.display = 'block';
        generateBtn.disabled = false;
    }
}

// Generate (Nano Banana Pro)
generateBtn.addEventListener('click', async () => {
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
        formData.append('furniture_image_path', furnitureImagePath);
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
        
        // Update loading text based on model
        updateLoadingText('Анализ изображений с GPT-4 Vision...');
        
        // Call API
        const response = await fetch(`${API_BASE_URL}/api/generate`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show result
            updateLoadingText('Готово!');
            
            setTimeout(() => {
                loadingState.style.display = 'none';
                resultState.style.display = 'block';
                
                resultImage.src = `${API_BASE_URL}${data.result_image_url}`;
                generationTime.textContent = data.generation_time.toFixed(1);
                
                // Показываем какая модель использовалась
                if (data.model_used) {
                    console.log(`Использована модель: ${data.model_used}`);
                    console.log(`Сохраняет оригинал: ${data.preserves_original}`);
                }
                
                // Load upsell recommendations
                loadUpsellRecommendations(data.analysis);
            }, 500);
        } else {
            throw new Error(data.error || 'Ошибка генерации');
        }
    } catch (error) {
        console.error('Generation error:', error);
        loadingState.style.display = 'none';
        alert(`Ошибка генерации: ${error.message}`);
    }
});

function updateLoadingText(text) {
    document.querySelector('.loading-substep').textContent = text;
}

// Upsell recommendations
async function loadUpsellRecommendations(analysis) {
    try {
        const formData = new FormData();
        formData.append('furniture_analysis', JSON.stringify(analysis.furniture_analysis));
        formData.append('room_analysis', JSON.stringify(analysis.room_analysis));
        
        const response = await fetch(`${API_BASE_URL}/api/upsell`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success && data.recommendations.length > 0) {
            renderUpsellRecommendations(data.recommendations);
        } else {
            document.getElementById('upsellSection').style.display = 'none';
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
            <img src="${API_BASE_URL}${item.image_url || '/catalog/placeholder.png'}" alt="${item.name}">
            <div class="upsell-item-content">
                <h4>${item.name}</h4>
                <p>${item.recommendation_reason || item.description || ''}</p>
                ${item.recommendation_category ? `<span class="upsell-item-category">${item.recommendation_category}</span>` : ''}
            </div>
        </div>
    `).join('');
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
    furnitureImagePath = null;
    manualPosition = null;
    
    roomPreview.style.display = 'none';
    roomPreview.src = '';
    roomDropZone.querySelector('.drop-zone-content').style.display = 'block';
    
    furniturePreview.style.display = 'none';
    furniturePreview.src = '';
    furnitureDropZone.querySelector('.drop-zone-content').style.display = 'block';
    
    step2.style.display = 'none';
    step3.style.display = 'none';
    
    generateBtn.disabled = true;
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
});
