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

import json
import re
import sys
import websocket

class DutchRoom :
    """Main class that represents a Room object in the D&D management App"""

    # Find out a room ID from the master speaker, by asking for a list
    # of targets. Even though the query specifies "room", it seems to
    # get speakers as well.
    def getRoomId(self):
        self.ws = websocket.WebSocket()
        self.ws.connect(self.masterurl)
        self.ws.send( self.getCommand('targets', {}, methodVal = 'read', targetVal = '*') )
        response = self.ws.recv()
        data = json.loads(response)

        # we expect an array of responses, one of which is a room, the
        # other two are the speakers. The room has always been the
        # first one in dumped traffic, but don't assume this.
        respcnt = (len(data['data']))
        self.roomtarget = ''
        for i in range(respcnt):
            if data['data'][i]['targetType'] == 'room' :   # found a room, so copy its ID
                self.roomtarget = data['data'][i]['target']


    def getCommand(self, endpointVal, dataDict, methodVal = 'update', targetVal = None):
        if targetVal is None:
            targetVal = self.roomtarget
        jsoncommand = {}
        jsoncommand['meta'] = {}
        jsoncommand['meta']['id'] = '999912345678'
        jsoncommand['meta']['method'] = methodVal
        jsoncommand['meta']['endpoint'] = endpointVal
        jsoncommand['meta']['targetType'] = 'room'
        jsoncommand['meta']['target'] = targetVal
        jsoncommand['data'] = dataDict
        return json.dumps(jsoncommand)


    def doPlay(self):
        self.ws.send( self.getCommand( 'streaming-api', {'method': 'Play', 'arguments': []} ) )
        self.ws.recv()


    def doPause(self):
        self.ws.send( self.getCommand( 'streaming-api', {'method': 'Pause', 'arguments': []} ) )
        self.ws.recv()


    def doNext(self):
        self.ws.send( self.getCommand( 'streaming-api', {'method': 'Next', 'arguments': []} ) )
        self.ws.recv()


    def doPrevious(self):
        self.ws.send( self.getCommand( 'streaming-api', {'method': 'Previous', 'arguments': []} ) )
        self.ws.recv()


    def doSleep(self):
        self.ws.send( self.getCommand( 'sleep', {'enable': True} ) )
        self.ws.recv()


    def doWake(self):
        self.ws.send( self.getCommand( 'sleep', {'enable': False} ) )
        self.ws.recv()


    def setInput(self, inputMode):
        # Wake if sleeping
        self.doWake()

        # Reset volume to play it safe
        self.setVolume(-30.0)
        self.ws.send( self.getCommand('inputMode', {'inputMode': inputMode} ) )
        self.ws.recv()


    def setVolume(self, gain):
        self.ws.send( self.getCommand('gain2', {'gain': gain} ) )
        self.ws.recv()


    def doPreset(self, presetId):
        print(self.getCommand('preset2', {'presetID': presetId}, methodVal = 'select' ) )
        self.ws.send( self.getCommand('preset2', {'presetID': presetId}, methodVal = 'select' ) )
        self.ws.recv()


    def doBacch(self, onOff):
        self.ws.send( self.getCommand('bacch-enabled', {'enable': onOff} ) )
        self.ws.recv()


    def doDump(self):
        self.ws.send( self.getCommand('network', {}, methodVal = 'read', targetVal = '*') )
        response = self.ws.recv()
        self.dump = json.loads(response)
        print(json.dumps(self.dump, indent=2))


    def doTogglePlay(self):
        # Dump room state to see if currently playing
        self.ws.send( self.getCommand('network', {}, methodVal = 'read', targetVal = '*') )
        response = self.ws.recv()
        self.dump = json.loads(response)
        isPlaying = self.dump['data']['state'][self.roomtarget]['data']['streamingInfo']['is_playing']

        # Toggle based on play state
        if isPlaying:
            self.doPause()
        else:
            self.doPlay()


    def __init__(self, ipAddress):
        self.masterurl = 'ws://' + ipAddress + ':8768'

        # Get the Room ID we want to talk to.
        self.getRoomId()


    def __del__(self):
        self.ws.close()


def main():
    valid_args = ['wake', 'sleep', 'dump', 'inputAes', 'inputRoon', 'inputSpotify', 'play', 'pause', 'next', 'previous', 'toggleplay', 'presetHarman', 'presetBass', 'presetLoud1', 'presetLoud3', 'bacchOn', 'bacchOff']

    # check for valid IP address
    ipRegex = re.compile('^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')

    args = sys.argv[1:]
    if (len(args) < 2) or not re.match(ipRegex, args[0]) or (args[1] not in valid_args):
        print ('Usage:', sys.argv[0], '<ip_address>', valid_args)
        return 1

    room = DutchRoom(args[0])

    match args[1]:
        case 'dump':
            room.doDump()
        case 'wake':
            room.doWake()
        case 'sleep':
            room.doSleep()
        case 'play':
            room.doPlay()
        case 'pause':
            room.doPause()
        case 'toggleplay':
            room.doTogglePlay()
        case 'next':
            room.doNext()
        case 'previous':
            room.doPrevious()
        case 'inputAes':
            room.setInput('aes')
        case 'inputRoon':
            room.setInput('Roon Ready')
        case 'inputSpotify':
            room.setInput('Spotify Connect')
        case 'presetHarman':
            room.doPreset('2d0f652b-4631-4f11-8205-85a9b223a8a9')
        case 'presetBass':
            room.doPreset('3ae3dd8f-a37c-44c0-8a5f-b84128b174af')
        case 'presetLoud1':
            room.doPreset('f88c9fd8-42c1-4411-8371-11daa293504f')
        case 'presetLoud3':
            room.doPreset('1212251f-fbe7-49e8-94e5-f21271a10dd9')
        case 'bacchOn':
            room.doBacch(True)
        case 'bacchOff':
            room.doBacch(False)

    return 0

if __name__ == '__main__':
    sys.exit(main())
