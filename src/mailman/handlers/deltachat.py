"""Optimizations for usage with DeltaChat clients"""

from mailman.core.i18n import _
from mailman.interfaces.handler import IHandler
from public import public
from zope.interface import implementer


@public
@implementer(IHandler)
class DeltaChatHandler:
    """Optimization for usage with Delta Chat clients."""

    name = "deltachat"
    description = _("Optimization for usage with Delta Chat clients.")

    def process(self, mlist, msg, msgdata):
        """See `IHandler`."""
        del msg["Subject"]  # TODO: remove when DC is fixed to hide subject
