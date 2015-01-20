#!/usr/bin/python
# -*- coding: utf-8 -*-

# nest.py -- a python interface to the Nest Thermostat
# by Scott M Baker, smbaker@gmail.com, http://www.smbaker.com/
#
# Usage:
#    'nest.py help' will tell you what to do and how to do it
#
# Licensing:
#    This is distributed under the Creative Commons 3.0 Non-commercial,
#    Attribution, Share-Alike license. You can use the code for noncommercial
#    purposes. You may NOT sell it. If you do use it, then you must make an
#    attribution to me (i.e. Include my name and thank me for the hours I spent
#    on this)
#
# Acknowledgements:
#    Chris Burris's Siri Nest Proxy was very helpful to learn the nest's
#       authentication and some bits of the protocol.
###############################################################################

# --- START: Workaround for HTTP ERROR from TLSv2------------------------------
import httplib
from httplib import HTTPConnection, HTTPS_PORT
import ssl
import socket

class HTTPSConnectionLocal(HTTPConnection):
    "This class allows communication via SSL."

    default_port = HTTPS_PORT

    def __init__(self, host, port=None, key_file=None, cert_file=None,
                 strict=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                 source_address=None):
        HTTPConnection.__init__(self, host, port, strict, timeout, 
                                source_address)
        self.key_file = key_file
        self.cert_file = cert_file

    def connect(self):
        "Connect to a host on a given (SSL) port."

        sock = socket.create_connection((self.host, self.port),
                                        self.timeout, self.source_address)
        
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
  
        # WORKAROUND: use TLSv1
        self.sock = ssl.wrap_socket(sock, self.key_file, self.cert_file,
                                    ssl_version=ssl.PROTOCOL_TLSv1)

httplib.HTTPSConnection = HTTPSConnectionLocal
# ---END: Workaround for HTTP ERROR from TLSv2---------------------------------


import urllib
import urllib2
import sys
from optparse import OptionParser

try:
   import json
except ImportError:
   try:
       import simplejson as json
   except ImportError:
       print "No json library available. I recommend installing either python-json"
       print "or simplejson."
       sys.exit(-1)

class Nest:
    def __init__(self, username, password, serial=None, index=0, units="F"):
        self.username = username
        self.password = password
        self.serial = serial
        self.units = units
        self.index = index

    def loads(self, res):
        if hasattr(json, "loads"):
            res = json.loads(res)
        else:
            res = json.read(res)
        return res

    def login(self):
        data = urllib.urlencode({"username": self.username, "password": self.password})

        req = urllib2.Request("https://home.nest.com/user/login",
                              data,
                              {"user-agent":"Nest/1.1.0.10 CFNetwork/548.0.4"})

        res = urllib2.urlopen(req).read()

        res = self.loads(res)

        self.transport_url = res["urls"]["transport_url"]
        self.access_token = res["access_token"]
        self.userid = res["userid"]

    def get_status(self):
        req = urllib2.Request(self.transport_url + "/v2/mobile/user." + self.userid,
                              headers={"user-agent":"Nest/1.1.0.10 CFNetwork/548.0.4",
                                       "Authorization":"Basic " + self.access_token,
                                       "X-nl-user-id": self.userid,
                                       "X-nl-protocol-version": "1"})

        res = urllib2.urlopen(req).read()

        res = self.loads(res)

        self.structure_id = res["structure"].keys()[0]

        if (self.serial is None):
            self.device_id = res["structure"][self.structure_id]["devices"][self.index]
            self.serial = self.device_id.split(".")[1]

        self.status = res

        #print "res.keys", res.keys()
        #print "res[structure][structure_id].keys", res["structure"][self.structure_id].keys()
        #print "res[device].keys", res["device"].keys()
        #print "res[device][serial].keys", res["device"][self.serial].keys()
        #print "res[shared][serial].keys", res["shared"][self.serial].keys()

    def temp_in(self, temp):
        if (self.units == "F"):
            return (temp - 32.0) / 1.8
        else:
            return temp

    def temp_out(self, temp):
        if (self.units == "F"):
            return temp*1.8 + 32.0
        else:
            return temp

    def show_status(self):
        shared = self.status["shared"][self.serial]
        device = self.status["device"][self.serial]

        allvars = shared
        allvars.update(device)

        for k in sorted(allvars.keys()):
             print k + "."*(32-len(k)) + ":", allvars[k]

    def show_curtemp(self):
        temp = self.status["shared"][self.serial]["current_temperature"]
        temp = self.temp_out(temp)

        print "%0.1f" % temp

    def show_curmode(self):
        mode = self.status["shared"][self.serial]["target_temperature_type"]
        if mode == 'range':
            min_temp = self.status["shared"][self.serial]["target_temperature_low"]
            min_temp = self.temp_out(min_temp);
            max_temp = self.status["shared"][self.serial]["target_temperature_high"]
            max_temp = self.temp_out(max_temp);
            print "range {0:.1f}°{2} - {1:.1f}°{2}".format(min_temp, max_temp, self.units)
        else:
            print mode

    def set_temperature(self, temp):
        temp = self.temp_in(temp)

        data = '{"target_change_pending":true,"target_temperature":' + '%0.1f' % temp + '}'
        req = urllib2.Request(self.transport_url + "/v2/put/shared." + self.serial,
                              data,
                              {"user-agent":"Nest/1.1.0.10 CFNetwork/548.0.4",
                               "Authorization":"Basic " + self.access_token,
                               "X-nl-protocol-version": "1"})

        res = urllib2.urlopen(req).read()

        print res

    def set_fan(self, state):
        data = '{"fan_mode":"' + str(state) + '"}'
        req = urllib2.Request(self.transport_url + "/v2/put/device." + self.serial,
                              data,
                              {"user-agent":"Nest/1.1.0.10 CFNetwork/548.0.4",
                               "Authorization":"Basic " + self.access_token,
                               "X-nl-protocol-version": "1"})

        res = urllib2.urlopen(req).read()

        print res

    def set_mode(self, state):
        data = '{"target_change_pending":true,"target_temperature_type":"' + str(state) + '"}'
        req = urllib2.Request(self.transport_url + "/v2/put/shared." + self.serial, 
                              data, 
                              {"user-agent":"Nest/1.1.0.10 CFNetwork/548.0.4", 
                               "Authorization":"Basic " + self.access_token,
                               "X-nl-protocol-version": "1"})

        res = urllib2.urlopen(req).read()

        print res

def create_parser():
   parser = OptionParser(usage="nest [options] command [command_options] [command_args]",
        description="Commands: temp, fan, mode, show, curtemp, curhumid, curmode, current",
        version="unknown")

   parser.add_option("-u", "--user", dest="user",
                     help="username for nest.com", metavar="USER", default=None)

   parser.add_option("-p", "--password", dest="password",
                     help="password for nest.com", metavar="PASSWORD", default=None)

   parser.add_option("-c", "--celsius", dest="celsius", action="store_true", default=False,
                     help="use celsius instead of fahrenheit")

   parser.add_option("-s", "--serial", dest="serial", default=None,
                     help="optional, specify serial number of nest thermostat to talk to")

   parser.add_option("-i", "--index", dest="index", default=0, type="int",
                     help="optional, specify index number of nest to talk to")


   return parser

def help():
    print "syntax: nest [options] command [command_args]"
    print "options:"
    print "   --user <username>      ... username on nest.com"
    print "   --password <password>  ... password on nest.com"
    print "   --celsius              ... use celsius (the default is fahrenheit)"
    print "   --serial <number>      ... optional, specify serial number of nest to use"
    print "   --index <number>       ... optional, 0-based index of nest"
    print "                                (use --serial or --index, but not both)"
    print
    print "commands: temp, fan, mode, show, curtemp, curhumid, curmode, current"
    print "    temp <temperature>         ... set target temperature"
    print "    fan [auto|on]              ... set fan state"
    print "    mode [cool|heat|off|range] ... set hvac state"
    print "    show                       ... show everything"
    print "    curtemp                    ... print current temperature"
    print "    curhumid                   ... print current humidity"
    print "    curmode                    ... print current mode"
    print "    current                    ... print current temperature & humidity"
    print
    print "examples:"
    print "    nest.py --user joe@user.com --password swordfish temp 73"
    print "    nest.py --user joe@user.com --password swordfish fan auto"

def main():
    parser = create_parser()
    (opts, args) = parser.parse_args()

    if (len(args)==0) or (args[0]=="help"):
        help()
        sys.exit(-1)

    if (not opts.user) or (not opts.password):
        print "how about specifying a --user and --password option next time?"
        sys.exit(-1)

    if opts.celsius:
        units = "C"
    else:
        units = "F"

    n = Nest(opts.user, opts.password, opts.serial, opts.index, units=units)
    n.login()
    n.get_status()

    cmd = args[0]

    if (cmd == "temp"):
        if len(args)<2:
            print "please specify a temperature"
            sys.exit(-1)
        n.set_temperature(int(args[1]))
    elif (cmd == "fan"):
        if len(args)<2:
            print "please specify a fan state of 'on' or 'auto'"
            sys.exit(-1)
        n.set_fan(args[1])
    elif (cmd == "mode"):
        if len(args)<2:
            print "please specify an hvac mode of 'cool', 'heat', 'off', or 'range'"
            sys.exit(-1)
        n.set_mode(args[1])
    elif (cmd == "show"):
        n.show_status()
    elif (cmd == "curtemp"):
        n.show_curtemp()
    elif (cmd == "curhumid"):
        print n.status["device"][n.serial]["current_humidity"]
    elif (cmd == "curmode"):
        n.show_curmode()
    elif (cmd == "current"):
        temp = n.status["shared"][n.serial]["current_temperature"]
        temp = n.temp_out(temp)
        auto_away = n.status["shared"][n.serial]["auto_away"]
        print "{0:.1f}°{1}".format(temp, units)
        print "%d%% Humidity" % n.status["device"][n.serial]["current_humidity"]
        if (auto_away == 1):
            print "[Auto Away Enabled]"
    else:
        print "misunderstood command:", cmd
        print "do 'nest.py help' for help"

if __name__=="__main__":
   main()





