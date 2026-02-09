#!/usr/bin/env python3
"""
Тест API Kie.ai — проверка доступности Gemini 2.5 Pro и Nano Banana Pro.
Запуск: python test_kie_api.py
"""
import requests
import json
from pathlib import Path

# Загружаем API ключ
env_path = Path(__file__).parent / '.env'
api_key = None
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.startswith('KIE_AI_API_KEY='):
                api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                break
if not api_key:
    print("❌ KIE_AI_API_KEY не найден в .env")
    exit(1)

print("🧪 Тест Kie.ai API")
print(f"🔑 API Key: {api_key[:10]}...{api_key[-5:]}")
print()

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# --- 1. Gemini 2.5 Pro (рассуждающая модель для анализа) ---
print("=" * 60)
print("1️⃣  Gemini 2.5 Pro (анализ комнаты/мебели, рекомендации)")
print("   URL: https://api.kie.ai/gemini-2.5-pro/v1/chat/completions")
print()

gemini_url = "https://api.kie.ai/gemini-2.5-pro/v1/chat/completions"
gemini_payload = {
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello, just testing. Reply with 'OK' if you're working."}
            ]
        }
    ],
    "stream": False,
    "include_thoughts": False,
    "reasoning_effort": "high"
}

try:
    r = requests.post(gemini_url, headers=headers, json=gemini_payload, timeout=30)
    print(f"   HTTP: {r.status_code}")
    data = r.json()
    if data.get('code') == 500 and 'maintained' in (data.get('msg') or '').lower():
        print("   ❌ Gemini на обслуживании (Maintenance)")
    elif 'choices' in data and data['choices']:
        content = data['choices'][0]['message']['content']
        print(f"   ✅ Gemini работает. Ответ: {content[:80]}")
    else:
        print("   ⚠️  Ответ:", json.dumps(data, indent=2, ensure_ascii=False)[:400])
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# --- 2. Nano Banana Pro (генерация изображений) ---
print()
print("=" * 60)
print("2️⃣  Nano Banana Pro (вставка мебели в комнату)")
print("   URL: https://api.kie.ai/api/v1/jobs/createTask")
print("   Опрос: https://api.kie.ai/api/v1/jobs/recordInfo?taskId=...")
print()

nano_url = "https://api.kie.ai/api/v1/jobs/createTask"
# Минимальный payload — без картинок API вернёт ошибку, но мы проверим доступность
nano_payload = {
    "model": "nano-banana-pro",
    "input": {
        "prompt": "test",
        "image_input": ["https://example.com/fake.png"],
        "aspect_ratio": "1:1",
        "resolution": "2K",
        "output_format": "png"
    }
}

try:
    r = requests.post(nano_url, headers=headers, json=nano_payload, timeout=30)
    print(f"   HTTP: {r.status_code}")
    data = r.json()
    if r.status_code == 200 and data.get('code') == 200 and data.get('data', {}).get('taskId'):
        print("   ✅ Nano Banana принимает задачи (taskId получен)")
    elif r.status_code == 200 and data.get('code') != 200:
        print(f"   ✅ Сервис доступен. Код: {data.get('code')}, сообщение: {data.get('message', '')[:80]}")
    else:
        print("   Ответ:", json.dumps(data, indent=2, ensure_ascii=False)[:350])
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

print()
print("=" * 60)
print("Где в проекте:")
print("  • Gemini: backend/services/gpt4_analyzer.py, backend/services/upsell.py")
print("  • Nano Banana: backend/services/nano_banana.py")
print("  • Промпты: в тех же файлах (_create_*_prompt, _create_prompt, _create_upsell_prompt)")
print("=" * 60)
