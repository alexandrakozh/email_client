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


def handling_header(header):
    header_name, header_value = header.split("=")
    # header_value = Header(header_value, sys.stdin.encoding)
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


def repeat(message, count):
    i = 0
    while i < count:
        i += 1
        yield message


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

    def __init__(self, message, server, mail_from, rcpt_to, count=None):
        threading.Thread.__init__(self)
        self.message = message
        self.server = server
        self.mail_from = mail_from
        self.rcpt_to = rcpt_to
        self.count = count

    def run(self):
        msg = replacing_id_in_message(self.message, self.count)
        self.server.sendmail(self.mail_from, self.rcpt_to, msg)
        return self.server


class Email(object):

    def __init__(self, mail_from, rcpt_to, user=None, headers=None, data=None,
                 data_file=None, attachment_path=None):
        self.mail_from = mail_from
        self.rcpt_to = rcpt_to
        self.user = user
        self.headers = headers
        self.data = data
        self.data_file = data_file
        self.attachment_path = attachment_path
        self._message = None
        self._subject = None

    @property
    def message(self):
        return self._message

    def generate_message(self):
        if len(self.attachment_path) == 1:
            if self.data is None and self.data_file is None:
                log.info(u'Creating singlepart message with one attachment \
                          and no data')
                return self.create_singlepart_msg()
            else:
                log.info(u'Creating multipart message with one attachment \
                          and data')
                return self.create_multipart_msg()
        elif len(self.attachment_path) > 1:
            log.info(u'Creating multipart message')
            return self.create_multipart_msg()
        else:
            log.info(u'Creating simple singlepart message')
            return self.create_singlepart_msg()

    def create_singlepart_msg(self):
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
                self.add_headers_to_msg()

            if os.path.isfile(attachment):
                log.info(u'File %s is attaching to message',
                         attachment)
                self.attach_files_to_message(attachment)
            return self.message

        if self.data_file is not None:
            with open(self.data_file, 'rb') as fp:
                self._message = MIMEText(fp.read())
        elif self.data is not None:
            self._message = MIMEText(self.data)
        if self.headers is not None:
            self.add_headers_to_msg()
        return self.message

    def create_multipart_msg(self):
        self._message = MIMEMultipart()
        if self.headers is not None:
            self.add_headers_to_msg()

        if self.data_file is not None and self.data is not None:
            if os.path.isfile(self.data_file):
                self.attachment_path.append(self.data_file)
            else:
                log.info(u"Data file %s doesn't exists", self.data_file)
        elif self.data_file is not None and self.data is None:
            if os.path.isfile(self.data_file):
                with open(self.data_file, 'rb') as fp:
                    text = fp.read()
                    msg = MIMEText(text)
                    self.message.attach(msg)
            else:
                log.info(u"Data file %s doesn't exists", self.data_file)
        elif self.data is not None and self.data_file is None:
            msg = MIMEText(self.data)
            self.message.attach(msg)

        for attachment in self.attachment_path:
            if not os.path.isfile(attachment):
                log.warning(u'File %s is not found', attachment)
                continue
            self.attach_files_to_message(attachment)
        return self.message

    def add_headers_to_msg(self):
        self.message['From'] = self.user
        self.message['To'] = ", ".join(self.rcpt_to)
        if self.headers is not None:
            for header in self.headers:
                header, value = handling_header(header)
                # log.info('Header: %s, header-value: %s', header, value)
                self.message[header] = value
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
        self.server.login(self.mail_from, self.pwd)
        log.info(u'Username and password are correct')
        return self.server

    def send_mail(self, msg):
        self.server.sendmail(self.mail_from, self.rcpt_to, msg)
        return self.server

    def send_multiple_messages(self, message):
        try:
            if self.count > 1:
                if self.concurrency > 1:
                    print 'concurrency many'
                    n = self.count // self.concurrency
                    for _ in range(n):
                        message.as_string()
                        count = 1
                        threads = []
                        for k in range(self.concurrency):
                            t = ThreadForSending(message, self.server,
                                                 self.mail_from, self.rcpt_to,
                                                 count)
                            print 'thread is added'
                            threads.append(t)
                            count += 1

                        for i in range(len(threads)):
                            threads[i].start()
                            print 'thread is started'
                        for j in range(len(threads)):
                            print 'thread join'
                            threads[j].join()
                else:
                    print 'concurrency one'
                    messages = repeat(message, self.count)
                    count = 1
                    for msg in messages:
                        msg = msg.as_string()
                        msg = replacing_id_in_message(msg, count)
                        self.send_mail(msg)
                        count += 1

            else:
                print 'count 1'
                msg = message.as_string()
                msg = replacing_id_in_message(msg, count=1)
                self.send_mail(msg)
            log.info(u'Mail is sent')
        except Exception:
            log.error(u'Sending Mail Error is raised')
            raise SendingMailError("Message cannot be sent!")
        finally:
            return self.server

    def server_disconnect(self):
        log.info(u'Server disconnects')
        self.server.quit()


def main():
    parser = mail_argument_configure()
    args = parser.parse_args()
    log.info('Arguments: %s', args)

    if message_in_stdin():
        log.info(u'The message is being read from stdin')
        message = read_from_stdin()
    else:
        message = Email(args.mail_from, args.rcpt_to, args.user,
                        args.headers, args.data, args.data_file,
                        args.attachment_path)
        message = message.generate_message()
        log.info(u'The message is being created')

    if args.stdout:
        msg = message.as_string()
        msg = replacing_id_in_message(msg, count=1)
        log.info(u'The message is being sent to stdout')
        print msg
    else:
        log.info(u'The message is being sent to recipient')
        mail = EmailTransport(args.smtp_address, args.mail_from, args.rcpt_to,
                              args.tls, args.user, args.pwd, args.count,
                              args.concurrency)
        mail.server_connect_and_login()
        mail.send_multiple_messages(message)
        mail.server_disconnect()


if __name__ == "__main__":
    main()


