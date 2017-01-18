import argparse
import re
import sys
import os.path
import os
from email.mime.text import MIMEText
import mimetypes
import email
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from smtplib import SMTP
import logging


def header_type(string):
    pattern = re.compile("(?P<header_name>\w+-?\w+)=(?P<header_value>[\w ]+)")
    match = pattern.match(string)
    if not match:
        msg = "%r is not an appropriate header type (name=value)" % string
        raise argparse.ArgumentTypeError(msg)
    return string


def defining_subject(headers):
    header_subject = None
    for i in headers:
        if i.startswith("Subject"):
            header_subject = i
        else:
            continue
    subject = header_subject.split("=")[-1]
    log.info('Subject is defined: %s', subject)
    return subject


def separating_header_name_and_value(header):
    header_name, header_value = header.split("=")
    log.info('Defined: header: %s, header value: %s', header_name, header_value)
    return header_name, header_value


def mail_argument_configuration():
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
                        help='Configuring sending an e-mail and redirecting \
                        it to STDOUT')
    parser.add_argument('--attachment_path', action='store', nargs='*',
                        default=[], help='Path to attachments in the message')
    return parser


class AttachmentFileError(Exception):
    pass


class SendingMailError(Exception):
    pass


class EmailCreationAndSending(object):

    def __init__(self, smtp_address, mail_from, rcpt_to, tls=False, user=None,
                 pwd=None, header=None, data=None, data_file=None, count=1,
                 concurrency=1, send_stdout=False, attachment_path=None):
        self.smtp_address = smtp_address
        self.tls = tls
        self.user = user
        self.pwd = pwd
        self.mail_from = mail_from
        self.header = header
        self.data = data
        self.data_file = data_file
        self.count = count
        self.concurrency = concurrency
        self.send_stdout = send_stdout
        self.attachment_path = attachment_path
        self.rcpt_to = rcpt_to
        self.message = None
        self.subject = None

    def reading_from_stdin(self):
        email_file = sys.stdin
        self.message = email_file.read()
        return self.message

    def message_creation(self):
        if len(self.attachment_path) == 1:
            if self.data is None and self.data_file is None:
                log.info(u'Creating singlepart message with one attachment \
                          and no data is started')
                return self.creating_singlepart_msg()
            else:
                log.info(u'Creating multipart message with one attachment \
                          and data is started')
                return self.creating_multipart_msg()
        elif len(self.attachment_path) > 1:
            log.info(u'Creating multipart message is started')
            return self.creating_multipart_msg()
        else:
            log.info(u'Creating simple singlepart message is started')
            return self.creating_singlepart_msg()

    def creating_singlepart_msg(self):
        self.subject = defining_subject(self.header)
        if len(self.attachment_path) > 0:
            self.message = MIMEMultipart()
            self.message['Subject'] = self.subject
            self.message['From'] = self.user
            self.message['To'] = ", ".join(self.rcpt_to)
            if len(self.header) > 0:
                for header in self.header:
                    header, value = separating_header_name_and_value(header)
                    self.message[header] = value
            if os.path.isfile(self.attachment_path[0]):
                self.attaching_files_to_message(self.attachment_path[0])
            return self.message

        if self.data_file is not None:
            with open(self.data_file, 'rb') as fp:
                self.message = MIMEText(fp.read())
        elif self.data is not None:
            self.message = MIMEText(self.data)
        self.message['Subject'] = self.subject
        self.message['From'] = self.user
        self.message['To'] = ", ".join(self.rcpt_to)
        return self.message

    def creating_multipart_msg(self):
        self.subject = defining_subject(self.header)
        self.message = MIMEMultipart()
        self.message['Subject'] = self.subject
        self.message['From'] = self.user
        self.message['To'] = ", ".join(self.rcpt_to)
        if len(self.header) > 0:
            for header in self.header:
                header, value = separating_header_name_and_value(header)
                self.message[header] = value

        if self.data_file is not None:
            with open(self.data_file, 'rb') as fp:
                text = fp.read()
                msg = MIMEText(text)
                self.message.attach(msg)
        elif self.data is not None:
            msg = MIMEText(self.data)
            self.message.attach(msg)

        for attachment in self.attachment_path:
            if not os.path.isfile(attachment):
                continue
            self.attaching_files_to_message(attachment)
        return self.message

    def attaching_files_to_message(self, attachment_file):
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

    def send_mail(self):
        server = SMTP(self.smtp_address)
        log.info(u'Client is connected to server')
        server.ehlo()
        if self.tls:
            server.starttls()
        server.login(self.mail_from, self.pwd)
        log.info(u'Username and password are correct')
        try:
            server.sendmail(self.mail_from, self.rcpt_to,
                            self.message.as_string())
            log.info(u'Your message was successfully send! Congratulations!!!')
        except Exception:
            log.error(u'Sending Mail Error is raised')
            raise SendingMailError("Message cannot be sent!")
        finally:
            server.quit()


def main():
    parser = mail_argument_configuration()
    args = parser.parse_args()
    log.info('%s', args)
    mail = EmailCreationAndSending(args.smtp_address, args.mail_from,
                                   args.rcpt_to, args.tls, args.user, args.pwd,
                                   args.header, args.data, args.data_file,
                                   args.count, args.concurrency,
                                   args.send_stdout, args.attachment_path)
    if not sys.stdin.isatty():
        log.info(u'The message is being read from stdin')
        mail.reading_from_stdin()
    else:
        log.info(u'The message is being created')
        mail.message_creation()
    if args.send_stdout:
        log.info(u'The message is being sent to stdout')
        message = mail.message_creation()
        print message
    else:
        log.info(u'The message is being sent to recipient')
        mail.send_mail()


if __name__ == "__main__":
    FORMAT = u'%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT, filename=u'email.log',
                        level=logging.DEBUG)
    log = logging.getLogger(__name__)
    main()

