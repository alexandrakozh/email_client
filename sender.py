import argparse
import re
import sys


def header_type(string):
    pattern = re.compile("(?P<header_name>\w+-?\w+)=(?P<header_value>[\w ]+)")
    match =  pattern.match(string)
    if not match:
        msg = "%r is not an appropriate header type (name=value)" % string
        raise argparse.ArgumentTypeError(msg)
    return string


def mail_agrument_configuring():
    if sys.stdin is not None:
        return reading_from_stdin()
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument('smtp_address', action='store',
                            help='Host (ip-adress) and port of mail server')
        parser.add_argument('--mail_from', action='store',
                            required = True,
                            help='E-mail adress of sender')
        parser.add_argument('--rcpt_to', action='store', nargs='+', required=True,
                            help='People who e-mail adress to')
        parser.add_argument('--tls', action='store_true',
                            help='Configuring TLS access')
        parser.add_argument('--user', action='store', default=None,
                            help='Name of user, who send e-mail')
        parser.add_argument('--pwd', action='store', default=None,
                            help='Password of sender')
        parser.add_argument('--header', action='store', nargs='*', default=[],
                            type=header_type,
                            help='Headers of the message in format name=value')
        parser.add_argument('--data', action='store', default=None,
                            help='Text, which message will contain')
        parser.add_argument('--data_file', action='store', default=None,
                            help='A path to e-mail script')
        parser.add_argument('--count', action='store', default=1, type=int,
                            help='A number of copies to send')
        parser.add_argument('--concurrency', action='store', default=1, type=int,
                            help='A number of simultaneous send')
        parser.add_argument('--send_stdout', action='store_true',
                            help='Configuring sending an e-mail and redirecting it to STDOUT')
        parser.add_argument('--attachment_path', action='store', nargs='*', default=[],
                            help='A path to attachments in the message')
        return parser


def reading_from_stdin():
    file = sys.stdin
    with open(file, 'rb') as email_from_stdin:
        msg = email_from_stdin.read()
    return msg




if __name__ == "__main__":
    args = mail_agrument_configuring()
    print args.parse_args()


