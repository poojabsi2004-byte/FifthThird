from odoo import models, api, _
import csv, io, logging
import paramiko
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)

 

    @api.model
    def process_bai_content(self, content):
        print("=== == == =3452345243523= =======")
        current_group = None
        current_account = None

        Group = self.env['bai.groups'].sudo()
        Account = self.env['bai.group.accounts'].sudo()
        Transaction = self.env['bai.transaction'].sudo()
        Transaction_record = self.env['bai.transaction'].sudo().search([])

        for raw_line in content.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            if line.endswith('/'):
                line = line[:-1]

            parts = line.split(',')
            record_type = parts[0]

            # GROUP HEADER (02)
            if record_type == '02':
                print("-- --- - --- record type in if '02'",parts[1])
                group_name = parts[1]

                current_group = Group.search(
                    [('name', '=', group_name)],
                    limit=1
                )

                if not current_group:
                    current_group = Group.create({
                        'name': group_name,
                    })

                current_account = None  # reset
                _logger.info("Group: %s", current_group.name)

            # ACCOUNT HEADER (03)
            elif record_type == '03' and current_group:
                print("-- --- - --- record type in if '03'",parts[1])
                account_number = parts[1]

                current_account = Account.search([
                    ('name', '=', account_number),
                    ('group_ids', 'in', current_group.id)
                ], limit=1)

                if not current_account:
                    current_account = Account.create({
                        'name': account_number,
                        'group_ids': [(4, current_group.id)],
                    })

                _logger.info("Account: %s", current_account.name)

            # TRANSACTION (16)
            
            elif record_type == '16' and current_account:
                type_code = []
                print("-- --- - --- record type in [if '16']",parts[1])
                for code in Transaction_record:
                    type_code.append(code.transaction_code)
                    
                print("-- -- -tyep code---", type_code)
                if parts[1] not in type_code:
                    Transaction.create({
                        'account_number': current_account.name,
                        'account_id': current_account.id,
                        'transaction_code': parts[1],
                        'amount': float(parts[2]),
                        'description': parts[3] if len(parts) > 3 else '',
                        
                    })
                else:
                    continue

            # ACCOUNT TRAILER (49)
            elif record_type == '49':
                current_account = None

            # GROUP TRAILER (98)
            elif record_type == '98':
                current_group = None

        return True
