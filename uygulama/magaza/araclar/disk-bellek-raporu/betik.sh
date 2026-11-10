echo "=== HOST: $(hostname) ==="
echo "--- BELLEK (RAM) ---"
free -h | awk 'NR<=2'
echo "--- DİSK ALANI ---"
df -h / /home 2>/dev/null | awk 'NR<=3'
