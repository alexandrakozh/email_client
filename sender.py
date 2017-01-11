import argparse
import smtplib

def mail_agrument_configuring():
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


class EmailClient(object):

    def __init__(self, smtp_address, mail_from, rcpt_to, tls=False, 
                user=None, pwd=None,  header=None, data=None,data_file=None, count=1,
                concurrency=1,send_stdout=False, attachment_path=None):
        self.smtp_address = smtp_address
        self.mail_from = mail_from
        self.rcpt_to = rcpt_to
        self.tls = tls
        self.user = user
        self.pwd = pwd
        self.header = header
        self.data = data
        self.data_file = data_file
        self.count = count
        self.concurrency = concurrency
        self.send_stdout = send_stdout
        self.attachment_path = attachment_path
        self.message = None

    def send_mail(self):
        self.message = "From: %s\r\n To: %s\r\n Subject: %s\r\n\r\n" % (self.mail_from, ", ".join(self.rcpt_to), self.header)
        server = SMTP(self.smtp_address)
        server.ehlo()
        if self.tls:
            server.starttls()
        server.login(self.user, self.pwd)

        try:
            server.sendmail(self.mail_from, self.rcpt_to, self.message)
            print 'Your message was successfully send! Congratulations!!!'
        except Exception:
            raise SendingMailError('Unable to send an e-mail. Please try again!!')
        finally:
            server.quit()


if __name__ == "__main__":
    args = mail_agrument_parsing_and_configuring()
    args.parse_args()
    mail = EmailClient(args.smtp_adress, args.mail_from, args.rcpt_to, args.tls, 
                        args.user, args.pwd, args.header, args.data, args.data_file, 
                        args.count, args.concurrency, args.send_stdout, args.attachment_path
                        )

