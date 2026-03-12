from odoo import models, fields, api
import base64
import paramiko

class BaiImport(models.Model):
    _name = 'bai.import'
    _description = 'BAI File Import'

    name = fields.Char(default="BAI Import")
    bai_file = fields.Binary(string="BAI File", required=True)
    filename = fields.Char(string="File Name")

    def action_import_file(self):
        content = base64.b64decode(self.bai_file).decode('utf-8')

        current_group_rec = None
        current_account_rec = None
        
        Group = self.env['bai.groups'].sudo()
        Account = self.env['bai.group.accounts'].sudo()
        Transaction = self.env['bai.transaction'].sudo()
        
        for raw_line in content.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            if line.endswith('/'):
                line = line[:-1]

            parts = line.split(',')
            record_type = parts[0]

            if record_type == '02':
                group_name = parts[1]

                    
                if group_name in Group:
                    current_account_rec = self.env['bai.group.accounts'].sudo().create({
                    'name': account_name,
                    'group_ids': Group.id,
                })
                else:
                    current_group_rec = self.env['bai.groups'].sudo().create({
                        'name': group_name,
                    })

                print("Created Group:", current_group_rec.name)

            elif record_type == '03':
                account_name = parts[1]

                current_account_rec = self.env['bai.group.accounts'].sudo().create({
                    'name': account_name,
                    'group_ids': [(4, current_group_rec.id)] if current_group_rec else [],
                })

                # also add account to group side (optional but clean)
                current_group_rec.write({
                    'account_ids': [(4, current_account_rec.id)]
                })

                print(" Created Account:", current_account_rec.name)

            # elif record_type == '16':
                
            #     transection_record = self.env['bai.transaction'].create({
            #         'account_number': current_account_rec.name if current_account_rec else False,
            #         'transaction_code': parts[1],
            #         'amount': float(parts[2]),
            #         'description': parts[3] if len(parts) > 3 else '',
            #         'account_id': current_account_rec.id if current_account_rec else False,
            #     })

            #     print("Transaction:", transection_record)
            elif record_type == '16' and current_account_rec:
                
                transaction_code = parts[1]
                amount = float(parts[2])
                description = parts[3] if len(parts) > 3 else ''

                existing_tx = self.env['bai.transaction'].search([
                    ('account_number', '=', current_account_rec.name),
                    ('transaction_code', '=', transaction_code),
                ], limit=1)

                if existing_tx:
                    _logger.info(
                        "Transaction already exists (Account=%s, Code=%s, Amount=%s)",
                        current_account_rec.name, transaction_code, amount
                    )
                    return  # or continue

                transection_record = self.env['bai.transaction'].create({
                    'account_id': current_account_rec.id,
                    'account_number': current_account_rec.name,
                    'transaction_code': transaction_code,
                    'amount': amount,
                    'description': description,
                    
                })
                print("-- --- - -imported_file",Transaction.imported_file )

                _logger.info("Transaction created: %s", transection_record.id)



            