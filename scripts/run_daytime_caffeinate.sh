#!/bin/zsh
set -euo pipefail

# Keep Mac awake only during daytime polling window (8:00 to 22:00 local).
hour=$(date +%H)
minute=$(date +%M)
second=$(date +%S)

hour=$((10#$hour))
minute=$((10#$minute))
second=$((10#$second))

if (( hour < 8 || hour >= 22 )); then
  exit 0
fi

remaining=$(( (22 - hour) * 3600 - minute * 60 - second ))
if (( remaining <= 0 )); then
  exit 0
fi

exec /usr/bin/caffeinate -dimsu -t "$remaining"
