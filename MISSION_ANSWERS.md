# Day 14 Lab - Mission Answers

> **Họ và tên:** Nguyễn Hải Anh  
> **MSSV:** 2A202603484  
> **Lớp:** K5-L3A  
> **Môn:** AICB-P1 — Deployment, Benchmark & Observability  

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`

Qua phân tích mã nguồn `develop/app.py`, phát hiện các anti-pattern sau:

1. **Hardcoded Secrets & Connection Strings (Dòng 17, 18):**
   - Mã nguồn chứa trực tiếp `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`.
   - *Nguy cơ:* Nếu vô tình commit lên Git repository, secrets sẽ bị lộ, dẫn đến rò rỉ dữ liệu hoặc bị lợi dụng quota thanh toán.
2. **Không có hệ thống quản lý cấu hình tập trung (Dòng 21, 22):**
   - Các biến cấu hình (`DEBUG = True`, `MAX_TOKENS = 500`) được gán cứng, không đọc từ biến môi trường (`os.getenv`). Không thể thay đổi hành vi giữa các môi trường Dev, Staging, Prod nếu không sửa code.
3. **Sử dụng `print()` thay cho Structured Logging (Dòng 33, 34, 38):**
   - Dùng lệnh `print()` thô sơ, không có timestamp, log level, request_id.
   - Đặc biệt tại dòng 34: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` ghi log cả secret ra stdout/file log, vi phạm nghiêm trọng nguyên tắc an toàn thông tin.
4. **Thiếu Health Check & Readiness Endpoints:**
   - Không có các endpoint `/health` (Liveness) hay `/ready` (Readiness). Container orchestrator (Docker, Kubernetes) hoặc Cloud platform (Railway, Render) không thể phát hiện khi tiến trình bị treo hoặc mất kết nối database để tự động khởi động lại.
5. **Hardcode Port và Host Binding nội bộ (Dòng 50-53):**
   - `host="localhost"` (chỉ lắng nghe loopback `127.0.0.1`), khiến container không thể tiếp nhận request từ bên ngoài (cần lắng nghe `0.0.0.0`).
   - `port=8000` bị gán cứng thay vì đọc từ biến môi trường `PORT` (do các nền tảng PaaS như Cloud Run, Render, Railway cấp phát động).
   - `reload=True` bật debug mode trong production gây tiêu tốn tài nguyên và tiềm ẩn nguy cơ bảo mật.
6. **Không có cơ chế Graceful Shutdown:**
   - Ứng dụng không xử lý tín hiệu `SIGTERM`. Khi container bị dừng đột ngột, các request đang xử lý dở dang sẽ bị cắt đứt lập tức, gây lỗi 502/504 cho người dùng.

---

### Exercise 1.2: Chạy và kiểm tra bản Basic (Develop)

Chạy ứng dụng với lệnh:
```bash
python 01-localhost-vs-production/develop/app.py
```

Gọi thử nghiệm bằng curl (lưu ý: bản develop nhận tham số `question` qua query string):
```bash
curl -i -X POST "http://localhost:8000/ask?question=Hello"
```

**Output phản hồi từ server:**
```http
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:30:15 GMT
server: uvicorn
content-length: 78
content-type: application/json

{"answer":"[Mock LLM] Response for: Hello. Deployment is all about reliability!"}
```

*Nhận xét:* Ứng dụng phản hồi 200 OK trên máy cá nhân, nhưng hoàn toàn không đáp ứng tiêu chuẩn production do thiếu bảo mật, giám sát và khả năng scale.

---

### Exercise 1.3: Comparison Table (12-Factor App Compliance)

| Tiêu chí | Develop (Basic) | Production (Advanced) | Tại sao quan trọng trong Production? |
| :--- | :--- | :--- | :--- |
| **Config & Secrets** | Hardcode trong code Python (`OPENAI_API_KEY`) | Đọc từ Environment Variables qua Pydantic Settings (`config.py`) | Tuân thủ 12-Factor (Config). Dễ dàng chuyển đổi giữa các môi trường Dev/Staging/Prod mà không cần sửa code; ngăn chặn lộ credentials lên GitHub. |
| **Health Check** | Không có | Có `/health` (Liveness) và `/ready` (Readiness) | Nền tảng Cloud/Kubernetes biết được trạng thái container để tự động restart khi process bị treo hoặc chuyển hướng traffic chỉ khi service đã sẵn sàng. |
| **Logging** | Dùng `print()` thô, in cả API key ra stdout | Structured JSON Logging (timestamp, level, message, metadata) | Giúp các hệ thống thu thập log tập trung (Datadog, Grafana Loki, CloudWatch) dễ dàng parse, filter, index và thiết lập cảnh báo khi có lỗi. |
| **Shutdown** | Đột ngột ngắt tiến trình (kill hard) | Bắt `SIGTERM`, dừng nhận traffic, chờ in-flight requests hoàn tất | Không làm mất dữ liệu của người dùng đang gọi API dở dang; ngắt kết nối database/cache sạch sẽ, tránh rò rỉ tài nguyên. |
| **Network Binding** | `localhost:8000` | `0.0.0.0:$PORT` | Cho phép nhận traffic từ ingress controller/reverse proxy ngoài container; tương thích với cơ chế cấp phát cổng động của PaaS. |
| **Reload Mode** | `reload=True` | `reload=False`, multi-worker | Tránh overhead tiêu hao CPU do file watcher; đảm bảo tính ổn định và thông lượng tải cao. |

---

## Part 2: Docker Containerization

### Exercise 2.1: Phân tích Dockerfile cơ bản (`02-docker/develop/Dockerfile`)

1. **Base image là gì?**
   - Base image là `python:3.11`. Đây là full Python distribution dựa trên Debian, chứa đầy đủ trình biên dịch, header packages và công cụ hệ thống (kích thước lớn ~1 GB).
2. **Working directory là gì?**
   - `WORKDIR /app`: Chỉ định thư mục làm việc mặc định bên trong container. Mọi lệnh tiếp theo (`COPY`, `RUN`, `CMD`) đều lấy thư mục này làm mốc tham chiếu.
3. **Tại sao `COPY requirements.txt` trước khi `COPY` source code?**
   - Tận dụng cơ chế **Docker Layer Caching**. Mã nguồn thường xuyên thay đổi, trong khi dependencies rất ít khi cập nhật. Việc copy và chạy `pip install` trước giúp Docker tái sử dụng layer cache của thư viện, giúp thời gian build sau các lần sửa code chỉ mất vài giây thay vì phải cài lại thư viện từ đầu.
4. **Khác biệt giữa `CMD` và `ENTRYPOINT`:**
   - `ENTRYPOINT`: Xác định tiến trình cố định không đổi khi container chạy (thường là executable). Các tham số truyền vào từ `docker run` sẽ được append vào sau `ENTRYPOINT`.
   - `CMD`: Xác định lệnh mặc định hoặc tham số mặc định. `CMD` có thể bị ghi đè hoàn toàn khi truyền lệnh khác qua `docker run`.

---

### Exercise 2.2 & 2.3: Multi-stage Build và So sánh Kích thước Image

#### Cơ chế hoạt động của Multi-stage Dockerfile (`02-docker/production/Dockerfile`):
- **Stage 1 (Builder):** Sử dụng `python:3.11-slim` làm môi trường build. Cài đặt các công cụ biên dịch (`gcc`, `libpq-dev`), sau đó tải và build các thư viện Python vào `/root/.local` bằng lệnh `pip install --user`.
- **Stage 2 (Runtime):** Khởi tạo từ image sạch `python:3.11-slim`, tạo `appuser` (non-root) để tăng cường bảo mật. Chỉ chép kết quả đã build từ `COPY --from=builder /root/.local /home/appuser/.local` và source code vào. Toàn bộ `gcc`, `apt cache` và build tools dư thừa ở Stage 1 bị loại bỏ hoàn toàn.

#### Bảng so sánh dung lượng đo được:

| Image | Kỹ thuật build | Base OS | Kích thước (MB) |
| :--- | :--- | :--- | :---: |
| `my-agent:develop` | Single-stage | `python:3.11` (Full Debian) | **1024 MB** (~1.0 GB) |
| `my-agent:advanced` | Multi-stage | `python:3.11-slim` + Non-root | **188 MB** |
| **Mức chênh lệch / Tối ưu** | | | **Giảm ~81.6%** |

*Ý nghĩa:* Giúp giảm thời gian pull/push image qua CI/CD, tiết kiệm băng thông và disk storage trên server, đồng thời giảm diện tích bề mặt tấn công bảo mật (Attack Surface).

---

### Exercise 2.4: Kiến trúc hệ thống Docker Compose Stack (`02-docker/production/docker-compose.yml`)

#### Sơ đồ kiến trúc giao tiếp:
```text
                       [ Internet / Client ]
                                 │
                            (Port 80/443)
                                 ▼
                     ┌───────────────────────┐
                     │   Nginx Reverse Proxy │
                     │   (Load Balancer)     │
                     └───────────┬───────────┘
                                 │ internal network
                                 ▼
                     ┌───────────────────────┐
                     │     Agent Service     │
                     │  (FastAPI on :8000)   │
                     └─────┬───────────┬─────┘
                           │           │
                 internal  │           │  internal
                     ┌─────▼───┐   ┌───▼─────┐
                     │  Redis  │   │ Qdrant  │
                     │ (:6379) │   │ (:6333) │
                     └─────────┘   └─────────┘
```

#### Cơ chế giao tiếp:
- **Nginx:** Đóng vai trò Reverse Proxy tiếp nhận traffic từ cổng công khai 80, chuyển tiếp request tới service `agent` qua mạng nội bộ Docker.
- **Agent Service:** Chạy FastAPI, không mở port trực tiếp ra host để đảm bảo bảo mật. Agent giao tiếp với:
  - `redis:6379`: Lưu trữ session, cache dữ liệu và thực hiện rate limit.
  - `qdrant:6333`: Cơ sở dữ liệu vector phục vụ truy vấn tìm kiếm tri thức (RAG).
- Thuộc tính `depends_on` với `condition: service_healthy` đảm bảo `redis` và `qdrant` phải sẵn sàng trước khi service `agent` khởi động.

---

## Part 3: Cloud Deployment

### Live Service Deployment (Railway)
- **Public URL:** `https://k5-l3a-day14-nguyenhaianh-2a202603484-deployment-production.up.railway.app`
- **Trạng thái:** Active, đã kết nối Redis, hoàn thành 4/4 lệnh kiểm thử ở CP6 (chi tiết trong `DEPLOYMENT.md`).

### Exercise 3.1 & 3.2: So sánh cấu hình `railway.toml` và `render.yaml`

| Tiêu chí | Railway (`railway.toml`) | Render (`render.yaml`) |
| :--- | :--- | :--- |
| **Định dạng file** | TOML (`config-as-code`) | YAML (Render Blueprint Specification) |
| **Cơ chế Build** | Tự động dò `builder = "NIXPACKS"` hoặc `DOCKERFILE` | Khai báo rõ ràng: `runtime: python` kèm `buildCommand` hoặc `docker` |
| **Cấp phát Cổng (PORT)** | Nền tảng tự inject biến `PORT` ngẫu nhiên; startCommand dùng `$PORT` | Tương tự, inject biến `PORT` vào môi trường container |
| **Quản lý Service phụ thuộc** | Tạo database/Redis qua giao diện Canvas trực quan hoặc plugin | Khai báo đồng thời Web Service và Redis trong cùng file Blueprint (`type: redis`) |
| **Bảo mật Biến môi trường** | Thiết lập qua CLI (`railway variables set`) hoặc Dashboard | Hỗ trợ khai báo thuộc tính `sync: false` (nhập tay trên dashboard) hoặc `generateValue: true` (Render tự sinh khóa bí mật an toàn) |
| **Health Check Path** | `healthcheckPath = "/health"`, kèm cấu hình timeout | `healthCheckPath: /health` |

---

### Exercise 3.3: Phân tích CI/CD Pipeline Google Cloud Run (`cloudbuild.yaml`)

Pipeline CI/CD định nghĩa trong file `03-cloud-deployment/production-cloud-run/cloudbuild.yaml` tự động thực hiện 4 bước khi có code commit vào nhánh `main`:
1. **Step 1 (Test):** Sử dụng container `python:3.11-slim`, cài đặt dependencies và chạy bộ unit test với `pytest tests/ -v`. Nếu test thất bại, pipeline dừng ngay lập tức.
2. **Step 2 (Build Docker Image):** Dùng `gcr.io/cloud-builders/docker` build Docker image từ mã nguồn, gắn tag theo mã commit `$COMMIT_SHA` và tag `latest`, đồng thời tái sử dụng `--cache-from` để tăng tốc độ build.
3. **Step 3 (Push to Registry):** Đẩy các image đã build lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **Step 4 (Deploy to Cloud Run):** Triển khai image mới lên Cloud Run service với cấu hình từ `service.yaml`, phân bổ traffic tự động, hỗ trợ auto-scaling từ 0 lên nhiều instance khi có tải.

---

## Part 4: API Security

### Exercise 4.1, 4.2 & 4.3: Kết quả kiểm thử Security & Rate Limiting

#### 1. Kiểm thử API Key Authentication (`04-api-gateway/develop/app.py`):

- **Trường hợp 1: Không truyền API Key (Kỳ vọng: 401 Unauthorized)**
```bash
curl -i -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
```
*Output:*
```http
HTTP/1.1 401 Unauthorized
content-type: application/json
content-length: 71

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

- **Trường hợp 2: Truyền sai API Key (Kỳ vọng: 403 Forbidden)**
```bash
curl -i -X POST http://localhost:8000/ask \
  -H "X-API-Key: wrong-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
```
*Output:*
```http
HTTP/1.1 403 Forbidden
content-type: application/json
content-length: 31

{"detail":"Invalid API key."}
```

- **Trường hợp 3: Truyền đúng API Key (Kỳ vọng: 200 OK)**
```bash
curl -i -X POST http://localhost:8000/ask \
  -H "X-API-Key: secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
```
*Output:*
```http
HTTP/1.1 200 OK
content-type: application/json

{"answer":"[Mock LLM] Response for: Hello. Deployment is all about reliability!"}
```

---

#### 2. Kiểm thử JWT & Rate Limiting (`04-api-gateway/production/`):

- **Lấy JWT Token:**
```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "demo123"}'
```
*Output:*
```json
{"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...[TOKEN REDACTED]...","token_type":"bearer","expires_in":3600}
```

- **Kiểm thử Rate Limiting (gọi liên tục quá 10 requests/phút):**
Tài khoản `student` bị áp ngưỡng 10 requests/phút bằng thuật toán Sliding Window Counter.
Khi gửi đến request thứ 11 trong vòng 60 giây:
```bash
curl -i -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer <TOKEN_CHE_KHONG_LO>" \
  -H "Content-Type: application/json" \
  -d '{"question":"Spamming request"}'
```
*Output (Kỳ vọng: 429 Too Many Requests):*
```http
HTTP/1.1 429 Too Many Requests
retry-after: 54
content-type: application/json

{"detail":{"error":"Rate limit exceeded","limit":10,"window":"60s","retry_after":54}}
```

---

### Exercise 4.4: Thiết kế và Hiện thực cơ chế Cost Guard

#### Mục đích:
Ngăn ngừa tình trạng người dùng cố tình hoặc vô ý spam các tác vụ tiêu tốn nhiều token LLM, làm cạn kiệt ngân sách API của hệ thống.

#### Cơ chế hiện thực qua Redis:
1. **Key Định danh theo Tháng:** Định dạng `cost:{user_id}:{YYYY-MM}`. Key này được thiết lập `TTL = 32 ngày` để tự động dọn dẹp bộ nhớ.
2. **Atomic Operation trong Redis:**
   - Dùng lệnh `INCRBYFLOAT` để cộng dồn chi phí của từng câu hỏi một cách thread-safe (không bị Race Condition giữa các workers).
3. **Luồng kiểm tra ngân sách:**
   - Trước khi gọi LLM: Kiểm tra `current_cost + estimated_cost > DAILY_BUDGET / MONTHLY_BUDGET`.
   - Nếu vượt quá ngân sách: Lập tức chặn request và trả mã trạng thái `HTTP 402 Payment Required` (kèm thông tin chi phí đã dùng và hạn mức).
   - Nếu còn ngân sách: Cho phép gọi LLM và cập nhật chi phí thực tế vào Redis.

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Check vs Readiness Check

- **Liveness Probe (`GET /health`):**
  - *Mục đích:* Trả lời câu hỏi: *"Tiến trình ứng dụng còn sống không?"*.
  - *Nguyên tắc:* Luôn luôn trả về mã `200 OK` nếu tiến trình Python/FastAPI còn phản hồi. Không phụ thuộc vào Redis hay Database. Nếu endpoint này thất bại hoặc timeout, orchestrator sẽ ra lệnh `kill -9` và khởi động lại container mới.
- **Readiness Probe (`GET /ready`):**
  - *Mục đích:* Trả lời câu hỏi: *"Ứng dụng đã sẵn sàng tiếp nhận và xử lý traffic người dùng chưa?"*.
  - *Nguyên tắc:* Kiểm tra kết nối tới các dịch vụ phụ thuộc sống còn (ping Redis, kiểm tra Database).
    - Nếu Redis phản hồi tốt: Trả về `200 OK`.
    - Nếu Redis mất kết nối hoặc DB bị treo: Trả về `503 Service Unavailable`.
    - *Tác dụng:* Load Balancer sẽ tạm thời tách instance này ra khỏi pool nhận traffic, không đẩy request của người dùng vào đây, tránh tình trạng lỗi hàng loạt trong khi chờ Redis hồi phục.

---

### Exercise 5.2: Cơ chế Graceful Shutdown

Khi container nhận lệnh tắt (`docker stop` hoặc rolling update trên Kubernetes), hệ điều hành sẽ gửi tín hiệu `SIGTERM`.

**Quy trình xử lý Graceful Shutdown chuẩn:**
1. Bắt tín hiệu `SIGTERM` bằng lifespan context manager của FastAPI.
2. Thiết lập cờ `is_ready = False` để endpoint `/ready` lập tức trả về `503`, báo hiệu cho Load Balancer ngắt traffic mới đến instance này.
3. Chờ toàn bộ các in-flight requests (các request đang tính toán hoặc đợi LLM phản hồi) hoàn thành trong khoảng thời gian `grace_period` (ví dụ 10–30 giây).
4. Đóng kết nối cơ sở dữ liệu, ngắt pool Redis sạch sẽ.
5. Thoát tiến trình an toàn với exit code 0 mà không làm đứt kết nối của bất kỳ client nào.

---

### Exercise 5.3: Stateless Architecture

- **Anti-pattern (Stateful in RAM):**
  - Lưu trữ lịch sử hội thoại trong biến toàn cục Python `conversation_history = {}`. Khi hệ thống scale ngang ra nhiều instances (ví dụ 3 instances phía sau Nginx), Request 1 vào Instance A, Request 2 lại bị chuyển sang Instance B. Instance B không có bộ nhớ RAM của Instance A, dẫn đến mất ngữ cảnh hội thoại.
- **Stateless Architecture (External State):**
  - Toàn bộ trạng thái phiên làm việc (session state, history, rate-limit buckets) được lưu trữ tại tầng dữ liệu dùng chung (Redis).
  - Mọi instance agent đều bình đẳng và không lưu trạng thái cục bộ. Một request có thể rơi vào bất kỳ instance nào cũng đều truy xuất được đầy đủ lịch sử từ Redis qua `session_id`.

---

### Exercise 5.4 & 5.5: Kiểm thử Scale Ngang và Stateless qua Nginx

Chạy stack với 3 agent replicas và Nginx:
```bash
docker compose -p k5-day14-scaling up -d --build --scale agent=3
python test_stateless.py
```

**Phân tích kết quả chạy `test_stateless.py`:**
- Script gửi liên tiếp 5 câu hỏi trong cùng một `session_id`.
- Quan sát trường `served_by` trong kết quả phản hồi:
  - Request 1 được xử lý bởi `agent_1`.
  - Request 2 được xử lý bởi `agent_2`.
  - Request 3 được xử lý bởi `agent_3`.
  - Request 4 được xử lý bởi `agent_1`.
  - Request 5 được xử lý bởi `agent_2`.
- Mặc dù 5 requests được phân phối luân phiên tới 3 container khác nhau do Nginx Load Balancer điều phối, nhưng toàn bộ lịch sử 5 lượt hỏi - đáp vẫn được lưu trữ và truy xuất nguyên vẹn từ Redis. Hệ thống hoạt động hoàn hảo dưới mô hình Stateless.

---

## Part 6: Deliverable Checklist

Output từ script chấm `python check_production_ready.py`:

```text
================================================================
  Production Readiness Check — Day 14 Lab
================================================================

✅ 1. Dockerfile (multi-stage, < 500 MB)
     ✅ Dockerfile tồn tại
     ✅ requirements.txt tồn tại
     ✅ Multi-stage build (≥ 2 lệnh FROM)
     ✅ Base image gọn (slim / alpine / distroless) — stage cuối dùng python:3.11-slim
     ✅ Chạy bằng user non-root
     ✅ Có HEALTHCHECK
     ✅ Docker: build image thành công — 44s
     ✅ Docker: image < 500 MB — 238 MB
     ✅ Docker: container chạy được, GET /health → 200

✅ 2. docker-compose.yml (agent + redis)
     ✅ docker-compose.yml tồn tại
     ✅ Có service agent (build từ Dockerfile) + redis — services: agent, redis — đọc bằng docker compose config
     ✅ Service agent kết nối redis (REDIS_URL + depends_on)

✅ 3. .dockerignore
     ✅ .dockerignore tồn tại và có nội dung
     ✅ .dockerignore loại trừ .env (secrets)
     ✅ .dockerignore loại trừ __pycache__, venv

✅ 4. Health check endpoint (GET /health)
     ✅ Code có route /health
     ✅ Khi chạy: GET /health → 200 — uvicorn --workers 2

✅ 5. Readiness endpoint (GET /ready)
     ✅ Code có route /ready
     ✅ Khi chạy: GET /ready → 200
     ✅ Khi chạy: Redis mất kết nối → /ready 503 (còn /health vẫn 200)

✅ 6. API Key authentication
     ✅ Code đọc header X-API-Key
     ✅ Khi chạy: thiếu / sai API key → 401
     ✅ Khi chạy: API key đúng → 200

✅ 7. Rate limiting
     ✅ Code trả HTTP 429 khi vượt giới hạn
     ✅ Khi chạy: vượt giới hạn → 429 — 429 sau 5 request thành công (RATE_LIMIT_PER_MINUTE=5)
     ✅ Khi chạy: state nằm trong Redis — restart agent vẫn bị 429

✅ 8. Cost guard
     ✅ Code trả HTTP 402 khi hết budget
     ✅ Khi chạy: hết budget → 402 — 402 ở request thứ 1

✅ 9. Config từ environment variables
     ✅ app/config.py đọc biến môi trường
     ✅ .env.example liệt kê đủ biến cấu hình
     ✅ .env nằm trong .gitignore
     ✅ Không hard-code secret trong code
     ✅ Khi chạy: agent dùng AGENT_API_KEY và RATE_LIMIT_PER_MINUTE từ env

✅ 10. Structured logging
     ✅ Code ghi log dạng JSON
     ✅ Khi chạy: mọi dòng log của app là JSON hợp lệ — 12 dòng JSON

✅ 11. Graceful shutdown
     ✅ Code xử lý SIGTERM / lifespan shutdown
     ✅ Docker: `docker stop` tắt êm (exit code 0, < 10s) — exit code 0, 0.5s

✅ 12. Public URL ready (Railway / Render config)
     ✅ Có railway.toml hoặc render.yaml (không chỉ toàn comment)
     ✅ railway.toml: builder + healthcheckPath = "/health"
     ✅ render.yaml: web service + healthCheckPath /health
     ✅ render.yaml: secret không ghi thẳng giá trị (generateValue / sync: false)
     ✅ App lắng nghe theo biến PORT do platform cấp

================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · PASS (42/42 checks passed)
================================================================
```

---

## AI Log

Tuân thủ quy định tại [RULES.md](RULES.md):
- **Công cụ sử dụng:** Antigravity AI Assistant.
- **Mục đích hỗ trợ:**
  - Tra cứu và tổng hợp các tiêu chí của 12-Factor App áp dụng cho AI Agent.
  - Phân tích cấu trúc Dockerfile multi-stage, tối ưu layer caching và cơ chế bảo mật non-root user.
  - Thiết kế kiến trúc Stateless với Redis và phân tích cơ chế hoạt động của Liveness/Readiness probes.
- **Kiểm chứng bởi sinh viên:**
  - Đã rà soát từng dòng code trong các thư mục `01-localhost-vs-production`, `02-docker`, `04-api-gateway`, `05-scaling-reliability`.
  - Đối chiếu toàn bộ câu trả lời với tiêu chí chấm của `INSTRUCTOR_GUIDE.md` và `RUBRIC.md`.
