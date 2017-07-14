# Copyright (C) 2011-2017 by the Free Software Foundation, Inc.
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

"""Test the outgoing runner."""

import tempfile
import unittest
import mailman.handlers.arc_sign

from mailman.app.lifecycle import create_list
from mailman.config import config
from mailman.handlers.arc_sign import ArcSign
from mailman.testing.helpers import (
    specialized_message_from_string as message_from_string)
from mailman.testing.layers import ConfigLayer
# tox -e py36-nocov mailman.handlers.tests.test_arc_sign


class TestArcSignMessage(unittest.TestCase):
    """Test Authentication-Results generation."""
    layer = ConfigLayer

    def setUp(self):
        privkey = b"""-----BEGIN RSA PRIVATE KEY-----
MIICXQIBAAKBgQDkHlOQoBTzWRiGs5V6NpP3idY6Wk08a5qhdR6wy5bdOKb2jLQi
Y/J16JYi0Qvx/byYzCNb3W91y3FutACDfzwQ/BC/e/8uBsCR+yz1Lxj+PL6lHvqM
KrM3rG4hstT5QjvHO9PzoxZyVYLzBfO2EeC3Ip3G+2kryOTIKT+l/K4w3QIDAQAB
AoGAH0cxOhFZDgzXWhDhnAJDw5s4roOXN4OhjiXa8W7Y3rhX3FJqmJSPuC8N9vQm
6SVbaLAE4SG5mLMueHlh4KXffEpuLEiNp9Ss3O4YfLiQpbRqE7Tm5SxKjvvQoZZe
zHorimOaChRL2it47iuWxzxSiRMv4c+j70GiWdxXnxe4UoECQQDzJB/0U58W7RZy
6enGVj2kWF732CoWFZWzi1FicudrBFoy63QwcowpoCazKtvZGMNlPWnC7x/6o8Gc
uSe0ga2xAkEA8C7PipPm1/1fTRQvj1o/dDmZp243044ZNyxjg+/OPN0oWCbXIGxy
WvmZbXriOWoSALJTjExEgraHEgnXssuk7QJBALl5ICsYMu6hMxO73gnfNayNgPxd
WFV6Z7ULnKyV7HSVYF0hgYOHjeYe9gaMtiJYoo0zGN+L3AAtNP9huqkWlzECQE1a
licIeVlo1e+qJ6Mgqr0Q7Aa7falZ448ccbSFYEPD6oFxiOl9Y9se9iYHZKKfIcst
o7DUw1/hz2Ck4N5JrgUCQQCyKveNvjzkkd8HjYs0SwM0fPjK16//5qDZ2UiDGnOe
uEzxBDAr518Z8VFbR41in3W4Y3yCDgQlLlcETrS+zYcL
-----END RSA PRIVATE KEY-----
"""
        self.keyfile = tempfile.NamedTemporaryFile(delete=True)
        self.keyfile.write(privkey)
        self.keyfile.flush()

        mailman.handlers.arc_sign.timestamp = "12345"

    def tearDown(self):
        self.keyfile.close()

    def test_arc_sign_message(self):
        config.push('arc_sign', """
        [ARC]
        enabled: yes
        authserv_id: lists.example.org
        selector: dummy
        domain: example.org
        sig_headers: mime-version, date, from, to, subject
        privkey: %s
        """ % (self.keyfile.name))

        self.addCleanup(config.pop, 'arc_sign')

        lst = create_list('test@example.com')
        msgdata = {'ARC-Standardize': True}

        msg = """Authentication-Results: lists.example.org; arc=none;
        spf=pass smtp.mfrom=jqd@d1.example;
        dkim=pass (1024-bit key) header.i=@d1.example; dmarc=pass
MIME-Version: 1.0
Return-Path: <jqd@d1.example.org>
Received: by 10.157.14.6 with HTTP; Tue, 3 Jan 2017 12:22:54 -0800 (PST)
Message-ID: <54B84785.1060301@d1.example.org>
Date: Thu, 14 Jan 2015 15:00:01 -0800
From: John Q Doe <jqd@d1.example.org>
To: arc@dmarc.org
Subject: Example 1

Hey gang,
This is a test message.
--J."""

        msg = message_from_string(msg)

        ArcSign().process(lst, msg, msgdata)

        res = ["i=1;lists.example.org;arc=none;spf=passsmtp.mfrom=jqd@d1"
               ".example;dkim=pass(1024-bitkey)header.i=@d1.example;dmar"
               "c=pass"]
        self.assertEqual("".join(msg["ARC-Authentication-Results"].split()),
                         "".join(res))

        sig = """a=rsa-sha256;
b=XWeK9DxQ8MUm+Me5GLZ5lQ3L49RdoFv7m7VlrAkKb3/C7jjw33TrTY0KYI5lkowvEGnAtm
5lAqLz67FxA/VrJc2JiYFQR/mBoJLLz/hh9y77byYmSO9tLfIDe2A83+6QsXHO3K6PxTz7+v
rCB4wHD9GADeUKVfHzmpZhFuYOa88=;
bh=KWSe46TZKCcDbH4klJPo+tjk5LWJnVRlP5pvjXFZYLQ=; c=relaxed/relaxed;
d=example.org; h=mime-version:date:from:to:subject;
i=1; s=dummy; t=12345"""
        sig = set("".join(sig.split()).split(";"))
        expected = "".join(msg["ARC-Message-Signature"].split()).split(";")
        expected = set(expected)
        self.assertEqual(sig, expected)

        seal = "".join(["a=rsa-sha256;b=Pg8Yyk1AgYy2l+kb6iy+mY106AXm5EdgDwJ"
                        "hLP7+XyT6yaS38ZUho+bmgSDorV+LyARH4A967A/oWMX3coyC7"
                        "pAGyI+hA3+JifL7P3/aIVP4ooRJ/WUgT79snPuulxE15jg6FgQ"
                        "E68ObA1/hy77BxdbD9EQxFGNcr/wCKQoeKJ8=; cv=none; d="
                        "example.org; i=1; s=dummy; t=12345"])
        seal = set("".join(seal.split()).split(";"))
        expected = set("".join(msg["ARC-Seal"].split()).split(";"))
        self.assertEqual(seal, expected)

    def test_arc_sign_message_no_chain_validation(self):
        config.push('arc_sign', """
        [ARC]
        enabled: yes
        authserv_id: lists.example.org
        selector: dummy
        domain:   example.org
        privkey: %s
        """ % (self.keyfile.name))

        self.addCleanup(config.pop, 'arc_sign')

        lst = create_list('test@example.com')
        msgdata = {}

        msg = """Authentication-Results: lists.example.org;
        spf=pass smtp.mfrom=jqd@d1.example;
        dkim=pass (1024-bit key) header.i=@d1.example; dmarc=pass
MIME-Version: 1.0
Return-Path: <jqd@d1.example.org>
Received: by 10.157.14.6 with HTTP; Tue, 3 Jan 2017 12:22:54 -0800 (PST)
Message-ID: <54B84785.1060301@d1.example.org>
Date: Thu, 14 Jan 2015 15:00:01 -0800
From: John Q Doe <jqd@d1.example.org>
To: arc@dmarc.org
Subject: Example 1

Hey gang,
This is a test message.
--J."""

        msg = message_from_string(msg)
        ArcSign().process(lst, msg, msgdata)

        self.assertEqual("ARC-Authentication-Results" in msg, False)
        self.assertEqual("ARC-Message-Signature" in msg, False)
        self.assertEqual("ARC-Seal" in msg, False)


class TestArcSignExceptions(unittest.TestCase):
    """Test ArcSigning Exceptions."""
    layer = ConfigLayer

    def setUp(self):
        privkey = b"""-----BEGIN RSA PRIVATE KEY-----
MIICXQIBAAKBgQDkHlOQoBTzWRiGs5V6NpP3idY6Wk08a5qhdR6wy5bdOKb2jLQi
Y/J16JYi0Qvx/byYzCNb3W91y3FutACDfzwQ/BC/e/8uBsCR+yz1Lxj+PL6lHvqM
KrM3rG4hstT5QjvHO9PzoxZyVYLzBfO2EeC3Ip3G+2kryOTIKT+l/K4w3QIDAQAB
AoGAH0cxOhFZDgzXWhDhnAJDw5s4roOXN4OhjiXa8W7Y3rhX3FJqmJSPuC8N9vQm
6SVbaLAE4SG5mLMueHlh4KXffEpuLEiNp9Ss3O4YfLiQpbRqE7Tm5SxKjvvQoZZe
zHorimOaChRL2it47iuWxzxSiRMv4c+j70GiWdxXnxe4UoECQQDzJB/0U58W7RZy
6enGVj2kWF732CoWFZWzi1FicudrBFoy63QwcowpoCazKtvZGMNlPWnC7x/6o8Gc
uSe0ga2xAkEA8C7PipPm1/1fTRQvj1o/dDmZp243044ZNyxjg+/OPN0oWCbXIGxy
WvmZbXriOWoSALJTjExEgraHEgnXssuk7QJBALl5ICsYMu6hMxO73gnfNayNgPxd
WFV6Z7ULnKyV7HSVYF0hgYOHjeYe9gaMtiJYoo0zGN+L3AAtNP9huqkWlzECQE1a
licIeVlo1e+qJ6Mgqr0Q7Aa7falZ448ccbSFYEPD6oFxiOl9Y9se9iYHZKKfIcst
o7DUw1/hz2Ck4N5JrgUCQQCyKveNvjzkkd8HjYs0SwM0fPjK16//5qDZ2UiDGnOe
uEzxBDAr518Z8VFbR41in3W4Y3yCDgQlLlcETrS+zYcL
-----END RSA PRIVATE KEY-----
"""
        self.keyfile = tempfile.NamedTemporaryFile(delete=True)
        self.keyfile.write(privkey)
        self.keyfile.flush()

        mailman.handlers.arc_sign.timestamp = "12345"

    def tearDown(self):
        self.keyfile.close()

    def test_arc_sign_unicode_privkey(self):
        config.push('arc_sign', """
        [ARC]
        enabled: yes
        authserv_id: lists.example.org
        selector: dummy
        domain: example.org
        sig_headers: mime-version, date, from, to, subject
        privkey:
        """)

        self.addCleanup(config.pop, 'arc_sign')

        lst = create_list('test@example.com')
        msgdata = {'ARC-Standardize': True}

        msg = """Authentication-Results: lists.example.org; arc=none;
        spf=pass smtp.mfrom=jqd@d1.example;
        dkim=pass (1024-bit key) header.i=@d1.example; dmarc=pass
MIME-Version: 1.0
Return-Path: <jqd@d1.example.org>
Received: by 10.157.14.6 with HTTP; Tue, 3 Jan 2017 12:22:54 -0800 (PST)
Message-ID: <54B84785.1060301@d1.example.org>
Date: Thu, 14 Jan 2015 15:00:01 -0800
From: John Q Doe <jqd@d1.example.org>
To: arc@dmarc.org
Subject: Example 1

Hey gang,
This is a test message.
--J."""

        msg = message_from_string(msg)

        ArcSign().process(lst, msg, msgdata)

        self.assertEqual("ARC-Authentication-Results" in msg, False)
        self.assertEqual("ARC-Message-Signature" in msg, False)
        self.assertEqual("ARC-Seal" in msg, False)

    def test_arc_sign_non_ascii_privkey(self):
        uni_keyfile = tempfile.NamedTemporaryFile(delete=True)
        uni_keyfile.write("¢¢¢¢¢¢¢".encode('utf-8'))
        uni_keyfile.flush()

        config.push('arc_sign', """
        [ARC]
        enabled: yes
        authserv_id: lists.example.org
        selector: dummy
        domain: example.org
        sig_headers: mime-version, date, from, to, subject
        privkey: %s
        """ % (uni_keyfile.name))

        self.addCleanup(config.pop, 'arc_sign')

        lst = create_list('test@example.com')
        msgdata = {'ARC-Standardize': True}

        msg = """Authentication-Results: lists.example.org; arc=none;
        spf=pass smtp.mfrom=jqd@d1.example;
        dkim=pass (1024-bit key) header.i=@d1.example; dmarc=pass
MIME-Version: 1.0
Return-Path: <jqd@d1.example.org>
Received: by 10.157.14.6 with HTTP; Tue, 3 Jan 2017 12:22:54 -0800 (PST)
Message-ID: <54B84785.1060301@d1.example.org>
Date: Thu, 14 Jan 2015 15:00:01 -0800
From: John Q Doe <jqd@d1.example.org>
To: arc@dmarc.org
Subject: Example 1

Hey gang,
This is a test message.
--J."""

        msg = message_from_string(msg)
        ArcSign().process(lst, msg, msgdata)

        self.assertEqual("ARC-Authentication-Results" in msg, False)
        self.assertEqual("ARC-Message-Signature" in msg, False)
        self.assertEqual("ARC-Seal" in msg, False)

        uni_keyfile.close()

    def test_arc_sign_dkim_exception(self):
        config.push('arc_sign', """
        [ARC]
        enabled: yes
        authserv_id: lists.example.org
        selector: dummy
        domain: example.org
        sig_headers: to, subject, date
        privkey: %s
        """ % (self.keyfile.name))

        self.addCleanup(config.pop, 'arc_sign')

        lst = create_list('test@example.com')
        msgdata = {'ARC-Standardize': True}

        msg = """Authentication-Results: lists.example.org; arc=none;
        spf=pass smtp.mfrom=jqd@d1.example;
        dkim=pass (1024-bit key) header.i=@d1.example; dmarc=pass
MIME-Version: 1.0
Return-Path: <jqd@d1.example.org>
Received: by 10.157.14.6 with HTTP; Tue, 3 Jan 2017 12:22:54 -0800 (PST)
Message-ID: <54B84785.1060301@d1.example.org>
Date: Thu, 14 Jan 2015 15:00:01 -0800
From: John Q Doe <jqd@d1.example.org>
To: arc@dmarc.org
Subject: Example 1

Hey gang,
This is a test message.
--J."""

        msg = message_from_string(msg)
        ArcSign().process(lst, msg, msgdata)

        self.assertEqual("ARC-Authentication-Results" in msg, False)
        self.assertEqual("ARC-Message-Signature" in msg, False)
        self.assertEqual("ARC-Seal" in msg, False)
