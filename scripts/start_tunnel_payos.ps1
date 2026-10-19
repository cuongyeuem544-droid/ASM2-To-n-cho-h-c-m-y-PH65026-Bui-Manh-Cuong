# Script khoi tao HTTPS Tunnel cho Webhook payOS (Localhost -> Internet)
# Dung de nhan Webhook chuyen khoan thuc tu payOS khi chay du an tai localhost

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "       H4CARE - HUONG DAN CAU HINH HTTPS TUNNEL CHO PAYOS        " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. payOS yeu cau Webhook URL phai la HTTPS co the truy cap cong khai." -ForegroundColor Yellow
Write-Host "   Dia chi Backend localhost can mo cong: 8000 (FastAPI)" -ForegroundColor Yellow
Write-Host ""
Write-Host ">>> Cac cach mo HTTPS Tunnel mien phi:" -ForegroundColor Green
Write-Host ""
Write-Host "  [Cach 1 - Tien loi nhat, khong can cai dat]: Dung localtunnel qua npx" -ForegroundColor White
Write-Host "    Lenh: npx localtunnel --port 8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "  [Cach 2 - On dinh cao, khong mat phi]: Dung Cloudflare Tunnel (cloudflared)" -ForegroundColor White
Write-Host "    Lenh: cloudflared tunnel --url http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "  [Cach 3]: Dung ngrok" -ForegroundColor White
Write-Host "    Lenh: ngrok http 8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "-----------------------------------------------------------------" -ForegroundColor Gray
Write-Host "2. SAU KHI CO LINK HTTPS (Vi du: https://xyz-abc.loca.lt):" -ForegroundColor Green
Write-Host "   URL Webhook chinh thuc cua H4CARE se la:" -ForegroundColor White
Write-Host "   https://<TEN-MIEN-TUNNEL>/api/v1/payments/payos/webhook" -ForegroundColor Magenta
Write-Host ""
Write-Host "3. CAU HINH TREN DASHBOARD PAYOS:" -ForegroundColor Green
Write-Host "   Buoc 1: Dang nhap https://my.payos.vn" -ForegroundColor White
Write-Host "   Buoc 2: Chon Kênh thanh toán -> Chon Ung dung H4CARE cua ban" -ForegroundColor White
Write-Host "   Buoc 3: Keo xuong muc 'Webhook' -> Dien URL Webhook o tren vao o Webhook URL" -ForegroundColor White
Write-Host "   Buoc 4: Bam 'Luu' va bam 'Kiem tra Webhook' de payOS gui goi tin test." -ForegroundColor White
Write-Host "=================================================================" -ForegroundColor Cyan

$choice = Read-Host "Ban co muon khoi chay localtunnel ngay bay gio khong? (Y/N)"
if ($choice -eq "Y" -or $choice -eq "y") {
    Write-Host "Dang khoi chay localtunnel tren port 8000..." -ForegroundColor Green
    npx localtunnel --port 8000
}
