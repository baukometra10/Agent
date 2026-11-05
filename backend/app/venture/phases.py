"""Venture phase catalog and gate policy."""

from __future__ import annotations

from app.db.models import VenturePhaseName

PHASE_ORDER: list[VenturePhaseName] = [
    VenturePhaseName.understand,
    VenturePhaseName.capabilities,
    VenturePhaseName.architecture,
    VenturePhaseName.prototype,
    VenturePhaseName.simulate,
    VenturePhaseName.implement,
    VenturePhaseName.monitor,
]

PHASE_LABELS_AR: dict[str, str] = {
    VenturePhaseName.understand.value: "فهم النشاط والأهداف",
    VenturePhaseName.capabilities.value: "استنباط الوظائف",
    VenturePhaseName.architecture.value: "تصميم المعمارية",
    VenturePhaseName.prototype.value: "نموذج أولي",
    VenturePhaseName.simulate.value: "محاكاة العمليات",
    VenturePhaseName.implement.value: "تنفيذ واختبار",
    VenturePhaseName.monitor.value: "متابعة واقتراح تطوير",
}

# Human gate before leaving these phases (approve to advance)
PHASE_REQUIRES_APPROVAL: dict[str, bool] = {
    VenturePhaseName.understand.value: False,
    VenturePhaseName.capabilities.value: False,
    VenturePhaseName.architecture.value: True,
    VenturePhaseName.prototype.value: True,
    VenturePhaseName.simulate.value: True,
    VenturePhaseName.implement.value: True,
    VenturePhaseName.monitor.value: False,
}
