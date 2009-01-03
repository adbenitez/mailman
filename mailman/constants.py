# Copyright (C) 2006-2009 by the Free Software Foundation, Inc.
#
# This file is part of GNU Mailman.
#
# GNU Mailman is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# GNU Mailman is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# GNU Mailman.  If not, see <http://www.gnu.org/licenses/>.

"""Various constants and enumerations."""

__all__ = [
    'SystemDefaultPreferences',
    ]


from mailman.interfaces import DeliveryMode, DeliveryStatus, IPreferences
from zope.interface import implements



class SystemDefaultPreferences(object):
    implements(IPreferences)

    acknowledge_posts = False
    hide_address = True
    preferred_language = 'en'
    receive_list_copy = True
    receive_own_postings = True
    delivery_mode = DeliveryMode.regular
    delivery_status = DeliveryStatus.enabled