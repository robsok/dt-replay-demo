from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime

@dataclass
class OrderState:
    order_id: str
    status: str = "Unknown"
    timestamps: Dict[str, datetime] = field(default_factory=dict)
    sla_hours: float = 8.0   # example SLA: 8 hours from Created -> Delivered

    def update(self, event: str, ts: datetime):
        self.status = event
        self.timestamps[event] = ts

    def lead_time_minutes(self) -> Optional[float]:
        if "Created" in self.timestamps and "Delivered" in self.timestamps:
            delta = self.timestamps["Delivered"] - self.timestamps["Created"]
            return delta.total_seconds() / 60.0
        return None

    def sla_breached(self) -> Optional[bool]:
        lt = self.lead_time_minutes()
        if lt is None:
            return None
        return lt > self.sla_hours * 60.0
