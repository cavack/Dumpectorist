from app.core.config import settings
from app.db.session import Database
from app.overview.database_provider import DatabaseOverviewProvider
from app.overview.summary_provider import OverviewSummaryProvider


database = Database(settings.database_url)
provider = DatabaseOverviewProvider(database.session_factory)


def get_overview_provider() -> OverviewSummaryProvider:
    return provider
