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

"""Creation/deletion hooks for the Postfix MTA.

Note: only hash: type maps are currently supported.
"""

import os
import socket
import time
import errno
import pwd
import fcntl
from stat import *

# Python's BerkeleyDB support is simply broken, IMO.  The best advice I can
# give is that if you are having problems, download and install PyBSDDB3, from
# pybsddb.sf.net, install it, and use it by (possibly) editing the following
# lines.
try:
    import bsddb
except ImportError:
    import bsddb3 as bsddb

from Mailman import mm_cfg
from Mailman import Utils
from Mailman import LockFile
from Mailman.i18n import _
from Mailman.MTA.Utils import makealiases

LOCKFILE = os.path.join(mm_cfg.LOCK_DIR, 'creator')

TEXTFILE = os.path.join(mm_cfg.DATA_DIR, 'aliases')
DBFILE = TEXTFILE + '.db'

VTEXTFILE = os.path.join(mm_cfg.DATA_DIR, 'virtual-mailman')
VDBFILE = VTEXTFILE + '.db'



# Here's the deal with locking.  In order to assure that Postfix doesn't read
# the file while we're writing updates, we should drop an exclusive advisory
# lock on the file.  Ideally, we'd specify the `l' flag to bsddb.hashopen()
# which translates to passing the O_EXLOCK flag to the underlying open call,
# for systems that support O_EXLOCK.
#
# Unfortunately, Linux is one of those systems that don't support O_EXLOCK.
# To make matters worse, the default bsddb module in Python gives us no access
# to the file descriptor of the database file, so we cannot hashopen(), dig
# out the fd, then use fcntl.flock() to acquire the lock.  Bummer. :(
#
# Another approach would be to do a file dance to assure exclusivity.
# I.e. when we add or remove list entries, we actually create a new .tmp file,
# write all the entries to that file, and then rename() that file to
# aliases.db.  The problem with /that/ approach though is that we can't get
# the file ownership right on the tmp file. That's because the process adding
# or removing entries may be Joe Shmoe who's a member of the `mailman' group,
# or it may be a cgi process run as `nobody' or `apache'.  Or eventually, it
# may be run via a mail program or any number of other processes.  Without a
# setuid program we simply can't assure that the ownership of the tmp file
# will be the same as the ownership of the original file, and /that/ we must
# absolutely guarantee.  Postfix runs mail programs under the uid of the owner
# of the aliases.db file.
#
# The best solution I can come up with involves opening the aliases.db file
# with bsddb.hashopen() first, then do a built-in open(), digout the fd from
# the file object and flock() it.  We have to open with bsddb.hashopen() first
# in case the file doesn't exist yet, but we can't write to it until we get
# the lock.  Blech.  If anybody has a better, portable, solution, I'm all
# ears.

def makelock():
    return LockFile.LockFile(LOCKFILE)


def _zapfile(filename):
    # Truncate the file w/o messing with the file permissions, but only if it
    # already exists.
    if os.path.exists(filename):
        fp = open(filename, 'w')
        fp.close()


def _zapdb(filename):
    if os.path.exists(filename):
        db = bsddb.hashopen(filename, 'c')
        for k in db.keys():
            del db[k]
        db.close()


def clear():
    _zapfile(TEXTFILE)
    _zapfile(VTEXTFILE)
    _zapdb(DBFILE)
    _zapdb(VDBFILE)



def addlist(mlist, db, fp):
    # Set up the mailman-loop address
    loopaddr = Utils.ParseEmail(Utils.get_site_email(extra='loop'))[0]
    loopmbox = os.path.join(mm_cfg.DATA_DIR, 'owner-bounces.mbox')
    # Seek to the end of the text file, but if it's empty write the standard
    # disclaimer, and the loop catch address.
    fp.seek(0, 2)
    if not fp.tell():
        print >> fp, """\
# This file is generated by Mailman, and is kept in sync with the
# binary hash file aliases.db.  YOU SHOULD NOT MANUALLY EDIT THIS FILE
# unless you know what you're doing, and can keep the two files properly
# in sync.  If you screw it up, you're on your own.
"""
        print >> fp, '# The ultimate loop stopper address'
        print >> fp, '%s: %s' % (loopaddr, loopmbox)
        print >> fp
    # Always update YP_LAST_MODIFIED
    db['YP_LAST_MODIFIED'] = '%010d' % time.time()
    # Add a YP_MASTER_NAME only if there isn't one already
    if not db.has_key('YP_MASTER_NAME'):
        db['YP_MASTER_NAME'] = socket.getfqdn()
    # Bootstrapping.  bin/genaliases must be run before any lists are created,
    # but if no lists exist yet then mlist is None.  The whole point of the
    # exercise is to get the minimal aliases.db file into existance.
    if mlist is None:
        return
    listname = mlist.internal_name()
    fieldsz = len(listname) + len('-request')
    # The text file entries get a little extra info
    print >> fp, '# STANZA START:', listname
    print >> fp, '# CREATED:', time.ctime(time.time())
    # Add the loop stopper address
    db[loopaddr + '\0'] = loopmbox + '\0'
    # Now add all the standard alias entries
    for k, v in makealiases(listname):
        # Every key and value in the dbhash file as created by Postfix
        # must end in a null byte.  That is, except YP_LAST_MODIFIED and
        # YP_MASTER_NAME.
        db[k + '\0'] = v + '\0'
        # Format the text file nicely
        print >> fp, k + ':', ((fieldsz - len(k) + 1) * ' '), v
    # Finish the text file stanza
    print >> fp, '# STANZA END:', listname
    print >> fp



def addvirtual(mlist, db, fp):
    listname = mlist.internal_name()
    fieldsz = len(listname) + len('request')
    hostname = mlist.host_name
    # Set up the mailman-loop address
    loopaddr = Utils.get_site_email(mlist.host_name, extra='loop')
    loopdest = Utils.ParseEmail(loopaddr)[0]
    # Seek to the end of the text file, but if it's empty write the standard
    # disclaimer, and the loop catch address.
    fp.seek(0, 2)
    if not fp.tell():
        print >> fp, """\
# This file is generated by Mailman, and is kept in sync with the binary hash
# file virtual-mailman.db.  YOU SHOULD NOT MANUALLY EDIT THIS FILE unless you
# know what you're doing, and can keep the two files properly in sync.  If you
# screw it up, you're on your own.
#
# Note that you should already have this virtual domain set up properly in
# your Postfix installation.  See README.POSTFIX for details.

# LOOP ADDRESSES START
%s\t%s
# LOOP ADDRESSES END
""" % (loopaddr, loopdest)
        # Add the loop address entry to the db file
        db[loopaddr + '\0'] = loopdest + '\0'
    # The text file entries get a little extra info
    print >> fp, '# STANZA START:', listname
    print >> fp, '# CREATED:', time.ctime(time.time())
    # Now add all the standard alias entries
    for k, v in makealiases(listname):
        fqdnaddr = '%s@%s' % (k, hostname)
        # Every key and value in the dbhash file as created by Postfix
        # must end in a null byte.  That is, except YP_LAST_MODIFIED and
        # YP_MASTER_NAME.
        db[fqdnaddr + '\0'] = k + '\0'
        # Format the text file nicely
        print >> fp, fqdnaddr, ((fieldsz - len(k) + 1) * ' '), '\t', k
    # Finish the text file stanza
    print >> fp, '# STANZA END:', listname
    print >> fp



# Blech.
def check_for_virtual_loopaddr(mlist, db, filename):
    loopaddr = Utils.get_site_email(mlist.host_name, extra='loop')
    loopdest = Utils.ParseEmail(loopaddr)[0]
    # If the loop address is already in the database, we don't need to add it
    # to the plain text file, but if it isn't, then we do!
    if db.has_key(loopaddr + '\0'):
        # It's already there
        return
    infp = open(filename)
    omask = os.umask(007)
    try:
        outfp = open(filename + '.tmp', 'w')
    finally:
        os.umask(omask)
    try:
        while 1:
            line = infp.readline()
            if not line:
                break
            outfp.write(line)
            if line.startswith('# LOOP ADDRESSES START'):
                print >> outfp, '%s\t%s' % (loopaddr, loopdest)
                break
        outfp.writelines(infp.readlines())
    finally:
        infp.close()
        outfp.close()
    os.rename(filename + '.tmp', filename)
    db[loopaddr + '\0'] = loopdest + '\0'



def do_create(mlist, dbfile, textfile, func):
    lockfp = None
    try:
        # First, open the dbhash file using built-in open so we can acquire an
        # exclusive lock on it.  See the discussion above for why we do it
        # this way instead of specifying the `l' option to dbhash.open()
        db = bsddb.hashopen(dbfile, 'c')
        lockfp = open(dbfile)
        fcntl.flock(lockfp.fileno(), fcntl.LOCK_EX)
        # Crack open the plain text file
        try:
            fp = open(textfile, 'r+')
        except IOError, e:
            if e.errno <> errno.ENOENT: raise
            omask = os.umask(007)
            try:
                fp = open(textfile, 'w+')
            finally:
                os.umask(omask)
        func(mlist, db, fp)
        # And flush everything out to disk
        fp.close()
        # Now double check the virtual plain text file
        if func is addvirtual:
            check_for_virtual_loopaddr(mlist, db, textfile)
        db.sync()
        db.close()
    finally:
        if lockfp:
            fcntl.flock(lockfp.fileno(), fcntl.LOCK_UN)
            lockfp.close()
    

def create(mlist, cgi=0, nolock=0):
    # Acquire the global list database lock
    lock = None
    if not nolock:
        lock = makelock()
        lock.lock()
    # Do the aliases file, which need to be done in any case
    try:
        do_create(mlist, DBFILE, TEXTFILE, addlist)
        if mlist and mlist.host_name in mm_cfg.POSTFIX_STYLE_VIRTUAL_DOMAINS:
            do_create(mlist, VDBFILE, VTEXTFILE, addvirtual)
    finally:
        if lock:
            lock.unlock(unconditionally=1)



def do_remove(mlist, dbfile, textfile, virtualp):
    lockfp = None
    try:
        listname = mlist.internal_name()
        # Crack open the dbhash file, and delete all the entries.  See the
        # discussion above for while we lock the aliases.db file this way.
        lockfp = open(dbfile)
        fcntl.flock(lockfp.fileno(), fcntl.LOCK_EX)
        db = bsddb.hashopen(dbfile, 'c')
        for k, v in makealiases(listname):
            try:
                del db[k + '\0']
            except KeyError:
                pass
        if not virtualp:
            # Always update YP_LAST_MODIFIED, but only for the aliases file
            db['YP_LAST_MODIFIED'] = '%010d' % time.time()
            # Add a YP_MASTER_NAME only if there isn't one already
            if not db.has_key('YP_MASTER_NAME'):
                db['YP_MASTER_NAME'] = socket.getfqdn()
        # And flush the changes to disk
        db.sync()
        # Now do our best to filter out the proper stanza from the text file.
        # The text file better exist!
        try:
            infp = open(textfile)
        except IOError, e:
            if e.errno <> errno.ENOENT: raise
            # Otherwise, there's no text file to filter so we're done.
            return
        omask = os.umask(007)
        try:
            outfp = open(textfile + '.tmp', 'w')
        finally:
            os.umask(omask)
        filteroutp = 0
        start = '# STANZA START: ' + listname
        end = '# STANZA END: ' + listname
        while 1:
            line = infp.readline()
            if not line:
                break
            # If we're filtering out a stanza, just look for the end marker
            # and filter out everything in between.  If we're not in the
            # middle of filter out a stanza, we're just looking for the proper
            # begin marker.
            if filteroutp:
                if line.startswith(end):
                    filteroutp = 0
                    # Discard the trailing blank line, but don't worry if
                    # we're at the end of the file.
                    infp.readline()
                # Otherwise, ignore the line
            else:
                if line.startswith(start):
                    # Filter out this stanza
                    filteroutp = 1
                else:
                    outfp.write(line)
        # Close up shop, and rotate the files
        infp.close()
        outfp.close()
        os.rename(textfile+'.tmp', textfile)
    finally:
        if lockfp:
            fcntl.flock(lockfp.fileno(), fcntl.LOCK_UN)
            lockfp.close()
    

def remove(mlist, cgi=0):
    # Acquire the global list database lock
    lock = makelock()
    lock.lock()
    try:
        do_remove(mlist, DBFILE, TEXTFILE, 0)
        if mlist.host_name in mm_cfg.POSTFIX_STYLE_VIRTUAL_DOMAINS:
            do_remove(mlist, VDBFILE, VTEXTFILE, 1)
    finally:
        lock.unlock(unconditionally=1)



def checkperms(state):
    targetmode = S_IFREG | S_IRUSR | S_IWUSR | S_IRGRP | S_IWGRP
    if state.VERBOSE:
        print _('checking permissions on %(DBFILE)s')
    try:
        stat = os.stat(DBFILE)
    except OSError, e:
        if e.errno <> errno.ENOENT: raise
        return
    if (stat[ST_MODE] & targetmode) <> targetmode:
        state.ERRORS += 1
        octmode = oct(stat[ST_MODE])
        print _('%(DBFILE)s permissions must be 066x (got %(octmode)s)'),
        if state.FIX:
            print _('(fixing)')
            os.chmod(DBFILE, stat[ST_MODE] | targetmode)
        else:
            print
    # Make sure the aliases.db is owned by root.  We don't need to check the
    # group ownership of the file, since check_perms checks this itself.
    if state.VERBOSE:
        print _('checking ownership of %(DBFILE)s')
    rootuid = pwd.getpwnam('mailman')[2]
    ownerok = stat[ST_UID] == rootuid
    if not ownerok:
        try:
            owner = pwd.getpwuid(stat[ST_UID])[0]
        except KeyError:
            owner = 'uid %d' % stat[ST_UID]
        print _('%(DBFILE)s owned by %(owner)s (must be owned by mailman)')
        state.ERRORS += 1
        if state.FIX:
            print _('(fixing)')
            os.chown(DBFILE, rootuid, mm_cfg.MAILMAN_GID)
        else:
            print
