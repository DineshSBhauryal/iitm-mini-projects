from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz


PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN = 54
INK = (0.12, 0.18, 0.23)
MUTED = (0.38, 0.45, 0.50)
TEAL = (0.02, 0.43, 0.43)
PALE_TEAL = (0.91, 0.96, 0.95)
PALE_GREY = (0.95, 0.96, 0.96)
WHITE = (1, 1, 1)

SUPPLIER_TEXT: dict[str, dict[str, Any]] = {
    "Apex Systems": {
        "tagline": "Enterprise architecture. Governed delivery. Resilient operations.",
        "executive_summary": "Apex Systems proposes a secure, enterprise-grade platform for digital procurement operations. Its response prioritizes interoperability, governance, and service resilience for high-volume processing across multiple business units.",
        "solution": "The proposed architecture uses modular services with an event-driven integration layer. Documented APIs connect procurement, identity, finance, and reporting systems. A multi-region hosting design, automated backup policy, and centralized observability support business continuity and workload growth.",
        "implementation": "The 14-week plan uses four gated phases: discovery and design (2 weeks), configuration and integration (5 weeks), migration and testing (4 weeks), and rollout with hypercare (3 weeks). Each phase ends with a readiness review and a named business-owner sign-off. Apex assigns a delivery manager, solution architect, integration lead, and migration specialist.",
        "commercial": "The proposal includes licensing, implementation services, integration work, and a 12-month managed-support package. Its premium price is comparatively clear, but environment sizing, transaction volumes, and the treatment of change requests should be confirmed before award.",
        "security": "Apex describes ISO 27001-aligned processes, centralized identity controls, encryption in transit and at rest, audit logging, and incident-response playbooks. The response identifies access-review responsibilities and privacy handling for regulated client data.",
        "support": "Apex offers 24x7 support coverage, a dedicated delivery manager, service-level objectives, monthly governance reviews, and structured knowledge transfer. References include public-sector and healthcare programs with multi-team operating models.",
        "strengths": ["Detailed integration and resilience design", "Strong security governance and support coverage"],
        "watch_items": ["Premium price position", "Confirm sizing and change-request assumptions"],
        "reference": "Illustrative references: multi-region public-sector procurement rollout; healthcare shared-services modernization.",
    },
    "BrightPath Tech": {
        "tagline": "A focused SaaS rollout with competitive commercial terms.",
        "executive_summary": "BrightPath Tech offers a low-cost, rapid-delivery solution for organizations seeking a streamlined rollout. The response emphasizes speed and ease of adoption, with a lighter level of detail around advanced enterprise customization and assurance evidence.",
        "solution": "The solution uses a SaaS-first architecture, reusable workflows, and standard API connectors. A focused configuration layer is intended to reduce deployment effort. The proposal explains core integrations but provides limited detail on high-volume architecture, complex custom workflows, and resilience testing.",
        "implementation": "BrightPath estimates a ten-week deployment. Discovery is compressed, with configuration and testing running in parallel. A project lead and configuration team are identified, while specialist availability and business-owner time commitments need confirmation. Risk management relies on milestone tracking, issue triage, and a small contingency backlog.",
        "commercial": "BrightPath presents the most competitive licensing and implementation estimate. The proposal should clarify assumptions for large transaction volumes, custom reporting, data migration, and extended support. Optional services are listed, but their likely use and rate-card impact are not fully quantified.",
        "security": "The response states standard encryption and role-based access controls. It gives less evidence for formal certifications, independent audit procedures, incident exercises, and privacy governance than the other sample proposals. These items should be treated as assurance questions, not assumed capabilities.",
        "support": "Support is provided through a standard help desk and a one-year service warranty, with limited named account ownership. The proposal references a small number of similar implementations and describes basic administrator training. Extended coverage and service-level commitments require clarification.",
        "strengths": ["Lowest stated price and short target timeline", "Simple SaaS operating model"],
        "watch_items": ["Limited formal assurance detail", "Clarify scope, specialist capacity, and support tiers"],
        "reference": "Illustrative reference: regional services organization workflow deployment; reference scope and outcomes require verification.",
    },
    "NexaWorks": {
        "tagline": "A balanced platform response with delivery discipline.",
        "executive_summary": "NexaWorks presents a balanced proposal with practical architecture, clear governance, and defined ownership across business and technical stakeholders. It combines phased delivery with operational planning and provides a reasonably transparent commercial breakdown.",
        "solution": "The solution adopts a modular platform with reusable data models and a standardized integration layer. The response describes API-based connections, reporting dashboards, automation workflows, and a phased rollout aligned to business readiness. It identifies deployment dependencies and proposes design reviews before configuration is finalized.",
        "implementation": "The 12-week plan defines discovery, design, configuration, migration, testing, and production acceptance gates. Workstreams have named roles, milestone owners, and contingency planning. Risk reviews occur after design sign-off and before production acceptance; the proposal includes business-user testing and operational handover activities.",
        "commercial": "The commercial model includes licensing, implementation effort, third-party costs, and support assumptions. Costs are moderate and supported by an effort breakdown. The buyer should validate the treatment of scope changes, volume growth, and optional optimization services against the final statement of work.",
        "security": "NexaWorks describes encryption, audit logs, access reviews, privacy controls, and policy alignment. Change-management oversight and security responsibilities are identified, though the proposal should attach evidence for any certification or independent assurance claims during due diligence.",
        "support": "A named customer-success manager coordinates training, go-live support, and post-launch optimization. References describe delivery in regulated and multi-site environments. The response proposes knowledge transfer and a transition period, with service levels to be finalized in contracting.",
        "strengths": ["Clear milestones, roles, and risk checkpoints", "Balanced commercial and operational response"],
        "watch_items": ["Validate change and volume assumptions", "Request evidence for assurance claims"],
        "reference": "Illustrative references: regulated multi-site case-management rollout; regional procurement transformation.",
    },
    "Orbit Digital": {
        "tagline": "Operational continuity backed by experienced support teams.",
        "executive_summary": "Orbit Digital emphasizes domain experience, stakeholder engagement, and support continuity. Its operating model is mature and practical, while some technical integration and certification details are described at a higher level than in the strongest technical responses.",
        "solution": "Orbit proposes a stable business-process platform with a configurable workflow engine and standard integrations. The response gives useful context on user experience, adoption, and change management. It should provide more detail on integration patterns, API limits, data ownership, and performance under peak transaction loads.",
        "implementation": "The 14-week timeline covers requirements validation, implementation, testing, and adoption readiness. Milestones align to operational rollout and training. The plan is credible, but resource loading, dependency ownership, and contingency actions are less granular than the leading delivery plan in this sample set.",
        "commercial": "The subscription model and support tiers are described with reasonable clarity. Pricing is competitive and assumptions are stated, although the proposal gives less detail on total lifecycle cost, migration effort, and the cost of expanding integrations or support coverage.",
        "security": "Orbit outlines data-handling procedures, secure access controls, and audit-friendly operations. Compliance coverage is positive, but the response should provide specific certification scope, control evidence, incident-response timelines, and privacy-role responsibilities during due diligence.",
        "support": "Support is a strong part of Orbit's response, with experienced delivery staff, customer references, managed-service governance, and knowledge transfer. The customer-success framework supports continuity, while final service levels and escalation response targets should be confirmed contractually.",
        "strengths": ["Experienced support and customer-success approach", "Practical adoption and governance model"],
        "watch_items": ["Add technical integration and performance detail", "Confirm lifecycle cost and assurance evidence"],
        "reference": "Illustrative references: enterprise workflow adoption program; managed-service transition for a multi-site client.",
    },
}


def _new_page(doc: fitz.Document, supplier: str, page_number: int, section: str) -> fitz.Page:
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.draw_rect(page.rect, color=WHITE, fill=WHITE)
    page.draw_rect(fitz.Rect(0, 0, PAGE_WIDTH, 11), color=TEAL, fill=TEAL)
    page.insert_text((MARGIN, 38), supplier, fontsize=9, fontname="helv", color=MUTED)
    page.insert_text((PAGE_WIDTH - MARGIN - 104, 38), section.upper(), fontsize=8, fontname="hebo", color=TEAL)
    page.draw_line((MARGIN, 51), (PAGE_WIDTH - MARGIN, 51), color=(0.82, 0.86, 0.87), width=0.7)
    page.draw_line((MARGIN, PAGE_HEIGHT - 47), (PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 47), color=(0.82, 0.86, 0.87), width=0.7)
    page.insert_text((MARGIN, PAGE_HEIGHT - 29), "ILLUSTRATIVE PROCUREMENT RESPONSE  |  CONFIDENTIAL", fontsize=7, fontname="helv", color=MUTED)
    page.insert_text((PAGE_WIDTH - MARGIN - 25, PAGE_HEIGHT - 29), f"{page_number:02d}", fontsize=8, fontname="hebo", color=TEAL)
    return page


def _insert_wrapped(page: fitz.Page, text: str, rect: fitz.Rect, *, size: float = 10.5, color: tuple[float, float, float] = INK, font: str = "helv", line_height: float = 1.35) -> float:
    remaining = page.insert_textbox(
        rect,
        text,
        fontsize=size,
        fontname=font,
        color=color,
        lineheight=line_height,
        align=fitz.TEXT_ALIGN_LEFT,
    )
    if remaining < 0:
        raise ValueError(f"Text overflowed the planned PDF layout: {text[:80]}")
    return rect.y0 + (rect.height - remaining)


def _section_block(page: fitz.Page, title: str, body: str, y: float, *, height: float = 190, eyebrow: str = "PROPOSAL RESPONSE") -> float:
    rect = fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, y + height)
    page.draw_rect(rect, color=(0.86, 0.89, 0.89), fill=WHITE, width=0.8)
    page.draw_rect(fitz.Rect(rect.x0, rect.y0, rect.x0 + 5, rect.y1), color=TEAL, fill=TEAL)
    page.insert_text((rect.x0 + 19, rect.y0 + 25), eyebrow, fontsize=7.5, fontname="hebo", color=TEAL)
    page.insert_text((rect.x0 + 19, rect.y0 + 48), title, fontsize=15, fontname="hebo", color=INK)
    _insert_wrapped(
        page,
        body,
        fitz.Rect(rect.x0 + 19, rect.y0 + 62, rect.x1 - 18, rect.y1 - 15),
        size=10,
        line_height=1.4,
    )
    return rect.y1


def _bullet_list(page: fitz.Page, items: list[str], rect: fitz.Rect, *, size: float = 9.2) -> None:
    y = rect.y0
    for item in items:
        page.draw_circle((rect.x0 + 4, y + 6), radius=2.2, color=TEAL, fill=TEAL)
        end_y = _insert_wrapped(
            page,
            item,
            fitz.Rect(rect.x0 + 14, y, rect.x1, min(y + 38, rect.y1)),
            size=size,
            line_height=1.25,
        )
        y = end_y + 8


def _cover_page(doc: fitz.Document, supplier: str, data: dict[str, Any]) -> None:
    page = _new_page(doc, supplier, 1, "Executive summary")
    page.draw_rect(fitz.Rect(0, 52, PAGE_WIDTH, 360), color=PALE_TEAL, fill=PALE_TEAL)
    page.insert_text((MARGIN, 112), "REQUEST FOR PROPOSAL", fontsize=9, fontname="hebo", color=TEAL)
    page.insert_textbox(
        fitz.Rect(MARGIN, 139, PAGE_WIDTH - MARGIN, 217),
        "Digital Procurement\nOperations Platform",
        fontsize=28,
        fontname="hebo",
        color=INK,
        lineheight=1.08,
    )
    _insert_wrapped(page, data["tagline"], fitz.Rect(MARGIN, 236, PAGE_WIDTH - MARGIN, 280), size=12, color=MUTED, line_height=1.3)
    page.draw_line((MARGIN, 309), (PAGE_WIDTH - MARGIN, 309), color=(0.71, 0.82, 0.81), width=1)
    page.insert_text((MARGIN, 337), f"SUBMITTED BY  {supplier.upper()}", fontsize=8.5, fontname="hebo", color=INK)

    page.insert_text((MARGIN, 402), "01  |  EXECUTIVE SUMMARY", fontsize=8, fontname="hebo", color=TEAL)
    page.insert_text((MARGIN, 429), "Proposal at a glance", fontsize=19, fontname="hebo", color=INK)
    _insert_wrapped(page, data["executive_summary"], fitz.Rect(MARGIN, 448, PAGE_WIDTH - MARGIN, 550), size=10.5, line_height=1.45)

    page.draw_rect(fitz.Rect(MARGIN, 578, PAGE_WIDTH - MARGIN, 770), color=PALE_GREY, fill=PALE_GREY)
    page.insert_text((MARGIN + 18, 606), "DIFFERENTIATORS", fontsize=8, fontname="hebo", color=TEAL)
    _bullet_list(page, data["strengths"], fitz.Rect(MARGIN + 18, 622, PAGE_WIDTH - MARGIN - 18, 690))
    page.insert_text((MARGIN + 18, 711), "POINTS TO CONFIRM", fontsize=8, fontname="hebo", color=TEAL)
    _bullet_list(page, data["watch_items"], fitz.Rect(MARGIN + 18, 727, PAGE_WIDTH - MARGIN - 18, 763), size=8.5)


def _solution_page(doc: fitz.Document, supplier: str, data: dict[str, Any]) -> None:
    page = _new_page(doc, supplier, 2, "Technical and delivery")
    page.insert_text((MARGIN, 94), "02  |  TECHNICAL RESPONSE", fontsize=8, fontname="hebo", color=TEAL)
    page.insert_text((MARGIN, 124), "Solution and delivery approach", fontsize=20, fontname="hebo", color=INK)
    page.insert_text((MARGIN, 151), "Architecture, dependencies, people, and implementation controls", fontsize=9, fontname="helv", color=MUTED)
    _section_block(page, "Proposed solution", data["solution"], 180, height=255, eyebrow="ARCHITECTURE AND INTEGRATION")
    _section_block(page, "Implementation plan and team", data["implementation"], 453, height=305, eyebrow="PHASES, MILESTONES, AND OWNERSHIP")


def _assurance_page(doc: fitz.Document, supplier: str, data: dict[str, Any]) -> None:
    page = _new_page(doc, supplier, 3, "Commercial and assurance")
    page.insert_text((MARGIN, 94), "03  |  COMMERCIAL AND ASSURANCE", fontsize=8, fontname="hebo", color=TEAL)
    page.insert_text((MARGIN, 124), "Commercials and security", fontsize=20, fontname="hebo", color=INK)
    page.insert_text((MARGIN, 151), "Pricing assumptions and assurance evidence for due diligence", fontsize=9, fontname="helv", color=MUTED)
    _section_block(page, "Commercial approach", data["commercial"], 180, height=255, eyebrow="PRICE, SCOPE, AND ASSUMPTIONS")
    _section_block(page, "Security and compliance", data["security"], 453, height=305, eyebrow="CONTROLS, PRIVACY, AND AUDITABILITY")


def _operations_page(doc: fitz.Document, supplier: str, data: dict[str, Any]) -> None:
    page = _new_page(doc, supplier, 4, "Support and references")
    page.insert_text((MARGIN, 94), "04  |  OPERATING MODEL", fontsize=8, fontname="hebo", color=TEAL)
    page.insert_text((MARGIN, 124), "Support and experience", fontsize=20, fontname="hebo", color=INK)
    page.insert_text((MARGIN, 151), "Service coverage, transition, knowledge transfer, and references", fontsize=9, fontname="helv", color=MUTED)
    _section_block(page, "Support model and transition", data["support"], 180, height=260, eyebrow="SERVICE, ESCALATION, AND HANDOVER")
    page.draw_rect(fitz.Rect(MARGIN, 462, PAGE_WIDTH - MARGIN, 660), color=PALE_TEAL, fill=PALE_TEAL)
    page.insert_text((MARGIN + 18, 491), "ILLUSTRATIVE REFERENCE PROFILE", fontsize=8, fontname="hebo", color=TEAL)
    _insert_wrapped(page, data["reference"], fitz.Rect(MARGIN + 18, 510, PAGE_WIDTH - MARGIN - 18, 628), size=10, line_height=1.4)
    page.insert_text((MARGIN, 710), "Evaluation note", fontsize=10, fontname="hebo", color=INK)
    _insert_wrapped(
        page,
        "This synthetic proposal is provided for demonstration and testing. Supplier claims and references are illustrative and must not be treated as verified procurement evidence.",
        fitz.Rect(MARGIN, 728, PAGE_WIDTH - MARGIN, 779),
        size=8.5,
        color=MUTED,
        line_height=1.3,
    )


def generate_sample_pdfs(output_dir: str | Path) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    for supplier, data in SUPPLIER_TEXT.items():
        doc = fitz.open()
        doc.set_metadata({
            "title": f"Digital Procurement Platform Proposal - {supplier}",
            "author": supplier,
            "subject": "Synthetic supplier proposal for RFP evaluation testing",
            "keywords": "RFP, procurement, platform, synthetic sample",
            "creator": "Agentic RFP Evaluation sample generator",
        })
        _cover_page(doc, supplier, data)
        _solution_page(doc, supplier, data)
        _assurance_page(doc, supplier, data)
        _operations_page(doc, supplier, data)

        safe_name = supplier.replace(" ", "_").lower()
        file_path = output_path / f"{safe_name}_proposal.pdf"
        doc.save(file_path, garbage=4, deflate=True)
        doc.close()
        generated.append(file_path)

    return generated


if __name__ == "__main__":
    files = generate_sample_pdfs(Path(__file__).resolve().parents[1] / "uploads")
    print(f"Generated {len(files)} sample PDFs in {files[0].parent}")
