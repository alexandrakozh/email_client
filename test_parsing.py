import unittest
import sender
from collections import OrderedDict
from mock import MagicMock, patch
from argparse import ArgumentParser
import logging


all_args_for_list = [
    ('_smtp_address', 'smtp_gmail.com:587'),
    ('mail_from', 'foo@mail.net'),
    ('rcpt_to', ['bar@mail.net', 'baz@mail.net']),
    ('tls', True),
    ('data_file', '/tmp/text.txt'),
    ('attachment_path', ['1', '2']),
    ('count', 2),
    ('stdout', True),
    ('headers', ['Content-type=text/plain', 'Subject=Hello']),
    ('pwd', '123'),
    ('user', 'Alexandra Kozhemiakina'),
    ('concurrency', 5),
    ('data', 'Hello!Parsing is working!')
    ]
all_args_for_list = OrderedDict(all_args_for_list)

default_args = [
    ('tls', False),
    ('data_file', None),
    ('attachment_path', []),
    ('count', 1),
    ('stdout', False),
    ('headers', []),
    ('pwd', None),
    ('user', None),
    ('concurrency', 1),
    ('data', None)
    ]
default_args = OrderedDict(default_args)


required_args = [
    ('_smtp_address', 'smtp_gmail.com:587'),
    ('mail_from', 'foo@mail.net'),
    ('rcpt_to', 'bar@mail.net')
    ]
required_args = OrderedDict(required_args)

one_attachment_no_data = [
    ('_smtp_address', 'smtp_gmail.com:587'),
    ('mail_from', 'foo@mail.net'),
    ('rcpt_to', ['bar@mail.net', 'baz@mail.net']),
    ('attachment_path', ['1', '2']),
    ('data', None),
    ('data_file', None)
    ]
one_attachment_no_data = OrderedDict(one_attachment_no_data)

one_attachment_and_data = [
    ('_smtp_address', 'smtp_gmail.com:587'),
    ('mail_from', 'foo@mail.net'),
    ('rcpt_to', ['bar@mail.net', 'baz@mail.net']),
    ('attachment_path', ['1']),
    ('data', 'Hi!')
    ]
one_attachment_and_data = OrderedDict(one_attachment_and_data)

many_attachments = [
    ('_smtp_address', 'smtp_gmail.com:587'),
    ('mail_from', 'foo@mail.net'),
    ('rcpt_to', ['bar@mail.net', 'baz@mail.net']),
    ('attachment_path', ['1', '2', '3']),
    ('data', 'Hi!'),
    ('data_file', '1.txt')
    ]
many_attachments = OrderedDict(many_attachments)

one_data = [
    ('_smtp_address', 'smtp_gmail.com:587'),
    ('mail_from', 'foo@mail.net'),
    ('rcpt_to', ['bar@mail.net', 'baz@mail.net']),
    ('data', 'Hi!')
    ]
one_data = OrderedDict(one_data)

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

    def test_mail_argument_configure_default_values(self):
        parser = sender.mail_argument_configure()
        res = parser.parse_args(dict_to_cmd_list(required_args))
        for key, value in default_args.items():
            self.assertEqual(getattr(res, key), default_args[key])

    def test_mail_argument_configure_all_values(self):
        parser = sender.mail_argument_configure()
        res = parser.parse_args(dict_to_cmd_list(all_args_for_list))
        for key, value in all_args_for_list.items():
            self.assertEqual(getattr(res, arg_by_key(key)), all_args_for_list[key])

    def test_argument_configure_without_positionals(self):
        i = 0
        while i < 3:
            args_without_one_positional = []
            args_list = required_args.keys()[:]
            del args_list[i]
            for arg in args_list:
                tup = (arg, required_args[arg])
                args_without_one_positional.append(tup)
            args_without_one_positional = OrderedDict(args_without_one_positional)
            with patch.object(ArgumentParser, 'exit') as mock_method:
                parser = sender.mail_argument_configure()
                parser.parse_args(dict_to_cmd_list(args_without_one_positional))
                mock_method.assert_called()
            i += 1

    def test_generate_message_singlepart(self):
        for d in (one_attachment_no_data, one_data):
            with patch.object(sender.EmailCreation, 'create_singlepart_msg') as mock_method:
                parser = sender.mail_argument_configure()
                args = parser.parse_args(dict_to_cmd_list(d))
                m = sender.EmailCreation(args.mail_from, args.rcpt_to, args.user,
                                     args.headers, args.data, args.data_file,
                                     args.attachment_path)

                mock_method.assert_called()

    def test_generate_message_multipart(self):
        for i in (one_attachment_and_data, many_attachments):
            with patch.object(sender.EmailCreation, 'create_multipart_msg') as mock_method:
                parser = sender.mail_argument_configure()
                args = parser.parse_args(dict_to_cmd_list(i))
                m = sender.EmailCreation(args.mail_from, args.rcpt_to, args.user,
                                     args.headers, args.data, args.data_file,
                                     args.attachment_path)
                message = m.generate_message()
                mock_method.assert_called()

        


if __name__ == '__main__':
    FORMAT = u'%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT, filename=u'email.log',
                        level=logging.DEBUG)
    log = logging.getLogger(__name__)
    unittest.main()