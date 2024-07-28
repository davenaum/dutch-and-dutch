"""Simple Class for controlling Sleep mode on Dutch & Dutch 8C loudspeakers."""
#
# usage: dutch.py DNSnameofaspeaker sleep|wake
#
# The message format was found by dumping websocket traffic from the
# D&D web client, and picking out the appropriate exchanges. So
# there's a chance of it being broken by future firmware updates.
#
# The protocol between the management agent (App or web) and the
# speakers seems quite comprehensive and allows for reading state,
# updating state, and registering for notification of changes. This
# allows multiple management agents to be in use, and for all to stay
# up to date with the current status.
#
# This code just assumes a simple setup of a pair of speakers in one
# room, and will act on those (or it might work on the first room if
# you have more than one). It just makes simple command/response
# websocket requests, nothing asynchronous is expected.
#
# The D&D web app initially reads "ClerkIP.js" from whatever server
# was specified in the initial HTTP URL and then connects to the mDNS
# name listed in that response.
#
# This script will just go straight into trying to talk via websocket
# on the appropriate port of the speaker specified in the first CLI
# argument. There isn't really any error checking, so it will probably
# just backtrace if anything unexpected happens.
#
# To make the script work reliably using the Home Assistant
# command_line integration, if you supply the script with an 
# IP address instead of a hostname, it will assume that is the
# master speaker, and talk to it directly.  You can find the master
# speaker by giving it the hostname, and it will print out the master's 
# IP address
#
#

import time
import json
import re
import sys
import socket
import websocket

class DutchRoom :
    """Main class that represents a Room object in the D&D management App"""

    # Talk to either speaker and find out who the master is. Not sure
    # if this really matters, but we might as well, because the App
    # does it. If an IP address is provided as the speaker name we will just
    # assume that one is the master
    def getmasterurl(self, rawip):
        """Get the master speaker websocket URL"""
        if rawip :
            self.masterurl = 'ws://'+self.name+':8768'
        else :
            ws = websocket.WebSocket()
            ws.connect('ws://'+self.name+':8768')
            ws.send(
                json.dumps(
                    {"meta":{"id":"999912345678","method":"read","endpoint":\
                             "master"},"data":{}}
                )
            )
            response = ws.recv()
            data = json.loads(response)
            ws.close()
            masterhost = data['data']['address']['hostname']
            # Especially on Home Assistant, the mDNS resolution sometimes fails
            # initially. So retry it a few times before giving up
            tries = 5
            for i in range(tries) :
                try:
                    masteraddr = socket.gethostbyname(masterhost)   # IPv4 address only
                except:
                    if i == (tries - 1) :
                        print("gethostbyname ", masterhost," failed")
                        raise 
                    else:
                        time.sleep(1)
                        continue
                    break
            masterport = str(data['data']['address']['port_ascend'])
            self.masterurl = "ws://" + masteraddr + ":" + masterport
            print ("Master speaker IP: ", masteraddr)

    # Find out a room ID from the master speaker, by asking for a list
    # of targets. Even though the query specifies "room", it seems to
    # get speakers as well.
    def getroomid(self):
        """Get the Room ID from the master speaker"""
        self.ws = websocket.WebSocket()
        self.ws.connect(self.masterurl)
        self.ws.send(
            json.dumps(
                {"meta":{"id":"999912345678","method":"read","endpoint":\
                         "targets","targetType":"room","target":"*"},"data":{}}
            )
        )
        response = self.ws.recv()
        data = json.loads(response)
        # we expect an array of responses, one of which is a room, the
        # other two are the speakers. The room has always been the
        # first one in dumped traffic, but don't assume this.
        respcnt = (len(data['data']))
        self.roomtarget = ""
        for i in range(respcnt):
            if data['data'][i]['targetType'] == "room" :   # found a room, so copy its ID
                self.roomtarget = data['data'][i]['target']
        # leave the websocket open for the next call.

    def getcommand(self, endpointval, datakey, dataval):
        jsoncommand = {}

        meta = {}
        meta['id'] = '999912345678'
        meta['method'] = 'update'
        meta['endpoint'] = endpointval
        meta['targetType'] = 'room'
        meta['target'] = self.roomtarget
        jsoncommand['meta'] = meta

        data = {}
        data[datakey] = dataval
        jsoncommand['data'] = data

        return json.dumps(jsoncommand)

    def dosleep(self):
        self.ws.send( self.getcommand( 'sleep', 'enable', True ) )
        self.ws.recv()

    def dowake(self):
        self.ws.send( self.getcommand( 'sleep', 'enable', False ) )
        self.ws.recv()

    def setinput(self, inputMode):
        # Reset volume to play it safe
        self.setvolume(-30.0)
        self.ws.send( self.getcommand('inputMode', 'inputMode', inputMode) )
        self.ws.recv()

    def setvolume(self, gain):
        self.ws.send( self.getcommand('gain2', 'gain', gain) )
        self.ws.recv()

    def dodump(self):
        # get the "network" data which seems to include almost all parameters and settings
        self.ws.send(
            json.dumps(
                {"meta":{"id":"999912345678","method":"read","endpoint":\
                         "network","targetType":"room","target":"*"},"data":{}}
            )
        )
        response = self.ws.recv()
        self.dump = json.loads(response)
        print(json.dumps(self.dump, indent=2))


    def __init__(self,name, rawip):
        self.name = name

        # Get the Room ID we want to talk to.
        self.getmasterurl(rawip)
        self.getroomid()

    def __del__(self):
        self.ws.close()


def main():
    valid_args = ['wake', 'sleep', 'dump', 'inputAes', 'inputRoon', 'inputSpotify']

    args = sys.argv[1:]
    if (len(args) < 2) or (args[1] not in valid_args):
        print ("Usage:", sys.argv[0], "name", valid_args)
        return 1

    # check for first argument being an IP address, if so we assume it's the master
    pat = re.compile ("^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
    rawip = bool(re.match(pat, args[0]))

    room = DutchRoom(args[0], rawip)

    command = args[1]

    match command:
        case 'dump':
            room.dodump()
        case 'wake':
            room.dowake()
        case 'sleep':
            room.dosleep()
        case 'inputAes':
            room.setinput('aes')
        case 'inputRoon':
            room.setinput('Roon Ready')
        case 'inputSpotify':
            room.setinput('Spotify Connect')

    return 0

if __name__ == '__main__':
    sys.exit(main())
