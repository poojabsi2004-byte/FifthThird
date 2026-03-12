from odoo import fields, models, api

class BSIBankAccount(models.Model):
    _name = "bai.bank.accounts"
    _description = "BSI Bank Accounts"
    _rec_name = "account_number"
    
    account_number = fields.Char(string="Account Number")
    account_name = fields.Char(string="Account Name")
    group_id = fields.Many2one('bai.bank.groups',string="Group")
    transaction_ids = fields.One2many('bai.bank.account.transactions','account_id',string="Transactions")
    