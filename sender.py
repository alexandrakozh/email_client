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
    mail = sys.stdin
    message = mail.read()
    return message


def message_in_stdin():
    return (
        not sys.stdin.isatty()
        and sys.stdin in select.select([sys.stdin], [], [], 0)[0]
    )


def replacing_id_in_message(message, count):
    if '#id#' in message:
        msg = message.replace('#id#', str(count))
    elif '#uuid#' in message:
        msg = message.replace('#uuid#', uuid.uuid4().hex)
    else:
        msg = message
    return msg


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


class ThreadForSending(threading.Thread):

    def __init__(self, message, smtp_address, tls, mail_from, pwd, rcpt_to):
        threading.Thread.__init__(self)
        self.message = message
        self.smtp_address = smtp_address
        self.tls = tls
        self.mail_from = mail_from
        self.pwd = pwd
        self.rcpt_to = rcpt_to

    def run(self):
        server = SMTP(self.smtp_address)
        server.ehlo()
        if self.tls:
            server.starttls()
        server.login(self.mail_from, self.pwd)
        server.sendmail(self.mail_from, self.rcpt_to, self.message)
        server.quit()


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
        self._subject = None

    @property
    def message(self):
        return self._message

    def generate_message(self, index=1):
        if len(self.attachment_path) == 1:
            if self.data is None and self.data_file is None:
                log.info(u'Creating singlepart message with one attachment \
                          and no data')
                return self.create_singlepart_msg(index)
            else:
                log.info(u'Creating multipart message with one attachment \
                          and data')
                return self.create_multipart_msg(index)
        elif len(self.attachment_path) > 1:
            log.info(u'Creating multipart message')
            return self.create_multipart_msg(index)
        else:
            log.info(u'Creating simple singlepart message')
            return self.create_singlepart_msg(index)

    def create_singlepart_msg(self, index=1):
        if len(self.attachment_path) > 0:
            attachment = self.attachment_path[0]
            with open(attachment, 'rb') as f:
                content_type, encoding = mimetypes.guess_type(f)
                maintype, subtype = content_type.split('/', 1)
                msg = MIMEBase(maintype, subtype)
                msg.set_payload(f.read())
            email.encoders.encode_base64(msg)
            msg.add_header("Content-Disposition", 'attachment',
                           filename=attachment)
            if self.headers is not None:
                self.add_headers_to_msg(index=index)

            if os.path.isfile(attachment):
                log.info(u'File %s is attaching to message',
                         attachment)
                self.attach_files_to_message(attachment)
            return self.message

        if self.data_file is not None:
            with open(self.data_file, 'rb') as fp:
                text = replacing_id_in_message(fp.read(), count=index)
                self._message = MIMEText(text)
        elif self.data is not None:
            text = replacing_id_in_message(self.data, count=index)
            self._message = MIMEText(text)
        if self.headers is not None:
            self.add_headers_to_msg(index=index)
        return self.message

    def create_multipart_msg(self, index=1):
        self._message = MIMEMultipart()
        if self.headers is not None:
            self.add_headers_to_msg(index=index)

        if self.data_file is not None and self.data is not None:
            if os.path.isfile(self.data_file):
                self.attachment_path.append(self.data_file)
            else:
                log.info(u"Data file %s doesn't exists", self.data_file)
        elif self.data_file is not None and self.data is None:
            if os.path.isfile(self.data_file):
                with open(self.data_file, 'rb') as fp:
                    text = replacing_id_in_message(fp.read(), count=index)
                    msg = MIMEText(text)
                    self.message.attach(msg)
            else:
                log.info(u"Data file %s doesn't exists", self.data_file)
        elif self.data is not None and self.data_file is None:
            text = replacing_id_in_message(self.data, count=index)
            msg = MIMEText(text)
            self.message.attach(msg)

        for attachment in self.attachment_path:
            if not os.path.isfile(attachment):
                log.warning(u'File %s is not found', attachment)
                continue
            self.attach_files_to_message(attachment)
        return self.message

    def add_headers_to_msg(self, index=1):
        self.message['From'] = self.mail_from
        self.message['To'] = ", ".join(self.rcpt_to)
        if self.headers is not None:
            for header in self.headers:
                name, value = get_header_name_value(header)
                value = Header(replacing_id_in_message(value, count=index),
                               sys.stdin.encoding)
                self.message[name] = value
        return self.message

    def attach_files_to_message(self, attachment_file):
        try:
            content_type, encoding = mimetypes.guess_type(attachment_file)
            maintype, subtype = content_type.split('/', 1)
            with open(attachment_file, 'rb') as fp:
                msg = MIMEBase(maintype, subtype)
                msg.set_payload(fp.read())
                msg.add_header("Content-Disposition", 'attachment',
                               filename=attachment_file)
            self.message.attach(msg)
        except Exception:
            log.error(u'Attachment File Error is raised')
            raise AttachmentFileError("The file cannot be attached. \
                                        Please try again!")
        return self.message

    def generate_messages(self, count=1):
        counter = 1
        while counter <= count:
            msg = self.generate_message(index=counter)
            yield msg.as_string()
            counter += 1


class EmailTransport(object):

    def __init__(self, smtp_address, mail_from, rcpt_to, tls=False, user=None,
                 pwd=None, count=1, concurrency=1):
        self.smtp_address = smtp_address
        self.mail_from = mail_from
        self.rcpt_to = rcpt_to
        self.tls = tls
        self.user = user
        self.pwd = pwd
        self.count = count
        self.concurrency = concurrency
        self.server = None

    def server_connect_and_login(self):
        self.server = SMTP(self.smtp_address)
        log.info(u'Client is connected to server')
        self.server.ehlo()
        if self.tls:
            log.info(u'TLS is started')
            self.server.starttls()
        if self.user is not None and self.pwd is not None:
            self.server.login(self.user, self.pwd)
            log.info(u'Username and password are correct')
        return self.server

    def send_mail(self, msg):
        self.server.sendmail(self.mail_from, self.rcpt_to, msg)
        return self.server

    def create_threads(self, count, message_generator):
        threads = []
        for _ in range(count):
            t = ThreadForSending(message_generator.next(), self.smtp_address,
                                 self.tls,self.mail_from, self.pwd,
                                 self.rcpt_to)
            log.info(u'Thread is created')
            threads.append(t)
        for i in range(len(threads)):
            threads[i].start()
        for j in range(len(threads)):
            threads[j].join()

    def send_multiple_messages(self, message_generator):
        try:
            if self.concurrency > 1:
                n = self.count // self.concurrency
                message_remain = self.count % self.concurrency
                for _ in range(n):
                    self.create_threads(self.concurrency,
                                        message_generator)
                self.create_threads(message_remain, message_generator)

            elif self.concurrency == 1:
                i = 0
                while i < self.count:
                    for msg in message_generator:
                        self.send_mail(msg)
                self.server_connect_and_login()
            log.info(u'Mail is sent')
        except Exception:
            log.error(u'Sending Mail Error is raised')
            raise SendingMailError("Message cannot be sent!")

    def server_disconnect(self):
        log.info(u'Server disconnects')
        self.server.quit()


def main():
    parser = mail_argument_configure()
    args = parser.parse_args()
    log.info(u'Arguments: %s', args)

    if message_in_stdin():
        log.info(u'The message is being read from stdin')
        message = read_from_stdin()
        if not args.stdout:
            transport = EmailTransport(args.smtp_address, args.mail_from,
                                       args.rcpt_to, args.tls, args.user,
                                       args.pwd, args.count,
                                       args.concurrency)
            transport.server_connect_and_login()
            for i in range(args.count):
                transport.send_mail(message)
            transport.server_disconnect()
        else:
            print message
    else:
        message = Email(args.mail_from, args.rcpt_to, args.headers, args.data,
                        args.data_file, args.attachment_path)
        log.info(u'Object message is created')
        messages = message.generate_messages(args.count)
        if args.stdout:
            for msg in messages:
                log.info(u'The message is sent to stdout')
                print msg
        else:
            log.info(u'The message is  sent to recipient')
            transport = EmailTransport(args.smtp_address, args.mail_from,
                                       args.rcpt_to, args.tls, args.user,
                                       args.pwd, args.count,
                                       args.concurrency)
            if args.count == 1:
                transport.server_connect_and_login()
                message = message.generate_message().as_string()
                transport.send_mail(message)
                transport.server_disconnect()
                log.info(u'Your message was sent')
            else:
                transport.send_multiple_messages(messages)


if __name__ == "__main__":
    main()


