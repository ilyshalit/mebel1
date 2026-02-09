#!/bin/bash
# Локальная проверка без вызовов к внешним API (Kie.ai).
# Запустите сначала: ./start.sh или вручную backend :8000 и frontend :8080

set -e
API="${API:-http://localhost:8000}"
FRONT="${FRONT:-http://localhost:8080}"

echo "🔍 Локальная проверка..."
echo "   API: $API"
echo "   Frontend: $FRONT"
echo ""

# Backend root
echo -n "Backend GET / ... "
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/")
if [ "$code" = "200" ]; then echo "OK ($code)"; else echo "FAIL ($code)"; exit 1; fi

# Backend health
echo -n "Backend GET /api/health ... "
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/health")
if [ "$code" = "200" ]; then echo "OK ($code)"; else echo "FAIL ($code)"; exit 1; fi

# Frontend
echo -n "Frontend GET / ... "
code=$(curl -s -o /dev/null -w "%{http_code}" "$FRONT/")
if [ "$code" = "200" ]; then echo "OK ($code)"; else echo "FAIL ($code)"; exit 1; fi

# Catalog (local data)
echo -n "Backend GET /api/catalog ... "
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/catalog")
if [ "$code" = "200" ]; then echo "OK ($code)"; else echo "FAIL ($code)"; exit 1; fi

echo ""
echo "✅ Локальные сервисы отвечают. Откройте в браузере: $FRONT"
echo "   Режим «Заменить мебель»: загрузите комнату → ИИ предложит что заменить → выберите новую мебель → Создать визуализацию."
