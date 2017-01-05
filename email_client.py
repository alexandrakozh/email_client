from smtplib import SMTP
import os.path
import os
from email.mime.text import MIMEText
import mimetypes
import email
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import argparse


class SendingMailError(Exception):
    pass


class AttachmentFileError(Exception):
    pass


class EmailClient(object):
    """Class that is able to sent e-mails according to specified arguments

    .. example:
        $ ./email_client.py smtp_gmail.com:587 --tls True --user Alexandra Kozhemiakina --pwd 123
         --mail_from sasha@gmail.com --header "Message is sent!"
         --data_file /tmp/mail.txt --count 2 --concurrency 2 --attachment_path '/tmp/image.jpg, /tmp/code.py'
         --rcpt-to artem@gmail.com, ss@gmail.com

    :param: str smtp_adress: host(or id) and port of mail server, required argument
    :param: boolean tls: if is True - start TLS connection, default - False
    :param: str user: name of user, that sends e-mail message
    :param: str pwd: user's password to enter his mail for sending letter
    :param: str mail_from: e-mail_address of user who sends email
    :param: str header: subject of the letter
    :param: str data: the body of the message, can be read from path to data file, if it is specified
    :param: str data_file: path to file, that contain text, that will be used as body of the message
    :param: int count: a number of copies to send
    :param: int concurrency: a number of simultaneous copies to send
    :param: boolean send_stdout: if is True - redirect message to STDOUT
    :param: str attachment_path: a list of attachments for creating MIME Multipart message
    :param: str rcpt_to: a list of receivers, who the letter is addressed to

    :rtype: string
    :return: Message with the result of sending the letter
    :raises: SendingMailError
    """

    # TODO: add **kwargs for header
    # TODO: add count and concurrency
    # TODO: redirect to STDOUT
    # TODO: send_stdout

    def __init__(self, smtp_address, tls=False, user=None, pwd=None, mail_from=None, header=None, data=None,
                 data_file=None, count=1, concurrency=1, send_stdout=False, *attachment_path, *rcpt_to):
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

    def message_type_choose(self):
        """Method which chooses the type of e-mail and sends message according to its type (singlepart or multipart).
        Creating multipart message method  will be called if there is more than ona attachment.
        Creating singlepart message method will be called in two cases: there is one attachment, but no data, or just
        data

        :rtype: string
        :return: Message with the result of sending the letter
        """

        if len(self.attachment_path) > 1:
            return self.creating_multipart_msg()
        elif len(self.attachment_path) == 1 and self.data is None:
            return self.creating_singlepart_msg()
        else:
            return self.creating_singlepart_msg()

    def attaching_files_to_message(self, attachment_file):
        """Method which checks for mimetype and encoding of file, encode, add header and attach this file to the letter.
        This method is used in creating singlepart message method and creating multipart message method. If file cannot
        be attached - raises AttachmentFileError

        :param: str attachment_file: file, that will be attached to the message
        :rtype: string
        :return: Message with the result of sending the letter
        :raises: AttachmentFileError
        """

        try:
            content_type, encoding = mimetypes.guess_type(attachment_file)
            maintype, subtype = content_type.split('/', 1)
            fp = open(attachment_file, 'rb')
            if maintype == "text":
                msg = MIMEText(fp.read(), _subtype=subtype)
            elif maintype == "image":
                msg = MIMEImage(fp.read(), _subtype=subtype)
            elif maintype == "audio":
                msg = MIMEAudio(fp.read(), _subtype=subtype)
            else:
                msg = MIMEBase(maintype, subtype)
                msg.set_payload(fp.read())
            fp.close()
            email.encoders.encode_base64(msg)
            msg.add_header("Content-Disposition", 'attachment', filename=attachment_file)
            self.message.attach(msg)
        except Exception:
            raise AttachmentFileError("The file cannot be attached. Please try again!")

    def creating_singlepart_msg(self):
        """Method forms a singlepart message.  If there is no data but one attachment, it attach it to the message
         If there is a path with data, it opens it, read and save as body of the message,
         otherwise it use data from argument given by user.

        :rtype: string
        :return: Message with the result of sending the letter
        :raises: AttachmentFileError
        """

        if len(self.attachment_path) != 0 and os.path.isfile(self.attachment_path[0]):
            self.message = MIMEMultipart()
            self.message['Subject'] = self.header
            self.message['From'] = self.mail_from
            self.message['To'] = ", ".join(self.rcpt_to)
            attachment = str(self.attachment_path)
            self.attaching_files_to_message(attachment)
            return self.send_mail()

        if self.data_file is not None:
            fp = open(self.data_file, 'rb')
            text = fp.read()
            fp.close()
        else:
            text = self.data.as_string()

        self.message = MIMEText(text)
        self.message['Subject'] = self.header
        self.message['From'] = self.mail_from
        self.message['To'] = ", ".join(self.rcpt_to)
        return self.send_mail()

    def creating_multipart_msg(self):
        """Method which sends e-mail with more than one attachment. Loop through the list of attachments and use
        attaching_files_to_message method to form MiME Multipart message

        :rtype: string
        :return: Message with the result of sending the letter
        :raises: AttachmentFileError
        """

        self.message = MIMEMultipart()
        self.message['Subject'] = self.header
        self.message['From'] = self.mail_from
        self.message['To'] = ", ".join(self.rcpt_to)

        for attachment in self.attachment_path:
            if not os.path.isfile(attachment):
                continue
            self.attaching_files_to_message(attachment)
        return self.send_mail()

    def send_mail(self, message_from_stdin=None):
        """Method which sends mail using SMTP server or accept e-mail from STDIN and sends it without modification

        :param: str message_from_stdin: completed message file that can be given and sent without modification
        :rtype: string
        :return: Message with the result of sending the letter
        :raises: SendingMailError
        """

        if message_from_stdin is not None:
            message = message_from_stdin.as_string()
        else:
            message = self.message.as_string()

        server = SMTP(self.smtp_address)
        server.ehlo()
        if self.tls:
            server.starttls()
        server.login(self.user, self.pwd)

        try:
            server.sendmail(self.mail_from, self.rcpt_to, message)
            print 'Your message was successfully send! Congratulations!!!'
        except Exception:
            raise SendingMailError('Unable to send an e-mail. Please try again!!')
        finally:
            server.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('smtp_adress', action='store', help='Tuple, which include host and port of mail server')
    parser.add_argument('--tls', action='store', default=False, choices=[True, False],
                        help='Configuring TLS access')
    parser.add_argument('--user', action='store', help='Name of user, who send e-mail')
    parser.add_argument('--pwd', action='store', help='Password of sender')
    parser.add_argument('--mail_from', action='store',  help='E-mail adress of sender')
    parser.add_argument('--rcpt_to', action='store', nargs='*', default=[],
                        help='People who e-mail adress to')
    parser.add_argument('--header', action='store', nargs='*', default=[],
                        help='Headers of the message')
    parser.add_argument('--data', action='store',
                        help='Text, which message will contain')
    parser.add_argument('--data_file', action='store',
                        help='A path to e-mail script')
    parser.add_argument('--count', action='store', default=1, type=int,
                        help='A number of copies to send')
    parser.add_argument('--concurrency', action='store', default=1, type=int,
                        help='A number of simultaneous send')
    parser.add_argument('--send_stdout', action='store', default=False, choices=[True, False],
                        help='Configuring sending an e-mail and redirecting it to STDOUT')
    parser.add_argument('--attachment_path', action='store', nargs='*', default=[],
                        help='A path to attachments in the message')
    args = parser.parse_args()

    mail = EmailClient(args.smtp_adress, args.tls, args.user, args.pwd, args.mail_from, args.header, args.data,
                       args.data_file, args.count, args.concurrency, args.send_stdout, args.attachment_path,
                       args.rcpt_to)
    mail.message_type_choose()