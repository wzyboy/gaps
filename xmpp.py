#!/usr/bin/env python3

import json
import subprocess

from time import strftime, localtime
from getpass import getpass
from termcolor import colored
from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout


class HighlightXMPP(ClientXMPP):

    def __init__(self, jid, password):
        ClientXMPP.__init__(self, jid, password)

        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message_handler)

    def session_start(self, event):

        print("Getting roster ...")
        try:
            self.send_presence()
            self.get_roster()
        except IqError as err:
            print('There was an error getting the roster')
            print(err.iq['error']['condition'])
            self.disconnect()
        except IqTimeout:
            print('Server is taking too long to respond')
            self.disconnect()
        print("Initialization sequence completed. Ready for service.")

    def message_handler(self, msg):

        timestamp = strftime('%Y-%m-%d %H:%M:%S', localtime())
        if msg['type'] in ('chat', 'normal'):
            if msg['body'].startswith('[ALARM]'):
                mm = colored(msg['body'], 'red')
                print(timestamp, mm)
                notify_send('[ALARM]', msg)
            elif msg['body'].startswith('[RECOVERY]'):
                mm = colored(msg['body'], 'green')
                print(timestamp, mm)
            else:
                mm = msg['body']
                print(timestamp, mm)


def get_config(config_file):

    try:
        config = open(config_file, 'r')
    except OSError:
        print(config_file, ' not found.')
        sys.exit(1)

    config_dict = json.load(config)
    config.close()

    return config_dict


def notify_send(summary, body, urgency='critical'):

    cmd = ['notify-send', '-u', urgency, summary, body]
    subprocess.call(cmd)


if __name__ == '__main__':

    try:
        config_dict = get_config('xmpp.json')
        jid = config_dict['jid']
        resource = config_dict['resource']
        host = config_dict['host']
        port = config_dict['port']
    except KeyError as e:
        print('Missing key: ', e)
        sys.exit(1)
    try:
        password = config_dict['password']
    except KeyError:
        password = getpass()

    full_jid = '/'.join([jid, resource])
    xmpp = HighlightXMPP(full_jid, password)

    xmpp.connect(address=(host, port))
    print('Connected. Logging in ...')
    xmpp.process(block=False)