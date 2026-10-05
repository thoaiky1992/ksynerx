from sqlalchemy import Column, String, DateTime, JSON, func
from app.core.database import Base

class WorkerConfig(Base):
    """Central worker_configs table for worker status and configuration."""
    __tablename__ = "worker_configs"

    id = Column(String(100), primary_key=True, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)
    source_type = Column(String(20), nullable=False) # 'SHOPIFY' or 'VIETFUL'
    status = Column(String(20), nullable=False, default="STOPPED") # 'RUNNING', 'STOPPED', 'FAILED'
    schedule_cron = Column(String(50), nullable=True) # Example: '*/1 * * * *' (for Shopify)
    config_json = Column(JSON, nullable=True, default={})
    checkpoint_data = Column(JSON, nullable=True, default={})
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "source_type": self.source_type,
            "status": self.status,
            "schedule_cron": self.schedule_cron,
            "config_json": self.config_json,
            "checkpoint_data": self.checkpoint_data,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
