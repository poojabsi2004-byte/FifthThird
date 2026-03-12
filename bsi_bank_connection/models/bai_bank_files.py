from odoo import fields, models, api

class BSIBankFile(models.Model):
    _name = "bai.bank.files"
    _description = "BSI Bank File"
    _rec_name = "sender_identification"
    
    sender_identification = fields.Char(string="Sender Identification")
    receiver_identification = fields.Char(string="Receiver Identification")
    group_ids = fields.One2many('bai.bank.groups','file_id',string="Groups")
    # file_creation_date = fields.Datetime(string="File Creation Date YYDDMM format")
    # file_dentification_number = fields.Integer(string="File Identification Number Identification")
