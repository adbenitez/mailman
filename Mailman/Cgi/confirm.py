# Copyright (C) 2001 by the Free Software Foundation, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software 
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

"""Confirm a pending action via URL."""

from Mailman import mm_cfg
from Mailman import Errors
from Mailman import i18n
from Mailman import MailList
from Mailman import Pending
from Mailman.htmlformat import *
from Mailman.Logging.Syslog import syslog

# Set up i18n
_ = i18n._
i18n.set_language(mm_cfg.DEFAULT_SERVER_LANGUAGE)



def main():
    doc = Document()
    doc.set_language(mm_cfg.DEFAULT_SERVER_LANGUAGE)

    parts = Utils.GetPathPieces()
    if not parts:
        bad_confirmation(doc)
        doc.AddItem(MailmanLogo())
        print doc.Format(bgcolor='#ffffff')
        return

    listname = parts[0].lower()
    try:
        mlist = MailList.MailList(listname, lock=0)
    except Errors.MMListError, e:
        bad_confirmation(doc, _('No such list <em>%(listname)s</em>'))
        doc.AddItem(MailmanLogo())
        print doc.Format(bgcolor='#ffffff')
        syslog('error', 'No such list "%s": %s' % (listname, e))
        return

    # Set the language for the list
    i18n.set_language(mlist.preferred_language)
    doc.set_language(mlist.preferred_language)

    # Now dig out the cookie
    mlist.Lock()
    try:
        try:
            cookie = parts[1]
            data = mlist.ProcessConfirmation(cookie)
            success(mlist, doc, *data)
        except (Errors.MMBadConfirmation, IndexError):
            days = int(mm_cfg.PENDING_REQUEST_LIFE / mm_cfg.days(1) + 0.5)
            bad_confirmation(doc, _('''Invalid confirmation string.  Note that
            confirmation strings expire approximately %(days)s days after the
            initial subscription request.  If your confirmation has expired,
            please try to re-submit your subscription.'''))
        doc.AddItem(mlist.GetMailmanFooter())
        print doc.Format(bgcolor='#ffffff')
    finally:
        mlist.Save()
        mlist.Unlock()



def bad_confirmation(doc, extra=''):
    title = _('Bad confirmation string')
    doc.SetTitle(title)
    doc.AddItem(Header(3, Bold(FontAttr(title, color='#ff0000', size='+2'))))
    doc.AddItem(extra)



def success(mlist, doc, op, data):
    listname = mlist.real_name
    # Different title based on operation performed
    if op == Pending.SUBSCRIPTION:
        title = _('Subscription request confirmed')
        addr, password, digest, lang = data
    # Current only one other operation
    else:
        title = _('Removal request confirmed')
        addr = data
        lang = mlist.GetPreferredLanguage(addr)
    # Use the user's preferred language
    i18n.set_language(lang)
    doc.set_language(lang)
    # Now set the title and report the results
    doc.SetTitle(title)
    doc.AddItem(Header(3, Bold(FontAttr(title, size='+2'))))
    if op == Pending.SUBSCRIPTION:
        doc.AddItem(_('''\
        You have successfully confirmed your subscription request for
        "%(addr)s" to the %(listname)s mailing list.  A separate confirmation
        message will be sent to your email address, along with your password,
        and other useful information and links.'''))
    else:
        doc.AddItem(_('''\
        You have successfully confirmed your removal request for "%(addr)s" to
        the %(listname)s mailing list.'''))
