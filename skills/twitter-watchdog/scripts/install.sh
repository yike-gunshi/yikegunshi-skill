#!/bin/bash
# Twitter Watchdog 定时任务安装脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_FILE="$PROJECT_DIR/assets/com.user.twitter-watchdog.plist"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/com.user.twitter-watchdog.plist"
PYTHON_SCRIPT="$PROJECT_DIR/scripts/twitter_watchdog.py"

echo "🐕 Twitter Watchdog 定时任务安装"
echo "================================"
echo ""

# 检查 Python 3
echo "📦 检查 Python 3..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python 3"
    echo "请先安装 Python 3: brew install python3"
    exit 1
fi
echo "✅ Python 3 已安装: $(python3 --version)"

# 检查并安装依赖
echo ""
echo "📦 检查 Python 依赖..."
MISSING_DEPS=()

if ! python3 -c "import requests" 2>/dev/null; then
    MISSING_DEPS+=("requests")
fi

if ! python3 -c "import yaml" 2>/dev/null; then
    MISSING_DEPS+=("pyyaml")
fi

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo "⚠️  缺少以下依赖: ${MISSING_DEPS[*]}"
    echo "📥 正在安装..."
    pip3 install "${MISSING_DEPS[@]}"
fi

echo "✅ 所有依赖已安装"

# 检查配置文件
echo ""
echo "⚙️  检查配置文件..."
CONFIG_FILE="$PROJECT_DIR/config/config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 错误: 配置文件不存在 $CONFIG_FILE"
    exit 1
fi

# 检查是否需要修改默认配置
if grep -q "your_twitter_username" "$CONFIG_FILE"; then
    echo "⚠️  请先配置你的 Twitter 用户名"
    echo "   编辑文件: $CONFIG_FILE"
    echo "   修改 'username: your_twitter_username' 为你的实际用户名"
    echo ""
    read -p "按回车继续（如已配置）或 Ctrl+C 取消..."
fi

echo "✅ 配置文件检查完成"

# 测试运行一次
echo ""
echo "🧪 测试运行..."
if python3 "$PYTHON_SCRIPT" --test 2>/dev/null || true; then
    echo "✅ 测试运行成功"
else
    echo "⚠️  测试运行可能有问题，请检查配置"
fi

# 安装 launchd 配置
echo ""
echo "📋 安装 launchd 定时任务..."

# 复制 plist 文件
cp "$PLIST_FILE" "$LAUNCHD_PLIST"

# 加载任务
launchctl load "$LAUNCHD_PLIST" 2>/dev/null || {
    echo "⚠️  任务可能已存在，尝试卸载后重新加载..."
    launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
    launchctl load "$LAUNCHD_PLIST"
}

echo "✅ 定时任务已加载"

# 显示任务状态
echo ""
echo "📊 任务状态:"
launchctl list | grep twitter-watchdog || echo "  任务未在列表中（可能还未首次运行）"

# 完成
echo ""
echo "✅ 安装完成！"
echo ""
echo "📂 数据目录: ./twitter_watchdog/"
echo "📝 日志文件:"
echo "   - /tmp/twitter_watchdog.log"
echo "   - /tmp/twitter_watchdog_errors.log"
echo ""
echo "⏰ 抓取频率: 每小时一次"
echo ""
echo "🔧 管理命令:"
echo "   查看状态: launchctl list | grep twitter-watchdog"
echo "   停止任务: launchctl unload $LAUNCHD_PLIST"
echo "   重启任务: launchctl load $LAUNCHD_PLIST"
echo "   查看日志: tail -f /tmp/twitter_watchdog.log"
echo ""
echo "💡 提示:"
echo "   - 修改配置文件后，需要重启任务: launchctl unload $LAUNCHD_PLIST && launchctl load $LAUNCHD_PLIST"
echo "   - 修改抓取频率，编辑 plist 文件中的 StartInterval 值（秒）"
echo "   - 立即运行一次: python3 $PYTHON_SCRIPT"
