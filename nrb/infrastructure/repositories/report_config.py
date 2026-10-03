"""MongoDB persistence for the configurable monthly-report layout."""

from nrb.infrastructure.repositories import mongo as db
from nrb.domain import report_config

SETTING_KEY = "report_config"


class MongoReportConfigRepository:
    def get_report_config(self):
        return db.get_setting(SETTING_KEY, report_config.DEFAULT_REPORT_CONFIG)

    def save_report_config(self, cfg):
        db.set_setting(SETTING_KEY, cfg)
