from odoo import fields, models

class BAIStoresGroups(models.Model):
    _name = 'bai.groups'
    _description = 'BAI Stores(Bank)'
    
    name = fields.Char(string="Group Name")
    account_ids = fields.Many2many('bai.group.accounts',string="Accounts")
    