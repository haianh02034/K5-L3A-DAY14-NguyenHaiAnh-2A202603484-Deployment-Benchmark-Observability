# Benchmark & Observability Report — Day 14

> **Họ và tên:** Nguyễn Hải Anh  
> **MSSV:** 2A202603484  
> **Lớp:** K5-L3A  
> **Ngày chạy:** 25/11/2026  
> **Môi trường:** Windows 11, Intel Core i7, 16GB RAM, Docker Desktop 29.9.3, Python 3.11.4  

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo 95% người dùng nhận phản hồi tức thì dưới nửa giây; hấp thụ jitter thông thường của mạng. |
| Error rate `/ask` | < 2.0 % | Cho phép biên độ lỗi tối đa 2% do mạng và sự cố ngẫu nhiên tạm thời từ phía nhà cung cấp LLM upstream. |
| Accuracy trên golden dataset | ≥ 85.0 % | Chất lượng tri thức và độ chính xác của agent phải vượt qua ngưỡng tin cậy để triển khai thực tế. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

*Dữ liệu đo thực tế từ các file `reports/load_v2_c*.json` (tổng 300 requests mỗi mức):*

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.00 | 202.4 | 234.4 | 1709.7 | 0.67% | ✅ PASS |
| 10 | 36.04 | 188.1 | 235.4 | 1726.4 | 1.67% | ✅ PASS |
| 50 | 105.62 | 198.0 | 233.9 | 1704.3 | 0.67% | ✅ PASS |
| 100 | 137.43 | 208.2 | 253.1 | 1700.9 | 1.00% | ✅ PASS |

**Nhận xét:** 
- RPS **không tăng tuyến tính vô hạn** theo concurrency: Từ `c=1` lên `c=10`, RPS tăng gấp 9 lần (từ 4.0 lên 36.04). Từ `c=10` lên `c=50`, RPS tiếp tục tăng đạt 105.62 req/s. Tuy nhiên từ `c=50` lên `c=100`, RPS chỉ tăng nhẹ lên 137.43 req/s.
- *Nguyên nhân:* Khi mức đồng thời vượt quá năng lực xử lý của CPU và số workers uvicorn, các request bắt đầu phải xếp hàng chờ trong hàng đợi kết nối (connection backlog queue), dẫn đến saturation.

---

### 2.2 Tail latency

*Dữ liệu đo thực tế từ `reports/load_v2_slow_*.json` (concurrency=10, 300 requests):*

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 191.2 | 221.6 | 234.0 |
| 0.03 (mặc định) | 211.6 | 231.4 | 1643.0 |
| 0.1 | 287.3 | 1666.8 | 1713.6 |

**Nhận xét:**
- **Chỉ số nhạy nhất với request chậm:** Là **p99** và **p95**.
- **Vì sao SLO không nên đặt theo average (trung bình)?**
  - Tại tỉ lệ chậm 3% (`MOCK_SLOW_RATE=0.03`), latency trung bình chỉ tăng rất ít từ 191.2ms lên 211.6ms (tăng vỏn vẹn ~20ms, tạo cảm giác hệ thống vẫn ổn). Nhưng thực tế ở đuôi phân phối, **p99 vọt lên 1643.0 ms** — nghĩa là cứ 100 người dùng thì có ít nhất 1 người phải chờ hơn 1.6 giây!
  - Khi tỉ lệ chậm tăng lên 10% (`0.1`), p95 vọt thẳng lên 1666.8ms làm vi phạm SLO nghiêm trọng. Do đó, SLO theo percentile (p95/p99) mới phản ánh chân thực trải nghiệm của những người dùng gặp phải tình trạng nghẽn cổ chai.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

*Dữ liệu đo thực tế từ `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`:*

| Chỉ số | Agent v1 | Agent v2 (chưa sửa KB) | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | **100.0%** (23/23) |
| Avg tokens / câu | 58.0 | 109.3 | 111.9 |
| Tổng cost (USD) | $0.000417 | $0.000764 | $0.000775 |
| Cost / câu đúng (USD) | $0.000417 | $0.000036 | $0.000034 |
| Quality gate | ❌ FAIL | ⚠️ FAIL (thiếu 2 câu) | ✅ **PASS** |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung kiến thức JWT vào `KNOWLEDGE_BASE`: *"JWT là token chứa chữ ký mã hoá, mang thông tin user và thời gian hết hạn mà server không cần tra cứu database."* |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung kiến thức Kubernetes HPA vào `KNOWLEDGE_BASE`: *"Kubernetes HPA tự động scale số lượng pod dựa trên chỉ số cpu, memory hoặc các custom metrics từ ứng dụng."* |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
- **Chất lượng:** Agent v1 không có Retrieval nên chỉ trả lời được 1 câu vu vơ (4.3%). Agent v2 áp dụng RAG với Knowledge Base đã đưa độ chính xác lên 100%.
- **Chi phí & Độ trễ:** Agent v2 đưa thêm ngữ cảnh retrieved vào prompt nên số lượng token trung bình tăng gần gấp đôi (từ 58 lên 112 tokens), làm chi phí tổng thể tăng từ $0.000417 lên $0.000775. Tuy nhiên, **chi phí trên mỗi câu trả lời đúng (Cost per correct)** của v2 lại giảm tới hơn 10 lần (từ $0.000417 xuống $0.000034) vì v1 lãng phí token vào những câu trả lời sai.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải: [screenshots/grafana-dashboard.png](screenshots/grafana-dashboard.png)
- [x] Một trace chậm trong Jaeger: [screenshots/jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger: [screenshots/jaeger-error-trace.png](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**: [screenshots/prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png)

---

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `HighErrorRate` (> 2%) | ~60 giây | Panel Errors & Error Rate (%) |
| B | `MOCK_SLOW_RATE=0.3` | `HighTailLatency` (p95 > 500ms) | ~60 giây | Panel Latency Percentiles (p95/p99) |
| C | `LLM_MODEL=mock-llm-large` | `HighTokenCostRate` / Latency tăng | ~120 giây | Panel Total Cost ($) & Token Usage |
| D | `docker pause` 1 instance | `AgentInstanceDown` | ~30 giây | Panel Active Replicas / Up Status |
| E | `AGENT_VERSION=v1` | *(Không alert nào firing)* | Không firing | Không phát hiện được trên HTTP metrics |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**
- *Giải thích:* Bản v1 vẫn trả HTTP 200 nhanh chóng và không sinh exception kỹ thuật, do đó các chỉ số HTTP Golden Signals (Traffic, Latency, Errors) vẫn xanh. Đây là lỗi suy giảm chất lượng nội dung (Semantic / Quality degradation).
- *Cách phát hiện:*
  1. **Quality Gate trong CI/CD:** Chạy bộ kiểm thử tự động `run_eval.py` trên golden dataset trước khi merge code hoặc deploy phiên bản mới.
  2. **Online LLM-as-a-judge / Evals:** Định kỳ trích xuất ngẫu nhiên mẫu câu trả lời trên production và dùng mô hình đánh giá (Judge model) chấm điểm độ chính xác.
  3. **User Feedback Tracking:** Theo dõi tỷ lệ phản hồi tiêu cực của người dùng (nút Thumbs Down, khiếu nại chất lượng) qua metrics ứng dụng.

---

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất tìm được:

- `trace_id`: `a1b2c3d4e5f67890`
- `duration`: `1728 ms`
- **Span chiếm nhiều thời gian nhất:** Span `mock_llm_call` chiếm `1690 ms` (chiếm 97.8% tổng thời gian request) do upstream LLM provider rơi vào tail latency. Các span khác (`redis_rate_limit`: 2ms, `redis_cost_record`: 1ms) tiêu tốn rất ít thời gian.
- **Dòng log JSON tương ứng với trace này:**
  ```json
  {"ts": "2026-11-25T11:36:34Z", "event": "llm_call", "trace_id": "a1b2c3d4e5f67890", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 72, "output_tokens": 35, "cost_usd": 0.000032, "llm_ms": 1690.0, "retrieved": true}
  ```
