#!/bin/bash

# Get GPU (VRAM) info
echo "GPU (VRAM)"
if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_INFO=$(nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$GPU_INFO" ]; then
        GPU_COUNT=$(echo "$GPU_INFO" | wc -l | xargs)
        echo "Detected GPUs: $GPU_COUNT"
        echo ""
        while IFS=',' read -r GPU_INDEX GPU_NAME GPU_CORE_UTIL GPU_USED GPU_TOTAL; do
            GPU_INDEX=$(echo "$GPU_INDEX" | xargs)
            GPU_NAME=$(echo "$GPU_NAME" | xargs)
            GPU_CORE_UTIL=$(echo "$GPU_CORE_UTIL" | xargs)
            GPU_USED=$(echo "$GPU_USED" | xargs)
            GPU_TOTAL=$(echo "$GPU_TOTAL" | xargs)

            GPU_PERCENT=$(awk -v used="$GPU_USED" -v total="$GPU_TOTAL" 'BEGIN {printf "%.1f", (used / total) * 100}')
            GPU_TOTAL_GB=$(awk -v total="$GPU_TOTAL" 'BEGIN {printf "%.0f", total / 1024}')

            echo "------------------------------"
            echo "GPU $GPU_INDEX: $GPU_NAME"
            echo "Core Utilization: $GPU_CORE_UTIL%"
            echo "Used: $GPU_USED MiB"
            echo "Total: $GPU_TOTAL MiB ($GPU_TOTAL_GB GB)"
            echo "Usage Percentage: $GPU_PERCENT%"
            echo ""
        done <<< "$GPU_INFO"
    else
        echo "nvidia-smi is available, but GPU metrics could not be read"
    fi
else
    echo "nvidia-smi not found (NVIDIA driver/toolkit not available in PATH)"
fi

echo ""

# Get RAM info
echo "RAM"
RAM_INFO=$(free -b | grep Mem)
RAM_USED=$(echo "$RAM_INFO" | awk '{printf "%.0f", $3 / 1024 / 1024}')
RAM_TOTAL=$(echo "$RAM_INFO" | awk '{printf "%.0f", $2 / 1024 / 1024 / 1024}')
RAM_AVAILABLE_GB=$(echo "$RAM_INFO" | awk '{printf "%.0f", $7 / 1024 / 1024 / 1024}')
RAM_PERCENT=$(echo "$RAM_INFO" | awk '{printf "%.1f", ($3 / $2) * 100}')

RAM_USED_GB=$(awk -v used="$RAM_USED" 'BEGIN {printf "%.1f", used / 1024}')

echo "Used: ${RAM_USED} MiB (~${RAM_USED_GB} GB)"
echo "Total: $RAM_TOTAL GB"
echo "Available: $RAM_AVAILABLE_GB GB"
echo "Usage Percentage: ~$RAM_PERCENT%"

echo ""

# Get CPU info
echo "CPU"
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us//')
echo "Current Usage: $CPU_USAGE%"
