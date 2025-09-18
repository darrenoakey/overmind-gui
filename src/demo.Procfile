web: while true; do echo "$(date) [WEB] 🌐 Server listening on port 3000"; echo "$(date) [WEB] 📊 Memory usage: $(ps -o pid,vsz,rss,pcpu,comm -p $$)"; echo "$(date) [WEB] 🔍 Processing request from $(curl -s httpbin.org/ip | head -1 || echo 'localhost')"; sleep 3; done

api: while true; do echo "$(date) [API] 🚀 API endpoint /users called"; echo "$(date) [API] 📈 Database query executed in $((RANDOM % 100 + 10))ms"; echo "$(date) [API] ✅ Response sent successfully"; echo "$(date) [API] 🔄 Cache hit ratio: $((RANDOM % 30 + 70))%"; sleep 2; done

worker: while true; do echo "$(date) [WORKER] ⚙️  Processing job #$((RANDOM % 1000))"; echo "$(date) [WORKER] 📦 Queue size: $((RANDOM % 50))"; echo "$(date) [WORKER] 🎯 Job completed successfully"; echo "$(date) [WORKER] 💤 Waiting for next job..."; sleep 4; done

monitor: while true; do echo "$(date) [MONITOR] 📊 CPU: $((RANDOM % 40 + 10))% | RAM: $((RANDOM % 60 + 20))%"; echo "$(date) [MONITOR] 🌡️  Temperature: $((RANDOM % 20 + 45))°C"; echo "$(date) [MONITOR] 💾 Disk usage: $((RANDOM % 30 + 50))%"; echo "$(date) [MONITOR] 🔋 System healthy"; sleep 5; done

logger: while true; do echo "$(date) [LOGGER] 📝 Log entry written to disk"; echo "$(date) [LOGGER] 🗂️  Rotating logs..."; echo "$(date) [LOGGER] 🧹 Cleaned up old entries"; echo "$(date) [LOGGER] 📊 Current log size: $((RANDOM % 500 + 100))MB"; sleep 6; done