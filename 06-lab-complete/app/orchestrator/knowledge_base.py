"""Lightweight lexical KB search for deploy-friendly retrieval."""
from __future__ import annotations

import math
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DOCS_DIR = Path(__file__).resolve().parent / "data" / "docs"
TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)
STOPWORDS = {
    "va",
    "và",
    "la",
    "là",
    "cua",
    "của",
    "cho",
    "trong",
    "the",
    "a",
    "an",
    "to",
    "is",
    "are",
    "do",
    "does",
    "khong",
    "không",
    "gi",
    "gì",
    "bao",
    "nhieu",
    "nhiêu",
    "nao",
    "nào",
    "duoc",
    "được",
    "co",
    "có",
    "voi",
    "với",
    "vong",
    "vòng",
    "ngay",
    "ngày",
    "theo",
    "noi",
    "nội",
    "bo",
    "bộ",
}

EMBEDDED_DOCS: dict[str, str] = {
    "sla_p1_2026.txt": """SLA TICKET - QUY ĐỊNH XỬ LÝ SỰ CỐ
Source: support/sla-p1-2026.pdf
Department: IT
Effective Date: 2026-01-15
Access: internal

=== Phần 1: Định nghĩa mức độ ưu tiên ===

P1 — CRITICAL (Khẩn cấp):
Định nghĩa: Sự cố ảnh hưởng toàn bộ hệ thống production, không có workaround.
Ví dụ: Database sập, API gateway down, toàn bộ người dùng không thể đăng nhập.

P2 — HIGH (Nghiêm trọng):
Định nghĩa: Sự cố ảnh hưởng một phần hệ thống, có workaround tạm thời.
Ví dụ: Một số tính năng không hoạt động, ảnh hưởng một nhóm người dùng.

P3 — MEDIUM (Trung bình):
Định nghĩa: Lỗi ảnh hưởng không đáng kể, người dùng vẫn làm việc được.

P4 — LOW (Thấp):
Định nghĩa: Yêu cầu cải tiến, gợi ý, hoặc lỗi giao diện nhỏ.

=== Phần 2: SLA theo mức độ ưu tiên ===

Ticket P1:
- Phản hồi ban đầu (first response): 15 phút kể từ khi ticket được tạo.
- Xử lý và khắc phục (resolution): 4 giờ.
- Escalation: Tự động escalate lên Senior Engineer nếu không có phản hồi trong 10 phút.
- Thông báo stakeholder: Ngay khi nhận ticket, update mỗi 30 phút cho đến khi resolve.

Ticket P2:
- Phản hồi ban đầu: 2 giờ.
- Xử lý và khắc phục: 1 ngày làm việc.
- Escalation: Tự động escalate sau 90 phút không có phản hồi.

Ticket P3:
- Phản hồi ban đầu: 1 ngày làm việc.
- Xử lý và khắc phục: 5 ngày làm việc.

Ticket P4:
- Phản hồi ban đầu: 3 ngày làm việc.
- Xử lý và khắc phục: Theo sprint cycle (thông thường 2-4 tuần).

=== Phần 3: Quy trình xử lý sự cố P1 ===

Bước 1: Tiếp nhận
On-call engineer nhận alert hoặc ticket, xác nhận severity trong 5 phút.

Bước 2: Thông báo
Gửi thông báo tới Slack #incident-p1 và email incident@company.internal ngay lập tức.

Bước 3: Triage và phân công
Lead Engineer phân công engineer xử lý trong 10 phút.

Bước 4: Xử lý
Engineer cập nhật tiến độ lên ticket mỗi 30 phút. Nếu cần hỗ trợ thêm, escalate ngay.

Bước 5: Resolution
Sau khi khắc phục, viết incident report trong vòng 24 giờ.

=== Phần 4: Công cụ và kênh liên lạc ===
Ticket system: Jira (project IT-SUPPORT)
Slack channel: #incident-p1, #incident-p2
PagerDuty: Tự động nhắn on-call khi P1 ticket mới
Hotline on-call: ext. 9999 (24/7)

=== Phần 5: Lịch sử phiên bản ===
v2026.1 (2026-01-15): Cập nhật SLA P1 resolution từ 6 giờ xuống 4 giờ.
v2025.3 (2025-09-01): Thêm quy trình escalation tự động.
v2025.1 (2025-03-01): Phiên bản đầu tiên.
""",
    "policy_refund_v4.txt": """CHÍNH SÁCH HOÀN TIỀN - PHIÊN BẢN 4
Source: policy/refund-v4.pdf
Department: CS
Effective Date: 2026-02-01
Access: internal

=== Điều 1: Phạm vi áp dụng ===
Chính sách này áp dụng cho tất cả các đơn hàng được đặt trên hệ thống nội bộ kể từ ngày 01/02/2026.
Các đơn hàng đặt trước ngày có hiệu lực sẽ áp dụng theo chính sách hoàn tiền phiên bản 3.

=== Điều 2: Điều kiện được hoàn tiền ===
Khách hàng được quyền yêu cầu hoàn tiền khi đáp ứng đủ các điều kiện sau:
- Sản phẩm bị lỗi do nhà sản xuất, không phải do người dùng.
- Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.
- Đơn hàng chưa được sử dụng hoặc chưa bị mở seal.

=== Điều 3: Điều kiện áp dụng và ngoại lệ ===
Hoàn tiền — Điều kiện áp dụng:
Yêu cầu được gửi trong vòng 7 ngày kể từ thời điểm xác nhận đơn hàng.

Ngoại lệ không được hoàn tiền:
- Sản phẩm thuộc danh mục hàng kỹ thuật số (license key, subscription).
- Đơn hàng đã áp dụng mã giảm giá đặc biệt theo chương trình khuyến mãi Flash Sale.
- Sản phẩm đã được kích hoạt hoặc đăng ký tài khoản.

=== Điều 4: Quy trình xử lý yêu cầu hoàn tiền ===
Bước 1: Khách hàng gửi yêu cầu qua hệ thống ticket nội bộ với category "Refund Request".
Bước 2: CS Agent xem xét trong vòng 1 ngày làm việc và xác nhận điều kiện đủ điều kiện.
Bước 3: Nếu đủ điều kiện, chuyển yêu cầu sang Finance Team để xử lý hoàn tiền.
Bước 4: Finance Team xử lý trong 3-5 ngày làm việc và thông báo kết quả cho khách hàng.

=== Điều 5: Hình thức hoàn tiền ===
- Hoàn tiền qua phương thức thanh toán gốc: áp dụng trong 100% trường hợp đủ điều kiện.
- Hoàn tiền qua credit nội bộ (store credit): khách hàng có thể chọn nhận store credit thay thế với giá trị 110% so với số tiền hoàn.

=== Điều 6: Liên hệ và hỗ trợ ===
Email: cs-refund@company.internal
Hotline nội bộ: ext. 1234
Giờ làm việc: Thứ 2 - Thứ 6, 8:00 - 17:30
""",
    "access_control_sop.txt": """QUY TRÌNH KIỂM SOÁT TRUY CẬP HỆ THỐNG (ACCESS CONTROL SOP)
Source: it/access-control-sop.md
Department: IT Security
Effective Date: 2026-01-01
Access: internal

Ghi chú: Tài liệu này trước đây có tên "Approval Matrix for System Access".

=== Section 1: Phạm vi và mục đích ===
Tài liệu này quy định quy trình cấp phép truy cập vào các hệ thống nội bộ của công ty.
Áp dụng cho tất cả nhân viên, contractor, và third-party vendor.

=== Section 2: Phân cấp quyền truy cập ===

Level 1 — Read Only:
Áp dụng cho: Tất cả nhân viên mới trong 30 ngày đầu.
Phê duyệt: Line Manager.
Thời gian xử lý: 1 ngày làm việc.

Level 2 — Standard Access:
Áp dụng cho: Nhân viên chính thức đã qua thử việc.
Phê duyệt: Line Manager + IT Admin.
Thời gian xử lý: 2 ngày làm việc.

Level 3 — Elevated Access:
Áp dụng cho: Team Lead, Senior Engineer, Manager.
Phê duyệt: Line Manager + IT Admin + IT Security.
Thời gian xử lý: 3 ngày làm việc.

Level 4 — Admin Access:
Áp dụng cho: DevOps, SRE, IT Admin.
Phê duyệt: IT Manager + CISO.
Thời gian xử lý: 5 ngày làm việc.
Yêu cầu thêm: Training bắt buộc về security policy.

=== Section 3: Quy trình yêu cầu cấp quyền ===

Bước 1: Nhân viên tạo Access Request ticket trên Jira (project IT-ACCESS).
Bước 2: Line Manager phê duyệt yêu cầu trong 1 ngày làm việc.
Bước 3: IT Admin kiểm tra compliance và cấp quyền.
Bước 4: IT Security review với Level 3 và Level 4.
Bước 5: Nhân viên nhận thông báo qua email khi quyền được cấp.

=== Section 4: Escalation khi cần thay đổi quyền hệ thống ===
Escalation chỉ áp dụng khi cần thay đổi quyền hệ thống ngoài quy trình thông thường.
Ví dụ: Khẩn cấp trong sự cố P1, cần cấp quyền tạm thời để fix incident.

Quy trình escalation khẩn cấp:
1. On-call IT Admin có thể cấp quyền tạm thời (max 24 giờ) sau khi được Tech Lead phê duyệt bằng lời.
2. Sau 24 giờ, phải có ticket chính thức hoặc quyền bị thu hồi tự động.
3. Mọi quyền tạm thời phải được ghi log vào hệ thống Security Audit.

=== Section 5: Thu hồi quyền truy cập ===
Quyền phải được thu hồi trong các trường hợp:
- Nhân viên nghỉ việc: Thu hồi ngay trong ngày cuối.
- Hết hạn contract: Thu hồi đúng ngày hết hạn.
- Chuyển bộ phận: Điều chỉnh trong 3 ngày làm việc.

=== Section 6: Audit và review định kỳ ===
IT Security thực hiện access review mỗi 6 tháng.
Mọi bất thường phải được báo cáo lên CISO trong vòng 24 giờ.

=== Section 7: Công cụ liên quan ===
Ticket system: Jira (project IT-ACCESS)
IAM system: Okta
Audit log: Splunk
Email: it-access@company.internal
""",
    "it_helpdesk_faq.txt": """IT HELPDESK FAQ — CÂU HỎI THƯỜNG GẶP
Source: support/helpdesk-faq.md
Department: IT
Effective Date: 2026-01-20
Access: internal

=== Section 1: Tài khoản và mật khẩu ===

Q: Tôi quên mật khẩu, phải làm gì?
A: Truy cập https://sso.company.internal/reset hoặc liên hệ Helpdesk qua ext. 9000. Mật khẩu mới sẽ được gửi qua email công ty trong vòng 5 phút.

Q: Tài khoản bị khóa sau bao nhiêu lần đăng nhập sai?
A: Tài khoản bị khóa sau 5 lần đăng nhập sai liên tiếp. Để mở khóa, liên hệ IT Helpdesk hoặc tự reset qua portal SSO.

Q: Mật khẩu cần thay đổi định kỳ không?
A: Có. Mật khẩu phải được thay đổi mỗi 90 ngày. Hệ thống sẽ nhắc nhở 7 ngày trước khi hết hạn.

=== Section 2: VPN và kết nối từ xa ===

Q: Phần mềm VPN nào công ty dùng?
A: Công ty sử dụng Cisco AnyConnect. Download tại https://vpn.company.internal/download.

Q: Tôi bị mất kết nối VPN liên tục, phải làm gì?
A: Kiểm tra kết nối Internet trước. Nếu vẫn lỗi, tạo ticket P3 với log file VPN đính kèm.

Q: VPN có giới hạn số thiết bị không?
A: Mỗi tài khoản được kết nối VPN trên tối đa 2 thiết bị cùng lúc.

=== Section 3: Phần mềm và license ===

Q: Tôi cần cài phần mềm mới, phải làm gì?
A: Gửi yêu cầu qua Jira project IT-SOFTWARE. Line Manager phải phê duyệt trước khi IT cài đặt.

Q: Ai chịu trách nhiệm gia hạn license phần mềm?
A: IT Procurement team quản lý tất cả license. Nhắc nhở sẽ được gửi 30 ngày trước khi hết hạn.

=== Section 4: Thiết bị và phần cứng ===

Q: Laptop mới được cấp sau bao lâu khi vào công ty?
A: Laptop được cấp trong ngày onboarding đầu tiên. Nếu có vấn đề, liên hệ HR hoặc IT Admin.

Q: Laptop bị hỏng phải báo cáo như thế nào?
A: Tạo ticket P2 hoặc P3 tùy mức độ nghiêm trọng. Mang thiết bị đến IT Room (tầng 3) để kiểm tra.

=== Section 5: Email và lịch ===

Q: Hộp thư đến đầy, phải làm gì?
A: Xóa email cũ hoặc yêu cầu tăng dung lượng qua ticket IT-ACCESS. Dung lượng tiêu chuẩn là 50GB.

Q: Tôi không nhận được email từ bên ngoài?
A: Kiểm tra thư mục Spam trước. Nếu vẫn không có, tạo ticket P2 kèm địa chỉ email gửi và thời gian gửi.

=== Section 6: Liên hệ IT Helpdesk ===
Hotline: ext. 9000 (8:00 - 18:00, Thứ 2 - Thứ 6)
Email: helpdesk@company.internal
Jira: project IT-SUPPORT
Slack: #it-helpdesk
Emergency (ngoài giờ): ext. 9999
""",
    "hr_leave_policy.txt": """CHÍNH SÁCH NGHỈ PHÉP VÀ PHÚC LỢI NHÂN SỰ
Source: hr/leave-policy-2026.pdf
Department: HR
Effective Date: 2026-01-01
Access: internal

=== Phần 1: Các loại nghỉ phép ===

1.1 Nghỉ phép năm (Annual Leave):
- Số ngày: 12 ngày/năm cho nhân viên dưới 3 năm kinh nghiệm.
- Số ngày: 15 ngày/năm cho nhân viên từ 3-5 năm kinh nghiệm.
- Số ngày: 18 ngày/năm cho nhân viên trên 5 năm kinh nghiệm.
- Chuyển năm sau: Tối đa 5 ngày phép năm chưa dùng được chuyển sang năm tiếp theo.

1.2 Nghỉ ốm (Sick Leave):
- Số ngày: 10 ngày/năm có trả lương.
- Yêu cầu: Thông báo cho Line Manager trước 9:00 sáng ngày nghỉ.
- Nếu nghỉ trên 3 ngày liên tiếp: Cần giấy tờ y tế từ bệnh viện.

1.3 Nghỉ thai sản:
- Nghỉ sinh con: 6 tháng theo quy định Luật Lao động.
- Nghỉ nuôi con nhỏ: 1 tiếng/ngày trong 12 tháng đầu sau sinh.

1.4 Nghỉ lễ tết:
Theo lịch nghỉ lễ quốc gia do HR công bố hàng năm vào tháng 12.

=== Phần 2: Quy trình xin nghỉ phép ===

Bước 1: Nhân viên gửi yêu cầu nghỉ phép qua hệ thống HR Portal (https://hr.company.internal) ít nhất 3 ngày làm việc trước ngày nghỉ.
Bước 2: Line Manager phê duyệt hoặc từ chối trong vòng 1 ngày làm việc.
Bước 3: Nhân viên nhận thông báo qua email sau khi được phê duyệt.

Trường hợp khẩn cấp: Có thể gửi yêu cầu muộn hơn nhưng phải được Line Manager đồng ý qua tin nhắn trực tiếp.

=== Phần 3: Chính sách làm thêm giờ ===

3.1 Điều kiện làm thêm:
Làm thêm giờ phải được Line Manager phê duyệt trước bằng văn bản.

3.2 Hệ số lương làm thêm:
- Ngày thường: 150% lương giờ tiêu chuẩn.
- Ngày cuối tuần: 200% lương giờ tiêu chuẩn.
- Ngày lễ: 300% lương giờ tiêu chuẩn.

=== Phần 4: Remote work policy ===

4.1 Điều kiện remote:
- Nhân viên sau probation period có thể làm remote tối đa 2 ngày/tuần.
- Team Lead phải phê duyệt lịch remote qua HR Portal.
- Ngày onsite bắt buộc: Thứ 3 và Thứ 5 theo lịch team.

4.2 Yêu cầu kỹ thuật khi remote:
- Kết nối VPN bắt buộc khi làm việc với hệ thống nội bộ.
- Camera bật trong các cuộc họp team.

=== Phần 5: Liên hệ HR ===
Email: hr@company.internal
Hotline: ext. 2000
HR Portal: https://hr.company.internal
Giờ làm việc: Thứ 2 - Thứ 6, 8:30 - 17:30
""",
}


def resolve_docs_dir() -> Path:
    env_path = (os.getenv("KB_DOCS_DIR") or "").strip()
    candidates = []
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(
        [
            DOCS_DIR,
            Path("/app/app/orchestrator/data/docs"),
            Path("/app/orchestrator/data/docs"),
            Path.cwd() / "app" / "orchestrator" / "data" / "docs",
            Path.cwd() / "orchestrator" / "data" / "docs",
        ]
    )

    for candidate in candidates:
        if not candidate.exists() or not candidate.is_dir():
            continue
        if any(candidate.glob("*.txt")):
            return candidate

    return DOCS_DIR


def is_using_embedded_docs() -> bool:
    docs_dir = resolve_docs_dir()
    if not docs_dir.exists() or not docs_dir.is_dir():
        return True
    return not any(docs_dir.glob("*.txt"))


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _tokenize(text: str) -> list[str]:
    tokens = [tok for tok in TOKEN_RE.findall(_normalize(text)) if len(tok) > 1]
    return [tok for tok in tokens if tok not in STOPWORDS]


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = []
    for part in text.split("\n\n"):
        cleaned = " ".join(part.strip().split())
        if len(cleaned) >= 40:
            paragraphs.append(cleaned)
    return paragraphs


@lru_cache(maxsize=1)
def load_chunks() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    docs_dir = resolve_docs_dir()
    file_docs: list[tuple[str, str]] = []

    if docs_dir.exists() and docs_dir.is_dir():
        for file_path in sorted(docs_dir.glob("*.txt")):
            raw = file_path.read_text(encoding="utf-8", errors="ignore")
            file_docs.append((file_path.name, raw))

    if not file_docs:
        file_docs = sorted(EMBEDDED_DOCS.items())

    for file_name, raw in file_docs:
        paragraphs = _split_paragraphs(raw)
        for idx, paragraph in enumerate(paragraphs):
            tokens = _tokenize(paragraph)
            if not tokens:
                continue
            chunks.append(
                {
                    "text": paragraph,
                    "source": file_name,
                    "metadata": {"chunk_index": idx + 1, "token_count": len(tokens)},
                    "tokens": tokens,
                }
            )

    return chunks


def _score(query_tokens: list[str], chunk_tokens: list[str]) -> float:
    if not query_tokens or not chunk_tokens:
        return 0.0

    query_set = set(query_tokens)
    chunk_set = set(chunk_tokens)
    overlap = query_set & chunk_set
    if not overlap:
        return 0.0

    coverage = len(overlap) / len(query_set)
    density = len(overlap) / math.sqrt(len(chunk_set))
    score = (0.8 * coverage) + (0.2 * density)
    return max(0.0, min(1.0, score))


def search_kb(query: str, top_k: int = 5, min_score: float = 0.12) -> list[dict[str, Any]]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    try:
        top_k = max(1, int(top_k))
    except (TypeError, ValueError):
        top_k = 5

    scored: list[dict[str, Any]] = []
    for chunk in load_chunks():
        score = _score(query_tokens, chunk.get("tokens", []))
        if score < min_score:
            continue
        scored.append(
            {
                "text": chunk["text"],
                "source": chunk["source"],
                "score": round(score, 4),
                "metadata": chunk["metadata"],
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]
