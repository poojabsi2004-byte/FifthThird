from odoo import models, fields, api
import datetime, base64
import paramiko, io, csv, logging
from odoo.exceptions import UserError, ValidationError

class BankStatementLogs(models.Model):
    _name = "bank.statement.log"
    _description = "Bank Statements"
    
    sequence = fields.Char(string="Sequence", default="new")
    file_name = fields.Char(string="File name")
    file_description = fields.Text(string="File Description")
    state = fields.Selection([('success', 'Success'), ('failed', 'Failed')], string="Status")
    create_date = fields.Datetime(string="Create Date", default=datetime.datetime.now())
    error_box = fields.Char(string="Error Message")
   
    file_data = fields.Binary("File")
    
    @api.model      
    def create(self, vals):
        if vals.get('sequence', 'new') == 'new':
            vals['sequence'] = self.env['ir.sequence'].next_by_code('statement.sequence.file') or 'new'
        result = super(BankStatementLogs, self).create(vals)
        return result
    
    @api.model
    def sftp_connection(self):
        
        username = self.env['ir.config_parameter'].sudo().get_param('bsi_bank_connection.sftp_username')
        password = self.env['ir.config_parameter'].sudo().get_param('bsi_bank_connection.sftp_password')
        
        print("------ sftp connection details ----- username---", username)
        print("------ sftp connection details ----- password---", password)
        
        if not username and password:
            raise ValidationError("SFTP account credentials could not be fetched.")
        
        host = '178.156.207.111'
        # host = '192.168.29.20'
        port = 22
        username = username
        password = password
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
            existing_files = self.env['bank.statement.log'].sudo().search([]).mapped('file_name')

            print("====== = =file path ====", files)
            for filename in files:
                if not filename.endswith('.txt'):
                    continue
                
                if filename in existing_files:
                    print(f"====== Skipping already processed file: {filename} ======")
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
                
                with sftp.open(file_path, 'rb') as file:
                    raw_data = file.read()
                    file_text = raw_data.decode('utf-8', errors='ignore')
                
                self.env['bank.statement.log'].sudo().create({
                    'sequence': sequence,
                    'file_name': filename,
                    'file_description': file_data,
                    'file_data': base64.b64encode(raw_data),
                    'state': 'success',
                })
                
                self.process_bai_content(file_data)
                print("=== =process_bai_content(file_data)=== ",file_data)
                
                # sftp.rename(file_path, dest_path)
                # print("--- file moved successfully ---")
                
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
        
        # sftp_connection = self.sftp_connection()
         
        # if sftp_connection:
        #     print("---SFTP Server Connection---")
        #     continue
        # else:
        #     raise ValidationError("SFTP connetion Failed")
        
        current_file = None
        current_group = None
        current_account = None
        last_transaction = None
        current_group_date = None
        current_file_datetime = None
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

            if record_type == "01":
                
                if len(parts) > 3 and parts[3]:
                    raw_datetime = f"{parts[3]}{parts[4]}"
                    print("--- -raw_date--", raw_datetime)
                    dt = datetime.datetime.strptime(raw_datetime, "%y%m%d%H%M%S")
                    current_file_datetime = dt

                    print("-if- current_file_datetime --", current_file_datetime)
                else:
                    current_file_datetime = fields.Date.today()
                    print("--else -- current_group_date--", current_file_datetime)
                
                
                print("-print if- current_file_datetime --", current_file_datetime)
                current_file = File.create({
                    'sender_identification': parts[1] if len(parts) > 1 else '',
                    'receiver_identification': parts[2] if len(parts) > 2 else '',
                    'file_creation_date': current_file_datetime,
                })
            elif record_type == '02':
                bank_name = parts[1] if len(parts) > 1 else ''

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

                current_group = Group.create({
                    'ultimate_receiver_identification': bank_name,
                    'file_id': current_file.id if current_file else False,
                    'group_date': current_group_date if current_group_date else fields.Date.today(),
                })

                current_account = None
            elif record_type == '03' and current_group:
                account_number = parts[1] if len(parts) > 1 else ''

                current_account = Account.search([
                    ('account_number', '=', account_number)
                ], limit=1)

                current_account = Account.create({
                    'account_number': account_number,
                    'group_id': current_group.id,
                    'account_name': pending_account_name if pending_account_name else '',
                })
            # ---------------- TRANSACTION 16 ----------------
            elif record_type == '16' and current_account:

                type_code = parts[1] if len(parts) > 1 else ''
                raw_amount = parts[2] if len(parts) > 2 else '0'
                fund_type = parts[3] if len(parts) > 3 else 'Z'
                print('-- -- fund_type-- ---', fund_type)
                
                amount = float(raw_amount) / 100 if raw_amount else 0.0
                
                if type_code in CREDIT_CODES:
                    trx_type = 'credit'
                elif type_code in DEBIT_CODES:
                    trx_type = 'debit'
                else:
                    trx_type = 'debit'

                trx_date = current_group_date
                
                if fund_type == 'V':
                    if len(parts) > 4 and parts[4]:
                        raw_date = parts[4]

                        year = int('20' + raw_date[0:2])
                        month = int(raw_date[2:4])
                        day = int(raw_date[4:6])

                        hour = 0
                        minute = 0

                        if len(parts) > 5 and parts[5]:
                            raw_time = parts[5]
                            hour = int(raw_time[0:2])
                            minute = int(raw_time[2:4])

                        trx_datetime = datetime.datetime(year, month, day, hour, minute)

                        trx_date = trx_datetime.date()
                        print("--- -- trx_date --- --", trx_date)
                
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
                    ('transaction_date', '=', trx_date if trx_date else current_group_date),
                ], limit=1)

                if existing:
                    last_transaction = existing
                    continue

                last_transaction = TransactionModel.create({
                    'account_id': current_account.id,
                    'type_code': type_code,
                    'amount': amount,
                    'transaction_type': trx_type,
                    'fund_type': fund_type,
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
    
    def action_download_file(self):
        self.ensure_one()
        for rec in self:
            rec.file_data = base64.b64encode(rec.file_description.encode('utf-8'))
            print("- -- action_download_file- -")
        return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{self._name}/{self.id}/file_data/{self.file_name}?download=true',
        'target': 'self',
    }


    def test_sftp_connection(self):
        
        username = self.env['ir.config_parameter'].sudo().get_param('bsi_bank_connection.sftp_username')
        password = self.env['ir.config_parameter'].sudo().get_param('bsi_bank_connection.sftp_password')
        
        print("------ sftp connection details ----- username---", username)
        print("------ sftp connection details ----- password---", password)
        
        if not username and password:
            raise ValidationError("SFTP account credentials could not be fetched.")
        
        host = '178.156.207.111'
        port = 22
        username = username
        password = password

        transport = None
        sftp = None

        try:    
            print("== =start= ==connect with sftp server -======")
            transport = paramiko.Transport((host, port))
            transport.connect(username=username, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            print("== =end= ==connect with sftp server -======")
        except Exception as e:
            raise UserError(("SFTP Error: %s") % str(e))

        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()