from .reliefweb import ReliefWebAdapter
from .unjobs import UNJobsAdapter
from .devex import DevexAdapter
from .impactpool import ImpactpoolAdapter
from .idealist import IdealistAdapter
from .unicef import UnicefAdapter
from .idb import IDBAdapter
from .un_inspira import UNInspiraAdapter
from .worldbank import WorldBankAdapter
from .ilo import ILOAdapter
from .unesco import UNESCOAdapter
from .fao import FAOAdapter
from .iom import IOMAdapter
from .caf import CAFAdapter
from .emb_uk import EmbassyUKAdapter
from .emb_canada import EmbassyCanadaAdapter
from .emb_usa import EmbassyUSAAdapter
from .change_detector import ChangePageAdapter

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
    ILOAdapter(),
    UNESCOAdapter(),
    FAOAdapter(),
    # IOMAdapter — disabled: all known recruit.iom.int / iom.int endpoints
    # return 403 (Akamai block) or "wrong url". Re-enable once a working
    # public endpoint is found.
    # CAFAdapter — disabled: caf.com returns a 103-byte Cloudflare challenge
    # from both httpx and Playwright. Needs a proxy or different endpoint.
    # Tier 3 — embassies (structured job boards)
    EmbassyUKAdapter(),
    EmbassyCanadaAdapter(),
    EmbassyUSAAdapter(),
    # Tier 3 — change detection (static embassy/news pages)
    ChangePageAdapter(),
]
