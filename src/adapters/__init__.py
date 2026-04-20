from .reliefweb import ReliefWebAdapter
from .unjobs import UNJobsAdapter
from .devex import DevexAdapter
from .impactpool import ImpactpoolAdapter
from .idealist import IdealistAdapter

ALL_ADAPTERS = [
    ReliefWebAdapter(),
    UNJobsAdapter(),
    DevexAdapter(),
    ImpactpoolAdapter(),
    IdealistAdapter(),
]
