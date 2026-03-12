from odoo import fields, models, api

class BSIBanGroups(models.Model):
    _name = "bai.bank.groups"
    _description = "BSI Bank Groups"
    _rec_name = 'ultimate_receiver_identification'
    
    ultimate_receiver_identification = fields.Char(string="Ultimate Receiver identification")
    file_id = fields.Many2one('bai.bank.files',string="File")
    account_ids = fields.One2many("bai.bank.accounts",'group_id',string="Accounts")