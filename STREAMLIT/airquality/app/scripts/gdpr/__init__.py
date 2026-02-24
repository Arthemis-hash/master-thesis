# GDPR Package
# Conformite RGPD - Brussels Air Quality Platform

from ...gdpr_anonymizer_sync import GDPRAnonymizer

RETENTION_POLICY = {
    "audit_log_days": 365,
    "session_days": 30,
    "inactive_user_days": 730,
    "data_export_days": 30,
}

__all__ = ["GDPRAnonymizer", "RETENTION_POLICY"]
