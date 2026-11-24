# -*- coding: utf-8 -*-
"""Import every instrument module so that the @register_instrument
decorators on each Instrument subclass run at package import time.
"""

from senaite.astm.instruments import abbott_afinion2    # noqa: F401
from senaite.astm.instruments import biomerieux_mini_vidas  # noqa: F401
from senaite.astm.instruments import dca_vantage    # noqa: F401
from senaite.astm.instruments import genexpert    # noqa: F401
from senaite.astm.instruments import hitachi_7600  # noqa: F401
from senaite.astm.instruments import horiba_pentra_xlr    # noqa: F401
from senaite.astm.instruments import horiba_yumizen_h5xx    # noqa: F401
from senaite.astm.instruments import roche_cobas_c111    # noqa: F401
from senaite.astm.instruments import roche_cobas_c311    # noqa: F401
from senaite.astm.instruments import spotchem_el    # noqa: F401
from senaite.astm.instruments import sysmex_xn    # noqa: F401
from senaite.astm.instruments import sysmex_xp    # noqa: F401
