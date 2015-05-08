#!/usr/bin/env python3

import os
import re
import sys
import json
import subprocess

from time import strftime, localtime, sleep
from getpass import getpass
from datetime import datetime, time
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
        print('Loading keywords ...')
        _keywords = get_dict('keywords.json')
        self.keywords = {}
        for _keyword in _keywords:
            r = re.compile(_keyword, re.IGNORECASE)
            self.keywords.update({r: _keywords[_keyword]})
        print('Loaded keywords:')
        for keyword in self.keywords:
            print(keyword, '\t=>', self.keywords[keyword])
        print("Initialization sequence completed. Ready for service.")

    def message_handler(self, msg):
        timestamp = strftime('%Y-%m-%d %H:%M:%S', localtime())
        if msg['type'] in ('chat', 'normal'):
            if msg['body'].startswith('[ALARM]'):
                mm = colored(msg['body'], 'red')
                print(timestamp, mm)
                for keyword in self.keywords:
                    if keyword.search(msg['body']):
                        notify_send('HEADS UP!!!', msg['body'])
                        if self.keywords[keyword]:
                            for number in self.keywords[keyword]:
                                skype_call(number)
                                sleep(3)
            elif msg['body'].startswith('[RECOVERY]'):
                mm = colored(msg['body'], 'green')
                print(timestamp, mm)
            else:
                mm = msg['body']
                print(timestamp, mm)


def get_dict(dict_file):
    try:
        with open(dict_file, 'r') as fd:
            return json.load(fd)
    except FileNotFoundError:
        print(dict_file, ' not found.')
        sys.exit(1)


def notify_send(summary, body, urgency='critical'):
    cmd = ['notify-send', '-u', urgency, summary, body]
    env = dict(os.environ, DISPLAY=':0')
    subprocess.call(cmd, env=env)
    print('Notify sent.')


def in_time_range():
    try:
        t1 = config_dict['call_start_hour']
        t2 = config_dict['call_end_hour']
    except KeyError:
        return True
    now_hour = datetime.now().hour
    if t1 < t2 and t1 <= now_hour < t2:
        return True
    elif t1 > t2 and (t1 <= now_hour or now_hour < t2):
        return True
    return False


def skype_call(number, prefix='+86'):
    if not in_time_range():
        print('Not making calls')
        return None
    if not str(number).startswith('+'):
        _number = prefix + str(number)
    else:
        _number = str(number)
    cmd = ['skype', '--call', _number]
    env = dict(os.environ, DISPLAY=':0')
    try:
        subprocess.call(cmd, env=env)
        print('Outgoing call: ', _number)
    except subprocess.CalledProcessError:
        print('Failed to call', _number)


if __name__ == '__main__':
    try:
        config_dict = get_dict('xmpp.json')
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
