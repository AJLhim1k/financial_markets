#!/bin/bash
echo "=== Запуск Education Platform ==="

TUNNEL_ID="543c257a-cc02-444f-8d11-e629b8fc44c1"
echo "Tunnel ID: $TUNNEL_ID"

# 1. Проверить файл туннеля
TUNNEL_FILE="/home/ajlhimik/.cloudflared/$TUNNEL_ID.json"
if [ ! -f "$TUNNEL_FILE" ]; then
    echo "❌ Файл туннеля не найден: $TUNNEL_FILE"
    exit 1
fi

# 2. Запустить бота (если не запущен)
echo "1. Проверяю бота..."
if ! pgrep -f "python bot.py" > /dev/null; then
    echo "   Запускаю бота..."
    cd /mnt/d/fin_markets_project
    nohup python bot.py > /tmp/education_bot.log 2>&1 &
    sleep 5
else
    echo "   ✅ Бот уже запущен"
fi

# 3. Проверить порт 8000
echo "2. Проверяю порт 8000..."
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "   ✅ Порт 8000 отвечает"
else
    echo "   ❌ Порт 8000 не отвечает"
    echo "   Запускаю бота заново..."
    pkill -f "python bot.py"
    cd /mnt/d/fin_markets_project
    nohup python bot.py > /tmp/education_bot.log 2>&1 &
    sleep 5
fi

# 4. Запустить туннель
echo "3. Запускаю Cloudflare Tunnel..."
pkill -f "cloudflared"
sleep 2

# Проверить конфиг
if [ ! -f ~/.cloudflared/config.yml ]; then
    echo "   Создаю конфиг..."
    cat > ~/.cloudflared/config.yml << EOF
tunnel: $TUNNEL_ID
credentials-file: $TUNNEL_FILE

ingress:
  - hostname: moexbot.uk
    service: http://localhost:8000
  - hostname: www.moexbot.uk
    service: http://localhost:8000
  - service: http_status:404
EOF
fi

# Запустить туннель
echo "   Туннель запускается..."
nohup cloudflared tunnel --config ~/.cloudflared/config.yml run $TUNNEL_ID > /tmp/cloudflared_edu.log 2>&1 &
sleep 7

# 5. Проверить запуск
echo "4. Проверяю запуск..."
if pgrep -f "cloudflared.*$TUNNEL_ID" > /dev/null; then
    echo "   ✅ Туннель запущен"
    echo ""
    echo "🌐 Домены:"
    echo "   • https://moexbot.uk"
    echo "   • https://www.moexbot.uk"
    echo "   • https://app.moexbot.uk"
    echo "   • https://api.moexbot.uk"
    echo ""
    echo "📊 Логи:"
    echo "   • Бот: /tmp/education_bot.log"
    echo "   • Туннель: /tmp/cloudflared_edu.log"
else
    echo "   ❌ Туннель не запустился"
    tail -10 /tmp/cloudflared_edu.log
fi

echo "=== Готово ==="