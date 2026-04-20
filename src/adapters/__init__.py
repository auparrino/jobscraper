from .reliefweb import ReliefWebAdapter
from .unjobs import UNJobsAdapter
from .devex import DevexAdapter
from .impactpool import ImpactpoolAdapter
from .idealist import IdealistAdapter
from .unicef import UnicefAdapter
from .idb import IDBAdapter
from .un_inspira import UNInspiraAdapter
from .worldbank import WorldBankAdapter

ALL_ADAPTERS = [
    # Tier 1 — consolidators
    ReliefWebAdapter(),
    UNJobsAdapter(),
    DevexAdapter(),
    ImpactpoolAdapter(),
    IdealistAdapter(),
    # Tier 2 — dedicated ATS
    UnicefAdapter(),
    IDBAdapter(),
    UNInspiraAdapter(),
    WorldBankAdapter(),
]
