from odoo import models, fields, api
import datetime
import paramiko, io, csv, logging
from odoo.exceptions import UserError

class BankStatementLogs(models.Model):
    _name = "bank.statement.log"
    _description = "Bank Statements"
    
    sequence = fields.Char(string="Sequence", default="new")
    file_name = fields.Char(string="File name")
    file_description = fields.Text(string="File Description")
    state = fields.Selection([('success', 'Success'), ('failed', 'Failed')], string="Status")
    create_date = fields.Datetime(string="Create Date", default=datetime.datetime.now())
    error_box = fields.Char(string="Error Message")
   
    @api.model      
    def create(self, vals):
        if vals.get('sequence', 'new') == 'new':
            vals['sequence'] = self.env['ir.sequence'].next_by_code('statement.sequence.file') or 'new'
        result = super(BankStatementLogs, self).create(vals)
        return result
    
    
    def sftp_connection(self):
        host = '178.156.207.111'
        port = 22
        username = 'fifththird_drop'
        password = '#8fn#*f4@fe&6b@648%'
        remote_path = 'incoming'
        destination_path = 'processed'

        transport = None
        sftp = None

        try:
            print("== =start= ==connect with sftp server -======")
            transport = paramiko.Transport((host, port))
            transport.connect(username=username, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            print("== =end= ==connect with sftp server -======")

            files = sftp.listdir(remote_path)

            print("====== = =file path ====", files)
            for filename in files:
                if not filename.endswith('.txt'):
                    continue

                file_path = f"{remote_path}/{filename}"
                dest_path = f"{destination_path}/{filename}"
                print("====== = =file path ====", file_path)
                print("====== = =file path ====", dest_path)

                
                with sftp.open(file_path, 'r') as file:
                    file_data = file.read().decode('utf-8')

               
                print("====== file_data====", file_data)

                sequence = self.env['ir.sequence'].with_context(ir_sequence_date=fields.Date.today()).next_by_code('statement.sequence.file')
                print("---- sequence--", sequence)
                
                self.env['bank.statement.log'].sudo().create({
                    'sequence': sequence,
                    'file_name': filename,
                    'file_description': file_data,
                    'state': 'success',
                })
                
                self.process_bai_content(file_data)
                
                # sftp.putfo(sftp.open(file_path, 'rb'), dest_path)
                # sftp.remove(file_path)
                # print("--- --fle transfer successfully----###")
                
                # with sftp.open(file_path, 'rb') as fl:
                #     sftp.putfo(fl, dest_path)
                #     print("--- -destination file---", dest_path)
                
                

        except Exception as e:
            raise UserError(("SFTP Error: %s") % str(e))

        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()
                
    
    @api.model
    def process_bai_content(self, file_data):

        current_file = None
        current_group = None
        current_account = None
        last_transaction = None
        current_group_date = None
        pending_account_name = None

        File = self.env['bai.bank.files'].sudo()
        Group = self.env['bai.bank.groups'].sudo()
        Account = self.env['bai.bank.accounts'].sudo()
        TransactionModel = self.env['bai.bank.account.transactions'].sudo()

        CREDIT_CODES = ['142','301','303','304','306','195','399']
        DEBIT_CODES  = ['451','475','495','575','401']

        for raw_line in file_data.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            if line.endswith('/'):
                line = line[:-1]

            parts = line.split(',')
            record_type = parts[0]

            # ---------------- FILE HEADER ----------------
            if record_type == "01":
                
                if len(parts) > 3 and parts[3]:
                    raw_date = parts[3]
                    print("--- -raw_date--", raw_date)
                    year = int('20' + raw_date[0:2])
                    month = int(raw_date[2:4])
                    day = int(raw_date[4:6])
                    current_group_date_1 = f"{year}-{month:02}-{day:02}"
                    print("-- -if- current_group_date--", current_group_date_1)
                else:
                    current_group_date = fields.Date.today()
                    print("--else -- current_group_date--", current_group_date_1)
                
                
                current_file = File.create({
                    'sender_identification': parts[1] if len(parts) > 1 else '',
                    'receiver_identification': parts[2] if len(parts) > 2 else '',
                    'file_creation_date': current_group_date_1 if current_group_date_1 else fields.Date.today(),
                })
                

            # ---------------- GROUP HEADER ----------------
            elif record_type == '02':
                bank_name = parts[1] if len(parts) > 1 else ''

                # -------- GET DATE FROM BAI (YYMMDD) --------
                if len(parts) > 4 and parts[4]:
                    raw_date = parts[4]
                    print("--- -raw_date--", raw_date)
                    year = int('20' + raw_date[0:2])
                    month = int(raw_date[2:4])
                    day = int(raw_date[4:6])
                    current_group_date = f"{year}-{month:02}-{day:02}"
                    print("-- -if- current_group_date--", current_group_date)
                else:
                    current_group_date = fields.Date.today()
                    print("--else -- current_group_date--", current_group_date)

                current_group = Group.search([
                    ('ultimate_receiver_identification', '=', bank_name)
                ], limit=1)

                if not current_group:
                    current_group = Group.create({
                        'ultimate_receiver_identification': bank_name,
                        'file_id': current_file.id if current_file else False,
                        'group_date': current_group_date if current_group_date else fields.Date.today(),
                    })

                current_account = None

            # ---------------- ACCOUNT HEADER ----------------
            elif record_type == '03' and current_group:
                account_number = parts[1] if len(parts) > 1 else ''

                current_account = Account.search([
                    ('account_number', '=', account_number)
                ], limit=1)

                if not current_account:
                    current_account = Account.create({
                        'account_number': account_number,
                        'group_id': current_group.id,
                        'account_name': pending_account_name if pending_account_name else '',
                    })
                else:
                # update name if we captured from 88
                    if pending_account_name:
                        current_account.account_name = pending_account_name

            # ---------------- TRANSACTION 16 ----------------
            elif record_type == '16' and current_account:

                type_code = parts[1] if len(parts) > 1 else ''
                raw_amount = parts[2] if len(parts) > 2 else '0'

                amount = float(raw_amount) / 100 if raw_amount else 0.0

                if type_code in CREDIT_CODES:
                    trx_type = 'credit'
                elif type_code in DEBIT_CODES:
                    trx_type = 'debit'
                else:
                    trx_type = 'debit'

                description = ''
                
                if pending_account_name:
                    description = f"{pending_account_name} - {description}"

                if len(parts) >= 7:
                    description = parts[6]

                existing = TransactionModel.search([
                    ('account_id', '=', current_account.id),
                    ('type_code', '=', type_code),
                    ('amount', '=', amount),
                    ('description', '=', description),
                    ('transaction_date', '=', current_group_date),
                ], limit=1)

                if existing:
                    last_transaction = existing
                    continue

                last_transaction = TransactionModel.create({
                    'account_id': current_account.id,
                    'type_code': type_code,
                    'amount': amount,
                    'transaction_type': trx_type,
                    'description': description,
                    'transaction_date': current_group_date,
                })

            # ---------------- DESCRIPTION CONTINUATION 88 ----------------
            elif record_type == '88' and last_transaction:
                extra_desc = ','.join(parts[1:]).strip()

                if extra_desc:
                    if last_transaction.description:
                        last_transaction.description += ' ' + extra_desc
                        pending_account_name = f"{pending_account_name} {extra_desc}" if pending_account_name else extra_desc
                    
                        if hasattr(current_account, 'account_name') and pending_account_name:
                            current_account.sudo().write({
                                'account_name': pending_account_name
                            })
                    else:
                        last_transaction.description = extra_desc
                        pending_account_name = extra_desc
                    
                        if hasattr(current_account, 'account_name') and pending_account_name:
                            current_account.sudo().write({
                                'account_name': pending_account_name
                            })
            # ---------------- ACCOUNT TRAILER ----------------
            elif record_type == '49':
                current_account = None
                last_transaction = None
                pending_account_name = None

            # ---------------- GROUP TRAILER ----------------
            elif record_type == '98':
                current_group = None

            print('-- - - - extra_desc----  --', pending_account_name)
        return True