#!/usr/bin/env python3

import os
import re
import sys
import json
import subprocess

from time import strftime, localtime, sleep
from getpass import getpass
from datetime import datetime
from termcolor import colored
from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout


class HighlightXMPP(ClientXMPP):

    def __init__(self, jid, password):
        ClientXMPP.__init__(self, jid, password)

        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.alarm_handler)
        self.add_event_handler("message", self.command_handler)

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
        self.reload_config()

    def reload_config(self):
        print('Loading keywords ...')
        _keywords = get_dict('keywords.json')
        self.keywords = {}
        for _keyword in _keywords:
            r = re.compile(_keyword, re.IGNORECASE)
            self.keywords.update({r: _keywords[_keyword]})
        print('Loaded keywords:')
        for keyword in self.keywords:
            print(keyword, '\t=>', self.keywords[keyword])
        print('Loading supersuer list ...')
        self.superusers = get_dict('superusers.json')
        print('Loaded superusers:')
        for superuser in self.superusers:
            print(superuser, '\t=>', self.superusers[superuser])
        print("Initialization sequence completed. Ready for service.")

    def alarm_handler(self, msg):
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

    def command_handler(self, msg):
        if msg['type'] in ('chat', 'normal'):
            user = msg['from'].user
            priv = self.superusers[user]  # A list or a single string "SHELL"
            _path = os.environ['PWD'] + '/bin/:' + os.environ['PATH']
            _env = dict(os.environ, PATH=_path)
            if user in self.superusers:
                if msg['body'].startswith('sh '):
                    if priv == 'SHELL':
                        cmd = msg['body'].split(' ', 1)[1]  # A string passed DIRECTLY to shell
                        print('Handling command from {0}: {1}'.format(user, cmd))
                        try:
                            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, universal_newlines=True, env=_env)
                            msg.reply('Shell output:\n{0}'.format(output)).send()
                        except subprocess.CalledProcessError as e:
                            msg.reply('Error:\n{0}'.format(e.output)).send()
                    elif isinstance(priv, list):
                        reply = ('Arbitrary shell commands not allowed for you.\n'
                                 'You shall only execute these commands:\n'
                                 '{0}.\n'
                                 'Try: cmd <command>').format(priv)
                        msg.reply(reply).send()
                elif msg['body'].startswith('cmd '):
                    cmd = msg['body'].split(' ')[1:]  # A list passed safely to subprocess
                    if cmd[0] not in priv:
                        reply = ('You shall only execute these commands:\n'
                                 '{0}.').format(priv)
                        msg.reply(reply).send()
                    else:
                        print('Handling command from {0}: {1}'.format(user, cmd))
                        try:
                            output = subprocess.check_output(cmd, shell=False, stderr=subprocess.STDOUT, universal_newlines=True, env=_env)
                            msg.reply('Command output:\n{0}'.format(output)).send()
                        except subprocess.CalledProcessError as e:
                            msg.reply('Error:\n{0}'.format(e.output)).send()
                elif msg['body'] == 'reload':
                    self.reload_config()
                    msg.reply('Reloaded.').send()
                else:
                    msg.reply("Sorry, didn't catch that.").send()


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
