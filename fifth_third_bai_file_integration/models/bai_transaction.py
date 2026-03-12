from odoo import models, fields

class BaiTransaction(models.Model):
    _name = 'bai.transaction'
    _description = 'BAI Transaction'
    _order = 'id desc'

    account_number = fields.Char(string="Account Number")
    transaction_code = fields.Char(string="BAI Code")
    amount = fields.Float(string="Amount")
    description = fields.Char(string="Description")
    account_id = fields.Many2one("bai.group.accounts", string="Account")
   