from odoo import fields, models, api

class BSIBankAccountTransaction(models.Model):
    _name = "bai.bank.account.transactions"
    _description = "BSI Bank Accounts Transaction"

    type_code = fields.Char(string="Type Code")
    description = fields.Char(string="Description")
    transaction_type = fields.Selection([('credit', 'Credit'), ('debit', 'Debit')], string="Transaction Type")
    amount = fields.Float(string="Amount")
    account_id = fields.Many2one("bai.bank.accounts",string="Account")
    transaction_date = fields.Date("Transaction Date")