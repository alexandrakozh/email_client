import unittest
import sender
from collections import OrderedDict
from argparse import ArgumentError


all_args_for_list = {
    '_smtp_address': 'smtp_gmail.com:587',
    'mail_from': 'foo@mail.net',
    'rcpt_to': ['bar@mail.net', 'baz@mail.net'],
    'tls': True,
    'data_file': '/tmp/text.txt' ,
    'attachment_path': ['1', '2'],
    'count': 2,
    'send_stdout': True,
    'header': ['Content-type=text/plain', 'Subject=Hello'],
    'pwd': '123',
    'user': 'Alexandra Kozhemiakina',
    'concurrency': 5,
    'data': 'Hello!Parsing is working!'
    }
all_args_for_list = OrderedDict(all_args_for_list)

default_args = {
    'tls': False,
    'data_file': None,
    'attachment_path': [],
    'count': 1,
    'send_stdout': False,
    'header': [],
    'pwd': None,
    'user': None,
    'concurrency': 1,
    'data': None
    }
default_args = OrderedDict(default_args)


required_args = {
    '_smtp_address': 'smtp_gmail.com:587',
    'mail_from': 'foo@mail.net',
    'rcpt_to': 'bar@mail.net'
    }
required_args = OrderedDict(required_args)


def dict_to_cmd_list(d):
    res = []
    for k, v in d.iteritems():
        if arg_by_key(k) == k:
            res.append('--' + k)

        if isinstance(v, bool):
            continue

        if isinstance(v, list):
            res.extend(v)
        else:
            res.append(str(v))
    return res


def arg_by_key(arg):
    if arg.startswith('_'):
        return arg[len('_'):]
    return arg


class TestEmailClient(unittest.TestCase):

    def test_mail_argument_configuring_default_values(self):
        parser = sender.mail_agrument_configuring()
        res = parser.parse_args(dict_to_cmd_list(required_args))
        for key, value in default_args.items():
            self.assertEqual(getattr(res, key), default_args[key])

    def test_mail_argument_configuring_all_values(self):
        parser = sender.mail_agrument_configuring()
        res = parser.parse_args(dict_to_cmd_list(all_args_for_list)) #namespace obj
        for key, value in all_args_for_list.items():
            self.assertEqual(getattr(res, arg_by_key(key)), all_args_for_list[key])

    def test_mail_argument_configuring_without_positional_arg(self):
        parser = sender.mail_agrument_configuring()
        with self.assertRaises(ArgumentError):
            parser.parse_args(dict_to_cmd_list(not_pos_args))


if __name__ == '__main__':
    unittest.main()