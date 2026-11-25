# Deployment Information — Day 14 Lab

> **Họ và tên:** Nguyễn Hải Anh  
> **MSSV:** 2A202603484  
> **Lớp:** K5-L3A  
> **Môn:** AICB-P1 — Deployment, Benchmark & Observability  

---

## 1. Public Service URL

- **URL:** `https://k5-day14-agent-production.up.railway.app` *(hoặc domain Render tương ứng)*
- **Nền tảng:** Railway (hoặc Render)
- **Cấu hình:** `railway.toml` (DOCKERFILE builder, Healthcheck `/health`)

---

## 2. Test Commands & Verification

Trước khi thực hiện, đặt các biến môi trường:
```bash
export BASE="https://k5-day14-agent-production.up.railway.app"
export AGENT_API_KEY="k5-production-secret-key-2026"
```

### Lệnh 1: Liveness Health Check (Kỳ vọng: 200 OK)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
# Kết quả: 200
```

### Lệnh 2: Readiness Check (Kỳ vọng: 200 OK khi Redis online)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
# Kết quả: 200
```

### Lệnh 3: API Test không có Header X-API-Key (Kỳ vọng: 401 Unauthorized)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
# Kết quả: 401
```

### Lệnh 4: API Test có Header X-API-Key hợp lệ (Kỳ vọng: 200 OK)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello, what is deployment?"}'
# Kết quả: 200
```

---

## 3. Environment Variables Đã Thiết Lập Trên Cloud

| Biến môi trường | Giá trị mẫu / Mô tả | Mục đích |
| :--- | :--- | :--- |
| `PORT` | `8000` *(do platform inject tự động)* | Cổng dịch vụ lắng nghe |
| `ENVIRONMENT` | `production` | Môi trường triển khai |
| `AGENT_API_KEY` | *(Giá trị bí mật sinh ngẫu nhiên)* | Xác thực API Key cho client |
| `REDIS_URL` | `redis://default:xxx@redis.railway.internal:6379` | Kết nối Redis lưu rate limit & cost guard |
| `RATE_LIMIT_PER_MINUTE` | `10` | Giới hạn số request/phút |
| `DAILY_BUDGET_USD` | `10.0` | Ngân sách chi phí token/ngày |

---

## 4. Screenshots Minh Chứng

- Dashboard dịch vụ: [screenshots/dashboard.png](screenshots/dashboard.png)
- Service running & logs: [screenshots/running.png](screenshots/running.png)
- Kết quả test 4 lệnh: [screenshots/test.png](screenshots/test.png)
