import argparse
import re
import sys
import os.path
import os
from email.mime.text import MIMEText
import mimetypes
import email
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from smtplib import SMTP
import logging
from email.header import Header
import uuid
import select
import threading
from itertools import chain, repeat


FORMAT = u'%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=FORMAT, filename=u'email.log',
                    level=logging.DEBUG)
log = logging.getLogger(__name__)


def header_type(string):
    pattern = re.compile("(?P<header_name>.+)=(?P<header_value>.+)")
    match = pattern.match(string)
    if not match:
        msg = "%r is not an appropriate header type (name=value)" % string
        raise argparse.ArgumentTypeError(msg)
    return string


def get_header_name_value(header):
    header_name, header_value = header.split("=")
    return header_name, header_value


def read_from_stdin():
    return sys.stdin.read()


def message_in_stdin():
    return (
        not sys.stdin.isatty()
        and sys.stdin in select.select([sys.stdin], [], [], 0)[0]
    )


def replace_id_in_string(string, counter):
    if '#id#' in string:
        return string.replace('#id#', str(counter))
    elif '#uuid#' in string:
        return string.replace('#uuid#', uuid.uuid4().hex)
    else:
        return string


def mail_argument_configure():
    parser = argparse.ArgumentParser()
    parser.add_argument('smtp_address', action='store',
                        help='Host (ip-address) and port of mail server')
    parser.add_argument('--mail_from', action='store',
                        required=True,
                        help='E-mail address of sender')
    parser.add_argument('--rcpt_to', action='store', nargs='+', required=True,
                        help='People who e-mail address to')
    parser.add_argument('--tls', action='store_true',
                        help='Configuring TLS access')
    parser.add_argument('--user', action='store', default=None,
                        help='Name of user, who send e-mail')
    parser.add_argument('--pwd', action='store', default=None,
                        help='Password of sender')
    parser.add_argument('--headers', action='store', nargs='*', default=[],
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
    parser.add_argument('--stdout', action='store_true',
                        help='Configuring sending an e-mail and redirecting \
                        it to STDOUT')
    parser.add_argument('--attachment_path', action='store', nargs='*',
                        default=[], help='Path to attachments in the message')
    return parser


class AttachmentFileError(Exception):
    pass


class SendingMailError(Exception):
    pass


class SendingThreads(threading.Thread):

    def __init__(self, transport, message, index):
        super(SendingThreads, self).__init__()
        self.transport = transport
        self.message = message
        self.index = index

    def run(self):
        try:
            self.transport.connect_and_login()
            self.transport.send_mail(self.message, self.index)
            self.transport.disconnect()
        except Exception:
            log.error(u'Sending Mail Error is raised')
            raise SendingMailError("Message cannot be sent!")


class Email(object):

    def __init__(self, mail_from, rcpt_to, headers=None, data=None,
                 data_file=None, attachment_path=None):
        self.mail_from = mail_from
        self.rcpt_to = rcpt_to
        self.headers = headers
        self.data = data
        self.data_file = data_file
        self.attachment_path = attachment_path
        self._message = None

    @property
    def message(self):
        return self._message

    def _should_be_multipart(self):
        if len(self.attachment_path) == 1:
            if not self.data  and not self.data_file:
                return False
            else:
                return True
        elif self.data and self.data_file:
            return True
        elif len(self.attachment_path) > 1:
            return True
        else:
            return False

    def generate_message(self, index=1):
        if self._should_be_multipart():
            log.info(u'Create multipart message')
            return self.create_multipart_msg(index)
        else:
            log.info(u'Create singlepart message')
            return self.create_singlepart_msg(index)

    def create_singlepart_msg(self, index=1):
        if len(self.attachment_path) > 0:
            attachment = self.attachment_path[0]
            self._message = self.attach_files_to_message(attachment)

        if self.data_file:
            with open(self.data_file, 'rb') as fp:
                text = replace_id_in_string(fp.read(), index)
        else:
            text = replace_id_in_string(self.data, index)
        self._message = MIMEText(text)

        if self.headers:
            self.add_headers_to_msg(index=index)
        return self.message

    def create_multipart_msg(self, index=1):
        self._message = MIMEMultipart()
        if self.headers is not None:
            self.add_headers_to_msg(index=index)

        text = None
        if self.data and not self.data_file:
            text = replace_id_in_string(self.data, index)
        elif self.data_file and not self.data:
            if os.path.isfile(self.data_file):
                with open(self.data_file, 'rb') as fp:
                    text = replace_id_in_string(fp.read(), index)
            else:
                log.warning(u"Data file %s doesn't exists", self.data_file)
        elif self.data_file and self.data:
            text = replace_id_in_string(self.data, index)
            if os.path.isfile(self.data_file):
                self.attachment_path.append(self.data_file)
                print self.attachment_path
            else:
                log.warning(u"Data file %s doesn't exists", self.data_file)
                raise ValueError('Data file doesn\'t exists')
        if text:
            msg = MIMEText(text)
            self.message.attach(msg)

        for attachment in self.attachment_path:
            msg = self.attach_files_to_message(attachment)
            self.message.attach(msg)
        return self.message

    def add_headers_to_msg(self, index=1):
        self.message['From'] = self.mail_from
        self.message['To'] = ", ".join(self.rcpt_to)
        for header in self.headers:
            name, value = get_header_name_value(header)
            value = Header(replace_id_in_string(value, counter=index),
                           sys.stdin.encoding)
            self.message[name] = value
        return self.message

    def attach_files_to_message(self, attachment_file):
        if os.path.isfile(attachment_file):
            log.info(u'File %s is attaching to message', attachment_file)
            try:
                content_type, encoding = mimetypes.guess_type(attachment_file)
                maintype, subtype = content_type.split('/', 1)
                with open(attachment_file, 'rb') as fp:
                    msg = MIMEBase(maintype, subtype)
                    msg.set_payload(fp.read())
                    email.encoders.encode_base64(msg)
                    msg.add_header("Content-Disposition", 'attachment',
                                   filename=attachment_file)
            except Exception:
                log.error(u'Attachment File Error is raised')
                raise AttachmentFileError("The file cannot be attached. \
                                            Please try again!")
        else:
            log.warning(u'File %s is not found', attachment_file)
            raise ValueError('File is not found')
        return msg

    def message_generator(self, count=1):
        for i in xrange(1, count+1):
            msg = self.generate_message(index=i)
            yield msg.as_string()


class EmailTransport(object):

    def __init__(self, smtp_address, mail_from, rcpt_to, tls=False, user=None,
                 pwd=None):
        self.smtp_address = smtp_address
        self.mail_from = mail_from
        self.rcpt_to = rcpt_to
        self.tls = tls
        self.user = user
        self.pwd = pwd
        self.server = None

    def copy(self):
        return self.__class__(
            self.smtp_address, self.mail_from, self.rcpt_to,
            self.tls, self.user, self.pwd
        )

    def connect_and_login(self):
        self.server = SMTP(self.smtp_address)
        log.debug(u'Client is connected to server')
        self.server.ehlo()
        if self.tls:
            log.debug(u'TLS is started')
            self.server.starttls()
        if self.user is not None and self.pwd is not None:
            self.server.login(self.user, self.pwd)
            log.debug(u'Username and password are correct')
        return self.server

    def send_mail(self, msg, index=1):
        mail_from = replace_id_in_string(self.mail_from, index)
        rcpt_to = replace_id_in_string(self.rcpt_to, index)
        self.server.sendmail(mail_from, rcpt_to, msg)
        return self.server

    def disconnect(self):
        log.debug(u'Server disconnects')
        self.server.quit()


def send_messages(message_gen, transport, count=1, concurrency=1):
    if concurrency > 1:
        cycles, remains = divmod(count, concurrency)
        ind = 1
        for batch in chain(repeat(concurrency, cycles),
                           repeat(remains, 1 if remains else 0)):
            threads = [SendingThreads(transport.copy(), next(message_gen),
                                      ind+1)
                       for _ in range(batch)]

            ind += batch
            for thr in threads:
                thr.start()
            for thr in threads:
                thr.join()
    else:
        try:
            transport.connect_and_login()
            for ind, msg in enumerate(message_gen, 1):
                transport.send_mail(msg, ind)
            transport.disconnect()
        except Exception as err:
            log.critical(u'Sending Mail Error is raised')
            raise SendingMailError("Message cannot be sent! %s" % str(err))


def main():
    parser = mail_argument_configure()
    args = parser.parse_args()
    log.debug(u'Arguments: %s', args)

    if message_in_stdin():
        log.info(u'The message is being read from stdin')
        message_str = read_from_stdin()
        message_gen = repeat(message_str, args.count)
    else:
        message = Email(args.mail_from, args.rcpt_to, args.headers, args.data,
                        args.data_file, args.attachment_path)
        log.debug(u'Object message is created')
        message_gen = message.message_generator(args.count)

    if args.stdout:
        for index, msg in enumerate(message_gen, 1):
            log.info(u'The message #%d is sent to stdout', index)
            print msg
    else:
        log.info(u'The message is being sent to recipient %r', args.rcpt_to)
        smtp_server = EmailTransport(args.smtp_address, args.mail_from,
                                     args.rcpt_to, args.tls, args.user,
                                     args.pwd)
        send_messages(message_gen, smtp_server, args.count, args.concurrency)
        log.info(u'Your message has been sent successfully')


if __name__ == "__main__":
    main()


