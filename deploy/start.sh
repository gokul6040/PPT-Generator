#!/bin/sh
set -e

export PORT="${PORT:-8501}"
echo "Starting TurnB PPT Agent on port ${PORT}"
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf
