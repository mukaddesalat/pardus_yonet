GW=$(ip route | awk '/default/ {print $3}' | head -n1)
echo "=== Ağ Geçidi: $GW ==="
if [ -n "$GW" ]; then
  ping -c 3 -W 2 "$GW" || echo "Ağ geçidine ulaşılamadı!"
fi
echo "=== DNS Testi (195.175.39.39) ==="
ping -c 2 -W 2 195.175.39.39 2>/dev/null || echo "Dış DNS erişimi başarısız!"
