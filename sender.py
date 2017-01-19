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


def header_type(string):
    pattern = re.compile("(?P<header_name>\w+-?\w+)=(?P<header_value>[\w ]+)")
    match = pattern.match(string)
    if not match:
        msg = "%r is not an appropriate header type (name=value)" % string
        raise argparse.ArgumentTypeError(msg)
    return string


def get_subject(headers):
    header_subject = None
    for i in headers:
        if i.lower().startswith("subject"):
            header_subject = i
            break
    subject = header_subject.split("=")[-1]
    return subject


def handling_header(header):
    header_name, header_value = header.split("=")
    header_value = Header(header_value, sys.stdin.encoding)
    return header_name, header_value


def read_from_stdin():
    mail = sys.stdin
    message = mail.read()
    return message


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


class EmailCreation(object):

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

    @property
    def subject(self):
        return self._subject

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
        self._subject = get_subject(self.headers)
        log.info('Subject: %s', self.subject)
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
        self.add_headers_to_msg()
        return self.message

    def create_multipart_msg(self):
        self._subject = get_subject(self.headers)
        log.info('Subject: %s', self.subject)
        self._message = MIMEMultipart()
        self.add_headers_to_msg()

        if self.data_file is not None and self.data is not None:
            self.attachment_path.append(self.data_file)
        elif self.data_file is not None and self.data is None:
            with open(self.data_file, 'rb') as fp:
                text = fp.read()
                msg = MIMEText(text)
                self.message.attach(msg)
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
        if len(self.headers) > 0:
            for header in self.headers:
                header, value = handling_header(header)
                log.info('Header: %s, header-value: %s', header, value)
                self.message[header] = value
        return self.message

    def attach_files_to_message(self, attachment_file):
        try:
            content_type, encoding = mimetypes.guess_type(attachment_file)
            maintype, subtype = content_type.split('/', 1)
            with open(attachment_file, 'rb') as fp:
                msg = MIMEBase(maintype, subtype)
                msg.set_payload(fp.read())
                email.encoders.encode_base64(msg)
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

    def send_mail(self, message):
        try:
            self.server.sendmail(self.mail_from, self.rcpt_to,
                                 message.as_string())
            log.info(u'Your message was successfully send!')
        except Exception:
            log.error(u'Sending Mail Error is raised')
            raise SendingMailError("Message cannot be sent!")
        return self.server

    def server_disconnect(self):
        log.info(u'Server is disconnecting')
        self.server.quit()


def main():
    parser = mail_argument_configure()
    args = parser.parse_args()
    log.info('Arguments: %s', args)
    message = EmailCreation(args.mail_from, args.rcpt_to, args.user,
                            args.headers, args.data, args.data_file,
                            args.attachment_path)

    if not sys.stdin.isatty():
        log.info(u'The message is being read from stdin')
        message = read_from_stdin()
    else:
        log.info(u'The message is being created')
        message = message.generate_message()

    if args.stdout:
        log.info(u'The message is being sent to stdout')
        print message
    else:
        log.info(u'The message is being sent to recipient')
        mail = EmailTransport(args.smtp_address, args.mail_from, args.rcpt_to,
                              args.tls, args.user, args.pwd, args.count,
                              args.concurrency)
        mail.server_connect_and_login()
        mail.send_mail(message)
        mail.server_disconnect()

if __name__ == "__main__":
    FORMAT = u'%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT, filename=u'email.log',
                        level=logging.DEBUG)
    log = logging.getLogger(__name__)
    main()
