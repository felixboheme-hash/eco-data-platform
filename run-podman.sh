#!/usr/bin/env bash
# 啟動/管理 eco-data-platform（生態資料庫 + BI網頁）的 Podman 容器服務。
# 需要先安裝 podman-compose（pip install podman-compose 或系統套件管理員安裝）。
#
# 用法：
#   ./run-podman.sh start        # 建置 + 啟動（db / etl / webapp 三個服務）
#   ./run-podman.sh logs         # 追蹤所有服務的 log
#   ./run-podman.sh stop         # 停止並移除容器
#   ./run-podman.sh reload-data  # 重新執行 etl，把 data/*.csv 重新匯入資料庫（不影響 db/webapp）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v podman-compose >/dev/null 2>&1; then
  echo "Error: podman-compose is not installed or not found in PATH." >&2
  echo "安裝方式：pip install podman-compose" >&2
  exit 1
fi

if ! podman info >/dev/null 2>&1; then
  echo "Error: 無法連線到 Podman，請先啟動 Podman（Windows/macOS: podman machine start）後再執行。" >&2
  exit 1
fi

if [ $# -eq 0 ]; then
  echo "Usage: $0 [start|logs|stop|reload-data]" >&2
  exit 1
fi

ACTION="$1"

case "$ACTION" in
  start)
    podman-compose up -d --build
    echo ""
    echo "服務已啟動。瀏覽器開啟 http://localhost:8000 查看BI網頁。"
    echo "用 './run-podman.sh logs' 追蹤 log。"
    ;;
  logs)
    podman-compose logs -f
    ;;
  stop)
    podman-compose down
    ;;
  reload-data)
    echo "重新執行 ETL，將 data/*.csv 匯入資料庫（db / webapp 不受影響）..."
    podman-compose run --rm etl
    echo "完成。"
    ;;
  *)
    echo "Usage: $0 [start|logs|stop|reload-data]" >&2
    exit 1
    ;;
esac
