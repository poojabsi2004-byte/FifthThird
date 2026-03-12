from odoo import fields, models

class BAIStoreGroupAccounts(models.Model):
    _name = 'bai.group.accounts'
    _description = 'BAI Stores Group Accounts'
    
    name = fields.Char(string="Account Name")
    group_ids = fields.Many2many('bai.groups', string="Groups")
    transaction_ids = fields.One2many('bai.transaction','account_id',string="Trasaction")
    