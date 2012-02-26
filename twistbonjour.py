# encoding: utf-8
"""Classes for using Apple's Bonjour with Twisted."""
__docformat__ = "restructuredtext en"
#*****************************************************************************
#http://ipython.scipy.org/svn/ipython/ipython/sandbox/bgranger/bonjour/twistbonjour.py
#       Copyright (C) 2005  Fernando Perez <fperez@colorado.edu>
#                           Brian E Granger <ellisonbg@gmail.com>
#                           Benjamin Ragan-Kelley <benjaminrk@gmail.com>
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#*****************************************************************************

import pybonjour

from twisted.internet.interfaces import IReadDescriptor
from twisted.internet import reactor
from twisted.python import log
from twisted.internet import defer
from twisted.spread import pb
from zope.interface import implements, classImplements

class BonjourError(Exception):
    """Bonjour Error"""

    def __init__(self, errorCode):
        self.errorCode = errorCode

    def __str__(self):
        return "Bonjour Error: %i" % self.errorCode

class BonjourRegistrationError(BonjourError):
    """Bonjour Registration Error"""

    def __str__(self):
        return "Bonjour Registration Error: %i" % self.errorCode    

class BonjourBrowseError(BonjourError):
    """Bonjour Browse Error"""

    def __str__(self):
        return "Bonjour Browse Error: %i" % self.errorCode    

class BonjourResolveError(BonjourError):
    """Bonjour Resolve Error"""

    def __str__(self):
        return "Bonjour Resolve Error: %i" % self.errorCode    


class BonjourDescriptor(object,log.Logger):
    """Integrates a Bonjour file desc. into the Twisted event loop.
    The user should not create instances of this class directly.  They
    should instead be created by the higher level classes like
    BonjourAdvertiser, BonjourBrowser, etc."""

    implements(IReadDescriptor)

    def __init__(self, sdRef):
        """Wrap a Bonjour file descriptor

        @arg fd: file Descriptor to wrap
        @type fd: int
        @arg sdRef: Initialized ServiceDiscovery reference
        """
        self.sdRef = sdRef

    def fileno(self):
        """Return the raw file descriptor"""
        return self.sdRef.fileno()

    def doRead(self):
        """Called by the Twited event loop when the fd is ready to read."""
        ret = pybonjour.DNSServiceProcessResult(self.sdRef)

    def connectionLost(self, reason):
        """Called by the Twisted event loop when things are shutting down."""
        log.msg("Stopping Bonjour Advertisement")
        if self.sdRef is not None:
            #pybonjour.DNSServiceRefDeallocate(self.sdRef)
            self.sdRef.close()
            self.sdRef = None


class BonjourAdvertiser(object):
    """Advertise a service using Bonjour."""
    def __init__(self, name, regtype, port, callback, reactor,
                 flags=0, interfaceIndex=0, domain='local',host='', 
                 txtLen=0, txtRecord=None, context=None):
        """Create an object to advertise a Bonjour service.
        It will call the callback when there is a Bonjour event.  The callback
        should have the following arguments:

        def callback(sdRef,flags,errorCode,name,regtype,domain,context):

        The callback could be called more than once.

        @arg name: The name of the service
        @type name: str
        @arg regtype: The type of service, like _http._tcp
        @type regtype: str
        @arg domain: The Bonjour domain to browse, like local
        @type domain: str
        @arg port: The port to advertise as
        @type port: int
        @arg reactor: The Twisted reactor
        """

        self.name = name
        self.regtype = regtype
        self.domain = domain
        self.port = port
        self.reactor = reactor
        self.callback = callback
        self.flags = flags
        self.interfaceIndex = interfaceIndex
        self.host = host
        self.txtLen = txtLen
        self.txtRecord = txtRecord
        self.context = context
        self.sdRef = None

    def startAdvertising(self):
        """Advertise the service with Bonjour.
        This method returns a deferred.  Upon success, the result
        is a dictionary of information about the service.  Upon failure,
        the result is a Failure object that knows the BonjourError code.
        """

        # Initiate Registration of the service
        self.sdRef = pybonjour.DNSServiceRegister(self.flags,
                                           self.interfaceIndex,
                                           self.name,
                                           self.regtype,
                                           self.domain,
                                           self.host,
                                           self.port,
                                           self.txtRecord,
                                           self.callback,
                                           )

        # # Error check for immediate failure
        # if ret != pybonjour.kDNSServiceErr_NoError:
        #     log.err('Error %s' % ret)
        #     raise BonjourRegistrationError(ret)

        # Get the file descriptor and integrate with twisted

        self.bonjourDesc = BonjourDescriptor(self.sdRef)
        self.reactor.addReader(self.bonjourDesc)

        return None

    def stopAdvertising(self):
        """Stop advertising the service."""

        # Remove the Reader Deallocate the serviceReference
        self.reactor.removeReader(self.bonjourDesc)
        if self.sdRef is not None:
        #    pybonjour.DNSServiceRefDeallocate(self.sdRef)
            self.sdRef.close()
            self.sdRef = None

class BonjourBrowser(object):
    """Browse for a Bonjour advertised service."""

    def __init__(self, regtype, callback, reactor,
                 flags=0, interfaceIndex=0, domain='local', 
                 context=None):
        """Create an object to browse for a Bonjour service.

        It will call the callback when there is a Bonjour event.  The callback
        should have the following arguments:

        def callback(sdRef,flags,interfaceIndex,errorCode,
                      name,regtype,domain,context):

        The callback could be called more than once.

        @arg name: The name of the service
        @type name: str
        @arg regtype: The type of service, like _http._tcp
        @type regtype: str
        @arg domain: The Bonjour domain to browse, like local
        @type domain: str
        @arg port: The port to advertise as
        @type port: int
        @arg reactor: The Twisted reactor
        """
        self.sdRef = None
        self.regtype = regtype
        self.domain = domain
        self.reactor = reactor
        self.resolveCallback = callback
        self.flags = flags
        self.interfaceIndex = interfaceIndex
        self.context = context
        self.resolvers = []

    def startBrowsing(self):
        """Advertise the service with Bonjour.
        This method returns a deferred.  Upon success, the result
        is a dictionary of information about the service.  Upon failure,
        the result is a Failure object that knows the BonjourError code.
        """

        # Initiate Registration of the service
        self.sdRef = pybonjour.DNSServiceBrowse(self.flags,
                                                self.interfaceIndex,
                                                self.regtype,
                                                self.domain,
                                                self.browseCallback)

        self.bonjourDesc = BonjourDescriptor(self.sdRef)
        self.reactor.addReader(self.bonjourDesc)

        return None

    def stopBrowsing(self):
        """Stop advertising the service."""

        # Remove the Reader Deallocate the serviceReference
        self.reactor.removeReader(self.bonjourDesc)
        if self.sdRef is not None:
            self.sdRef.close()
            self.sdRef = None

    def browseCallback(self, sdRef, flags, interfaceIndex, errorCode, serviceName,
                    regtype, replyDomain):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            log.err("Bonjour error: %s" % errorCode)
            return

        if not (flags & pybonjour.kDNSServiceFlagsAdd):
            self.serviceRemovedCallback(serviceName,regtype,replyDomain)
            return

        res = BonjourResolver(serviceName,regtype,self.resolveCallback,
                              self.reactor,flags,interfaceIndex,replyDomain)
        res.startResolving()
        #self.resolvers.append(res)
    def serviceRemovedCallback(self, serviceName, regtype, relpyDomain):
        log.msg("Service Removed")


class BonjourResolver(object):
    """Resolve a Bonjour service."""

    def __init__(self, name, regtype, callback, reactor,
                 flags=0, interfaceIndex=0, domain='local', 
                 context=None):
        """Create an object to resolve a Bonjour service.
        It will call the callback when there is a Bonjour event.  The callback
        should have the following arguments:

        def callback(sdRef,flags,interfaceIndex,errorCode,
                      fullname,hosttarget,port,txtLen,txtRecord,context):

        The callback could be called more than once.

        @arg name: The name of the service
        @type name: str
        @arg regtype: The type of service, like _http._tcp
        @type regtype: str
        @arg domain: The Bonjour domain to browse, like local
        @type domain: str
        @arg port: The port to advertise as
        @type port: int
        @arg reactor: The Twisted reactor
        """

        self.sdRef = None
        self.name = name
        self.regtype = regtype
        self.domain = domain
        self.reactor = reactor
        self.callback = callback
        self.flags = flags
        self.interfaceIndex = interfaceIndex

    def startResolving(self):
        """Advertise the service with Bonjour.

        This method returns a deferred.  Upon success, the result
        is a dictionary of information about the service.  Upon failure,
        the result is a Failure object that knows the BonjourError code.
        """


        # Initiate Registration of the service
        self.sdRef = pybonjour.DNSServiceResolve(self.flags,
                                                 self.interfaceIndex,
                                                 self.name,
                                                 self.regtype,
                                                 self.domain,
                                                 self.callback)

        self.bonjourDesc = BonjourDescriptor(self.sdRef)
        self.reactor.addReader(self.bonjourDesc)

        return None

    def stopResolving(self):
        """Stop advertising the service."""

        # Remove the Reader Deallocate the serviceReference
        self.reactor.removeReader(self.bonjourDesc)
        if self.sdRef is not None:
            self.sdRef.close()
            self.sdRef = None

class PBServerFactoryBonjour(pb.PBServerFactory):
    """A replacement for PBServerFactory that enables Bonjour Registration."""

    def __init__(self, root, serviceName, 
                 serviceType, servicePort, unsafeTracebacks=False):

        pb.PBServerFactory(root, unsafeTracebacks)
        self.serviceName = serviceName
        self.serviceType = serviceType
        self.servicePort = servicePort

    def startFactory(self):
        self.ba = BonjourAdvertiser(self.serviceName,
                                    self.serviceType,
                                    self.servicePort,
                                    self.registrationCallback,
                                    reactor)
        self.ba.startAdvertising()

    def stopFactory(self):
        self.ba.stopAdvertising()

    def registrationCallback(self, sdRef, flags, errorCode, name, regtype, domain):
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            print errorCode, name, regtype, domain
        else:
            print "Bonjour registration error"

#def listenTCP(port, factory, backlog=50, interface='', serviceName):
#    def listenTCP(self, port, factory, backlog=50, interface='')
