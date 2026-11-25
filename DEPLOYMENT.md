# Deployment Information — Day 14 Lab

> **Họ và tên:** Nguyễn Hải Anh  
> **MSSV:** 2A202603484  
> **Lớp:** K5-L3A  
> **Môn:** AICB-P1 — Deployment, Benchmark & Observability  

---

## 1. Public Service URL

- **URL:** `https://k5-l3a-day14-nguyenhaianh-2a202603484-deployment-production.up.railway.app`
- **Nền tảng:** Railway
- **Cấu hình:** `railway.toml` (DOCKERFILE builder, Healthcheck `/health`)

---

## 2. Test Commands & Verification (Đã kiểm tra thực tế thành công)

Trước khi thực hiện, đặt các biến môi trường:
```bash
export BASE="https://k5-l3a-day14-nguyenhaianh-2a202603484-deployment-production.up.railway.app"
export AGENT_API_KEY="my-secret-key-123"
```

### Lệnh 1: Liveness Health Check (Đã test: 200 OK)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
# Kết quả thực tế: 200
```

### Lệnh 2: Readiness Check (Đã test: 200 OK khi Redis online)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
# Kết quả thực tế: 200
```

### Lệnh 3: API Test không có Header X-API-Key (Đã test: 401 Unauthorized)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
# Kết quả thực tế: 401
```

### Lệnh 4: API Test có Header X-API-Key hợp lệ (Đã test: 200 OK)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello, what is deployment?"}'
# Kết quả thực tế: 200
```

---

## 3. Environment Variables Đã Thiết Lập Trên Railway

| Biến môi trường | Giá trị | Mục đích |
| :--- | :--- | :--- |
| `PORT` | `8000` *(Railway inject tự động)* | Cổng dịch vụ lắng nghe |
| `ENVIRONMENT` | `production` | Môi trường production |
| `AGENT_API_KEY` | *(Khóa bí mật bạn đã đặt)* | Xác thực API Key cho client |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` | Kết nối Redis nội bộ lưu rate limit & cost guard |
| `RATE_LIMIT_PER_MINUTE` | `10` | Giới hạn 10 requests/phút |
| `DAILY_BUDGET_USD` | `10.0` | Giới hạn ngân sách chi phí/ngày |

---

## 4. Screenshots Minh Chứng

- Dashboard dịch vụ: [screenshots/dashboard.png](screenshots/dashboard.png)
- Service running & logs: [screenshots/running.png](screenshots/running.png)
- Kết quả test 4 lệnh: [screenshots/test.png](screenshots/test.png)
